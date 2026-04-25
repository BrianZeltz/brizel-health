"""Focused tests for backup/recovery key hierarchy foundations."""

from __future__ import annotations

import asyncio
import os
import sys
import types
from base64 import urlsafe_b64encode
from datetime import UTC, datetime

homeassistant_module = types.ModuleType("homeassistant")
core_module = types.ModuleType("homeassistant.core")
core_module.HomeAssistant = object
helpers_module = types.ModuleType("homeassistant.helpers")
storage_module = types.ModuleType("homeassistant.helpers.storage")


class _DummyStore:
    def __init__(self, *_args, **_kwargs) -> None:
        pass


storage_module.Store = _DummyStore
sys.modules.setdefault("homeassistant", homeassistant_module)
sys.modules.setdefault("homeassistant.core", core_module)
sys.modules.setdefault("homeassistant.helpers", helpers_module)
sys.modules.setdefault("homeassistant.helpers.storage", storage_module)

from custom_components.brizel_health.infrastructure.repositories.ha_key_hierarchy_repository import (
    HomeAssistantKeyHierarchyRepository,
)
from custom_components.brizel_health.infrastructure.security.ha_local_crypto_service import (
    HomeAssistantLocalCryptoService,
)
from custom_components.brizel_health.infrastructure.storage.store_manager import (
    get_default_storage_data,
)
from custom_components.brizel_health.domains.security.models.key_hierarchy import (
    ENVELOPE_MATERIAL_STATE_LOCAL_DIRECT,
    ENVELOPE_MATERIAL_STATE_PENDING_WRAP,
    ENVELOPE_MATERIAL_STATE_WRAPPED,
    ENVELOPE_RECIPIENT_NODE,
    ENVELOPE_RECIPIENT_RECOVERY,
    ENVELOPE_WRAP_MECHANISM_NODE_ENROLLMENT_WRAPPED,
    ENVELOPE_WRAP_MECHANISM_LOCAL_DIRECT,
    ENVELOPE_WRAP_MECHANISM_NODE_PREPARED,
    ENVELOPE_WRAP_MECHANISM_NODE_WRAPPED,
    NODE_ENROLLMENT_ALGORITHM,
    ENVELOPE_WRAP_MECHANISM_RECOVERY_KEY_WRAPPED,
    ENVELOPE_WRAP_MECHANISM_RECOVERY_PASSPHRASE_WRAPPED,
    ENVELOPE_WRAP_MECHANISM_RECOVERY_PREPARED,
    JOIN_REQUEST_STATUS_EXPIRED,
    JOIN_REQUEST_STATUS_PENDING,
    JoinEnrollmentRequest,
    PROTECTED_DATA_CLASS_HISTORY_PAYLOADS,
    PROTECTED_DATA_CLASS_KEY_MATERIAL,
    RecoveryKeyMetadata,
    RECOVERY_KDF_NONE,
    RECOVERY_KDF_PBKDF2_SHA256,
    RECOVERY_METHOD_DIRECT_KEY,
    RECOVERY_METHOD_PASSPHRASE,
)


class FakeStoreManager:
    """Tiny async-save store shim for repository tests."""

    def __init__(self) -> None:
        self.data = get_default_storage_data()
        self.save_count = 0

    async def async_save(self) -> None:
        self.save_count += 1


def test_default_storage_data_includes_separate_security_metadata_and_secrets() -> None:
    data = get_default_storage_data()

    assert data["security"]["metadata"]["server_enrollment"] is None
    assert data["security"]["metadata"]["profile_keys"] == {}
    assert data["security"]["metadata"]["key_envelopes"] == {}
    assert data["security"]["metadata"]["recovery_keys"] == {}
    assert data["security"]["metadata"]["join_requests"] == {}
    assert data["security"]["secrets"]["server_node_keys"] == {}
    assert data["security"]["secrets"]["server_enrollment_private_keys"] == {}
    assert data["security"]["secrets"]["profile_keys"] == {}
    assert data["security"]["secrets"]["wrapped_profile_keys"] == {}


def test_storage_plan_marks_history_payloads_encrypted_and_key_material_hidden() -> None:
    repository = HomeAssistantKeyHierarchyRepository(FakeStoreManager())
    plan = repository.storage_plan()

    history_class = next(
        entry
        for entry in plan
        if entry.data_class_id == PROTECTED_DATA_CLASS_HISTORY_PAYLOADS
    )
    key_material_class = next(
        entry
        for entry in plan
        if entry.data_class_id == PROTECTED_DATA_CLASS_KEY_MATERIAL
    )

    assert history_class.encrypt_at_rest is True
    assert "record_id" in history_class.sync_visible_fields
    assert "updated_at" in history_class.sync_visible_fields
    assert key_material_class.encrypt_at_rest is True
    assert key_material_class.visible_metadata_fields == ()


def test_server_node_context_persists_stable_metadata_and_separate_secret_material() -> None:
    store_manager = FakeStoreManager()
    repository = HomeAssistantKeyHierarchyRepository(store_manager)

    first = asyncio.run(repository.ensure_server_node_context())
    second = asyncio.run(repository.ensure_server_node_context())

    assert first.node_id.startswith("node-ha-")
    assert first.node_key_id.startswith("node-key-")
    assert second.node_key_id == first.node_key_id
    assert store_manager.data["security"]["metadata"]["server_node"]["node_key_id"] == (
        first.node_key_id
    )
    assert (
        first.node_key_id
        in store_manager.data["security"]["secrets"]["server_node_keys"]
    )


def test_server_enrollment_context_persists_public_descriptor_and_private_material() -> None:
    store_manager = FakeStoreManager()
    repository = HomeAssistantKeyHierarchyRepository(store_manager)

    first = asyncio.run(repository.ensure_server_enrollment_context())
    second = asyncio.run(repository.ensure_server_enrollment_context())
    descriptor = repository.get_server_enrollment_descriptor()

    assert first.node_id.startswith("node-ha-")
    assert first.recipient_key_id.startswith("node-enroll-")
    assert first.algorithm == NODE_ENROLLMENT_ALGORITHM
    assert first.public_key_b64
    assert second.recipient_key_id == first.recipient_key_id
    assert descriptor is not None
    assert descriptor.node_id == first.node_id
    assert descriptor.recipient_key_id == first.recipient_key_id
    assert (
        first.recipient_key_id
        in store_manager.data["security"]["secrets"]["server_enrollment_private_keys"]
    )


def test_profile_key_context_creates_local_server_envelope() -> None:
    store_manager = FakeStoreManager()
    repository = HomeAssistantKeyHierarchyRepository(store_manager)

    profile_key = asyncio.run(repository.ensure_profile_key_context("profile-a"))
    envelopes = repository.list_envelopes()

    assert profile_key.profile_id == "profile-a"
    assert (
        profile_key.profile_key_id
        not in store_manager.data["security"]["secrets"]["profile_keys"]
    )
    assert len(envelopes) == 1
    assert envelopes[0].recipient_kind == ENVELOPE_RECIPIENT_NODE
    assert envelopes[0].wrap_mechanism == ENVELOPE_WRAP_MECHANISM_LOCAL_DIRECT
    assert envelopes[0].material_state == ENVELOPE_MATERIAL_STATE_LOCAL_DIRECT
    assert envelopes[0].wrapped_key_material_id
    assert (
        envelopes[0].wrapped_key_material_id
        in store_manager.data["security"]["secrets"]["wrapped_profile_keys"]
    )
    assert envelopes[0].wrapped_key_material is None


def test_authorized_node_envelope_is_prepared_without_fake_wrapped_material() -> None:
    store_manager = FakeStoreManager()
    repository = HomeAssistantKeyHierarchyRepository(store_manager)

    envelope = asyncio.run(
        repository.prepare_authorized_node_envelope(
            profile_id="profile-a",
            recipient_node_id="node-app-b",
            recipient_node_key_id="node-key-app-b",
        )
    )

    assert envelope.recipient_kind == ENVELOPE_RECIPIENT_NODE
    assert envelope.recipient_id == "node-key-app-b"
    assert envelope.wrap_mechanism == ENVELOPE_WRAP_MECHANISM_NODE_PREPARED
    assert envelope.material_state == ENVELOPE_MATERIAL_STATE_PENDING_WRAP
    assert envelope.wrapped_key_material is None
    assert envelope.metadata["recipient_node_id"] == "node-app-b"


def test_recovery_passphrase_envelope_tracks_kdf_metadata() -> None:
    store_manager = FakeStoreManager()
    repository = HomeAssistantKeyHierarchyRepository(store_manager)

    envelope, recovery_key = asyncio.run(
        repository.prepare_recovery_passphrase_envelope(profile_id="profile-a")
    )

    assert recovery_key.kind == RECOVERY_METHOD_PASSPHRASE
    assert recovery_key.kdf_algorithm == RECOVERY_KDF_PBKDF2_SHA256
    assert recovery_key.iterations > 0
    assert recovery_key.salt_b64
    assert envelope.recipient_kind == ENVELOPE_RECIPIENT_RECOVERY
    assert envelope.wrap_mechanism == ENVELOPE_WRAP_MECHANISM_RECOVERY_PREPARED
    assert envelope.material_state == ENVELOPE_MATERIAL_STATE_PENDING_WRAP
    assert envelope.metadata["recovery_id"] == recovery_key.recovery_id


def test_local_crypto_service_rewraps_profile_key_for_authorized_node() -> None:
    store_manager = FakeStoreManager()
    repository = HomeAssistantKeyHierarchyRepository(store_manager)
    crypto_service = HomeAssistantLocalCryptoService(repository)
    recipient_node_key_material = _random_base64url(32)

    envelope = asyncio.run(
        crypto_service.wrap_profile_key_for_authorized_node(
            profile_id="profile-a",
            recipient_node_id="node-app-b",
            recipient_node_key_id="node-key-app-b",
            recipient_node_key_material=recipient_node_key_material,
        )
    )

    assert envelope.wrap_mechanism == ENVELOPE_WRAP_MECHANISM_NODE_WRAPPED
    assert envelope.material_state == ENVELOPE_MATERIAL_STATE_WRAPPED
    assert envelope.wrapped_key_material_id
    assert envelope.wrapped_key_material is None
    assert (
        envelope.wrapped_key_material_id
        in store_manager.data["security"]["secrets"]["wrapped_profile_keys"]
    )

    unwrapped = crypto_service.unwrap_authorized_node_envelope(
        envelope=envelope,
        recipient_node_key_material=recipient_node_key_material,
    )

    assert len(unwrapped) == 32


def test_local_crypto_service_can_rewrap_for_enrollment_descriptor() -> None:
    sender_store = FakeStoreManager()
    sender_repository = HomeAssistantKeyHierarchyRepository(sender_store)
    sender_crypto = HomeAssistantLocalCryptoService(sender_repository)

    recipient_store = FakeStoreManager()
    recipient_repository = HomeAssistantKeyHierarchyRepository(recipient_store)
    recipient_crypto = HomeAssistantLocalCryptoService(recipient_repository)
    recipient_descriptor = asyncio.run(
        recipient_repository.ensure_server_enrollment_context()
    ).to_descriptor()

    sender_envelope = asyncio.run(
        sender_crypto.wrap_profile_key_for_enrollment_descriptor(
            profile_id="profile-a",
            recipient=recipient_descriptor,
        )
    )
    wrapped_material_json = sender_repository.get_wrapped_key_material(
        sender_envelope.wrapped_key_material_id or ""
    )

    assert sender_envelope.wrap_mechanism == ENVELOPE_WRAP_MECHANISM_NODE_ENROLLMENT_WRAPPED
    assert sender_envelope.material_state == ENVELOPE_MATERIAL_STATE_WRAPPED
    assert sender_envelope.metadata["recipient_node_id"] == recipient_descriptor.node_id
    assert (
        sender_envelope.metadata["recipient_key_id"]
        == recipient_descriptor.recipient_key_id
    )
    assert sender_envelope.metadata["ephemeral_public_key_b64"]
    assert wrapped_material_json

    unwrapped = recipient_crypto.unwrap_enrollment_envelope_for_current_node(
        envelope=sender_envelope,
        wrapped_material_json=wrapped_material_json,
    )

    assert len(unwrapped) == 32


def test_local_crypto_service_supports_recovery_key_and_passphrase_wraps() -> None:
    store_manager = FakeStoreManager()
    repository = HomeAssistantKeyHierarchyRepository(store_manager)
    crypto_service = HomeAssistantLocalCryptoService(repository)
    recovery_key_material = _random_base64url(32)

    recovery_envelope, recovery_key = asyncio.run(
        crypto_service.wrap_profile_key_for_recovery_key(
            profile_id="profile-a",
            recovery_key_material=recovery_key_material,
        )
    )
    passphrase_envelope, passphrase_key = asyncio.run(
        crypto_service.wrap_profile_key_for_recovery_passphrase(
            profile_id="profile-a",
            passphrase="alpha bravo charlie delta",
        )
    )

    assert recovery_key.kind == RECOVERY_METHOD_DIRECT_KEY
    assert recovery_key.kdf_algorithm == RECOVERY_KDF_NONE
    assert recovery_envelope.wrap_mechanism == ENVELOPE_WRAP_MECHANISM_RECOVERY_KEY_WRAPPED
    assert recovery_envelope.material_state == ENVELOPE_MATERIAL_STATE_WRAPPED
    assert passphrase_key.kind == RECOVERY_METHOD_PASSPHRASE
    assert passphrase_key.kdf_algorithm == RECOVERY_KDF_PBKDF2_SHA256
    assert (
        passphrase_envelope.wrap_mechanism
        == ENVELOPE_WRAP_MECHANISM_RECOVERY_PASSPHRASE_WRAPPED
    )
    assert passphrase_envelope.material_state == ENVELOPE_MATERIAL_STATE_WRAPPED

    from_recovery_key = crypto_service.unwrap_recovery_key_envelope(
        envelope=recovery_envelope,
        recovery_key_material=recovery_key_material,
    )
    from_passphrase = crypto_service.unwrap_recovery_passphrase_envelope(
        envelope=passphrase_envelope,
        passphrase="alpha bravo charlie delta",
    )

    assert from_recovery_key == from_passphrase
    assert len(from_recovery_key) == 32


def test_local_crypto_service_migrates_legacy_raw_profile_key_material_to_local_wrap() -> None:
    store_manager = FakeStoreManager()
    repository = HomeAssistantKeyHierarchyRepository(store_manager)
    crypto_service = HomeAssistantLocalCryptoService(repository)
    server_node = asyncio.run(repository.ensure_server_node_context())
    now = datetime(2026, 4, 25, 10, tzinfo=UTC)
    profile_key_id = "profile-key-legacy"
    raw_key_material = _random_base64url(32)

    store_manager.data["security"]["metadata"]["profile_keys"]["profile-a"] = {
        "profile_id": "profile-a",
        "profile_key_id": profile_key_id,
        "key_version": 1,
        "algorithm": "profile_key_random_256_v1",
        "created_at": now.isoformat().replace("+00:00", "Z"),
        "updated_at": now.isoformat().replace("+00:00", "Z"),
    }
    store_manager.data["security"]["metadata"]["key_envelopes"]["env-legacy"] = {
        "envelope_id": "env-legacy",
        "profile_key_id": profile_key_id,
        "profile_key_version": 1,
        "recipient_kind": ENVELOPE_RECIPIENT_NODE,
        "recipient_id": server_node.node_key_id,
        "wrap_mechanism": ENVELOPE_WRAP_MECHANISM_LOCAL_DIRECT,
        "material_state": ENVELOPE_MATERIAL_STATE_LOCAL_DIRECT,
        "wrapped_key_material_id": None,
        "wrapped_key_material": None,
        "metadata": {
            "node_id": server_node.node_id,
            "node_key_id": server_node.node_key_id,
            "access_scope": "current_home_assistant_installation",
        },
        "created_at": now.isoformat().replace("+00:00", "Z"),
        "updated_at": now.isoformat().replace("+00:00", "Z"),
    }
    store_manager.data["security"]["secrets"]["profile_keys"][profile_key_id] = (
        raw_key_material
    )

    envelope = asyncio.run(
        crypto_service.encrypt_profile_payload(
            profile_id="profile-a",
            data_class_id=PROTECTED_DATA_CLASS_HISTORY_PAYLOADS,
            payload={"note": "legacy migration"},
            aad_context={"profile_id": "profile-a", "kind": "legacy-test"},
        )
    )
    round_trip = asyncio.run(
        crypto_service.decrypt_profile_payload(
            profile_id="profile-a",
            envelope=envelope,
            expected_aad_context={"profile_id": "profile-a", "kind": "legacy-test"},
        )
    )
    migrated_envelope = repository.get_envelope("env-legacy")

    assert round_trip["note"] == "legacy migration"
    assert profile_key_id not in store_manager.data["security"]["secrets"]["profile_keys"]
    assert migrated_envelope is not None
    assert migrated_envelope.wrapped_key_material_id
    assert (
        migrated_envelope.wrapped_key_material_id
        in store_manager.data["security"]["secrets"]["wrapped_profile_keys"]
    )


def test_key_hierarchy_audit_is_clean_for_valid_local_direct_state() -> None:
    store_manager = FakeStoreManager()
    repository = HomeAssistantKeyHierarchyRepository(store_manager)

    asyncio.run(repository.ensure_profile_key_context("profile-a"))
    report = repository.audit_key_hierarchy()

    assert report.findings == ()
    assert report.has_errors is False


def test_key_hierarchy_audit_flags_missing_wrapped_material_and_orphan_material() -> None:
    store_manager = FakeStoreManager()
    repository = HomeAssistantKeyHierarchyRepository(store_manager)

    asyncio.run(repository.ensure_profile_key_context("profile-a"))
    envelope = repository.list_envelopes()[0]
    original_material_id = envelope.wrapped_key_material_id
    store_manager.data["security"]["metadata"]["key_envelopes"][envelope.envelope_id][
        "wrapped_key_material_id"
    ] = "missing-material"

    report = repository.audit_key_hierarchy()
    codes = {finding.code for finding in report.findings}

    assert "envelope_missing_wrapped_material" in codes
    assert "orphan_wrapped_material" in codes
    assert any(
        finding.wrapped_key_material_id == original_material_id
        for finding in report.findings
        if finding.code == "orphan_wrapped_material"
    )


def test_key_hierarchy_audit_flags_raw_and_wrapped_plus_recovery_without_envelope() -> None:
    store_manager = FakeStoreManager()
    repository = HomeAssistantKeyHierarchyRepository(store_manager)
    now = datetime(2026, 4, 25, 12, tzinfo=UTC)

    profile_key = asyncio.run(repository.ensure_profile_key_context("profile-a"))
    store_manager.data["security"]["secrets"]["profile_keys"][
        profile_key.profile_key_id
    ] = _random_base64url(32)
    store_manager.data["security"]["metadata"]["recovery_keys"][
        "recovery-orphan"
    ] = RecoveryKeyMetadata(
        recovery_id="recovery-orphan",
        kind=RECOVERY_METHOD_PASSPHRASE,
        kdf_algorithm=RECOVERY_KDF_PBKDF2_SHA256,
        iterations=210000,
        salt_b64=_random_base64url(16),
        created_at=now,
        updated_at=now,
    ).to_dict()

    report = repository.audit_key_hierarchy()
    codes = {finding.code for finding in report.findings}

    assert "raw_profile_key_material_still_present_after_wrap" in codes
    assert "recovery_key_missing_envelope" in codes
    assert report.has_errors is True


def test_key_hierarchy_audit_flags_missing_local_direct_envelope() -> None:
    store_manager = FakeStoreManager()
    repository = HomeAssistantKeyHierarchyRepository(store_manager)

    profile_key = asyncio.run(repository.ensure_profile_key_context("profile-a"))
    store_manager.data["security"]["metadata"]["key_envelopes"] = {}

    report = repository.audit_key_hierarchy()

    assert any(
        finding.code == "profile_key_missing_local_direct_envelope"
        and finding.profile_key_id == profile_key.profile_key_id
        for finding in report.findings
    )


def test_key_hierarchy_audit_flags_local_direct_recipient_mismatch() -> None:
    store_manager = FakeStoreManager()
    repository = HomeAssistantKeyHierarchyRepository(store_manager)

    asyncio.run(repository.ensure_profile_key_context("profile-a"))
    envelope = repository.list_envelopes()[0]
    store_manager.data["security"]["metadata"]["key_envelopes"][envelope.envelope_id][
        "recipient_id"
    ] = "node-key-wrong"
    store_manager.data["security"]["metadata"]["key_envelopes"][envelope.envelope_id][
        "metadata"
    ] = {
        **store_manager.data["security"]["metadata"]["key_envelopes"][
            envelope.envelope_id
        ]["metadata"],
        "node_id": "node-wrong",
        "node_key_id": "node-key-wrong",
    }

    report = repository.audit_key_hierarchy()

    assert any(
        finding.code == "local_direct_envelope_recipient_mismatch"
        and finding.envelope_id == envelope.envelope_id
        for finding in report.findings
    )


def test_key_hierarchy_audit_flags_join_request_without_approval_envelope() -> None:
    store_manager = FakeStoreManager()
    repository = HomeAssistantKeyHierarchyRepository(store_manager)
    recipient = asyncio.run(repository.ensure_server_enrollment_context()).to_descriptor()
    request = JoinEnrollmentRequest(
        request_id="join-approved-1",
        profile_id="profile-a",
        requesting_node_id="node-app-b",
        recipient=recipient,
        requested_at=datetime(2026, 4, 20, 10, 10, tzinfo=UTC),
        expires_at=datetime(2026, 4, 20, 11, 10, tzinfo=UTC),
        status="approved",
        approval_id="approval-1",
        approval_envelope_id="env-missing",
        approved_by_node_id="home_assistant",
        approved_by_node_key_id="node-key-ha",
        approved_at=datetime(2026, 4, 20, 10, 12, tzinfo=UTC),
    )

    asyncio.run(repository.create_join_request(request))
    report = repository.audit_key_hierarchy(
        now=datetime(2026, 4, 20, 10, 20, tzinfo=UTC)
    )

    assert any(
        finding.code == "join_request_missing_approval_envelope"
        and finding.request_id == request.request_id
        for finding in report.findings
    )


def test_key_hierarchy_audit_flags_pending_envelope_with_material() -> None:
    store_manager = FakeStoreManager()
    repository = HomeAssistantKeyHierarchyRepository(store_manager)

    envelope = asyncio.run(
        repository.prepare_recovery_passphrase_envelope(profile_id="profile-a")
    )[0]
    store_manager.data["security"]["secrets"]["wrapped_profile_keys"][
        "pending-material"
    ] = "{}"
    store_manager.data["security"]["metadata"]["key_envelopes"][envelope.envelope_id][
        "wrapped_key_material_id"
    ] = "pending-material"

    report = repository.audit_key_hierarchy()

    assert any(
        finding.code == "pending_envelope_has_material"
        and finding.envelope_id == envelope.envelope_id
        for finding in report.findings
    )


def test_recovery_passphrase_unwrap_fails_with_wrong_secret() -> None:
    store_manager = FakeStoreManager()
    repository = HomeAssistantKeyHierarchyRepository(store_manager)
    crypto_service = HomeAssistantLocalCryptoService(repository)

    envelope, _recovery_key = asyncio.run(
        crypto_service.wrap_profile_key_for_recovery_passphrase(
            profile_id="profile-a",
            passphrase="correct horse battery staple",
        )
    )

    try:
        crypto_service.unwrap_recovery_passphrase_envelope(
            envelope=envelope,
            passphrase="totally wrong secret",
        )
    except Exception:
        assert True
    else:
        raise AssertionError("Expected wrong passphrase unwrap to fail.")


def test_join_request_repository_tracks_request_and_effective_expiry() -> None:
    store_manager = FakeStoreManager()
    repository = HomeAssistantKeyHierarchyRepository(store_manager)
    recipient = asyncio.run(repository.ensure_server_enrollment_context()).to_descriptor()
    request = JoinEnrollmentRequest(
        request_id="join-request-1",
        profile_id="profile-a",
        requesting_node_id="node-app-b",
        recipient=recipient,
        requested_at=datetime(2026, 4, 20, 10, 10, tzinfo=UTC),
        expires_at=datetime(2026, 4, 20, 10, 20, tzinfo=UTC),
        status=JOIN_REQUEST_STATUS_PENDING,
    )

    asyncio.run(repository.create_join_request(request))
    live = repository.get_join_request(
        "join-request-1",
        now=datetime(2026, 4, 20, 10, 15, tzinfo=UTC),
    )
    expired = repository.get_join_request(
        "join-request-1",
        now=datetime(2026, 4, 20, 10, 25, tzinfo=UTC),
    )

    assert live is not None
    assert live.status == JOIN_REQUEST_STATUS_PENDING
    assert expired is not None
    assert expired.status == JOIN_REQUEST_STATUS_EXPIRED


def _random_base64url(length: int) -> str:
    return urlsafe_b64encode(os.urandom(length)).decode("ascii").rstrip("=")
