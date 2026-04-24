"""Focused tests for backup/recovery key hierarchy foundations."""

from __future__ import annotations

import asyncio
import os
import sys
import types
from base64 import urlsafe_b64encode

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
    ENVELOPE_WRAP_MECHANISM_LOCAL_DIRECT,
    ENVELOPE_WRAP_MECHANISM_NODE_PREPARED,
    ENVELOPE_WRAP_MECHANISM_NODE_WRAPPED,
    ENVELOPE_WRAP_MECHANISM_RECOVERY_KEY_WRAPPED,
    ENVELOPE_WRAP_MECHANISM_RECOVERY_PASSPHRASE_WRAPPED,
    ENVELOPE_WRAP_MECHANISM_RECOVERY_PREPARED,
    PROTECTED_DATA_CLASS_HISTORY_PAYLOADS,
    PROTECTED_DATA_CLASS_KEY_MATERIAL,
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

    assert data["security"]["metadata"]["profile_keys"] == {}
    assert data["security"]["metadata"]["key_envelopes"] == {}
    assert data["security"]["metadata"]["recovery_keys"] == {}
    assert data["security"]["secrets"]["server_node_keys"] == {}
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


def test_profile_key_context_creates_local_server_envelope() -> None:
    store_manager = FakeStoreManager()
    repository = HomeAssistantKeyHierarchyRepository(store_manager)

    profile_key = asyncio.run(repository.ensure_profile_key_context("profile-a"))
    envelopes = repository.list_envelopes()

    assert profile_key.profile_id == "profile-a"
    assert (
        profile_key.profile_key_id
        in store_manager.data["security"]["secrets"]["profile_keys"]
    )
    assert len(envelopes) == 1
    assert envelopes[0].recipient_kind == ENVELOPE_RECIPIENT_NODE
    assert envelopes[0].wrap_mechanism == ENVELOPE_WRAP_MECHANISM_LOCAL_DIRECT
    assert envelopes[0].material_state == ENVELOPE_MATERIAL_STATE_LOCAL_DIRECT
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


def _random_base64url(length: int) -> str:
    return urlsafe_b64encode(os.urandom(length)).decode("ascii").rstrip("=")
