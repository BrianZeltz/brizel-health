"""Home Assistant backed backup/recovery key hierarchy repository."""

from __future__ import annotations

import base64
import json
from base64 import urlsafe_b64encode
from datetime import UTC, datetime
from secrets import token_bytes
from typing import TYPE_CHECKING
from uuid import uuid4

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import x25519

from ...domains.security.models.key_hierarchy import (
    AUDIT_SEVERITY_ERROR,
    AUDIT_SEVERITY_WARNING,
    ENVELOPE_MATERIAL_STATE_LOCAL_DIRECT,
    ENVELOPE_MATERIAL_STATE_PENDING_WRAP,
    ENVELOPE_RECIPIENT_NODE,
    ENVELOPE_RECIPIENT_RECOVERY,
    ENVELOPE_WRAP_MECHANISM_LOCAL_DIRECT,
    ENVELOPE_WRAP_MECHANISM_NODE_PREPARED,
    ENVELOPE_WRAP_MECHANISM_RECOVERY_PREPARED,
    JOIN_REQUEST_STATUS_APPROVED,
    JOIN_REQUEST_STATUS_COMPLETED,
    JOIN_REQUEST_STATUS_EXPIRED,
    JOIN_REQUEST_STATUS_INVALIDATED,
    JOIN_REQUEST_STATUS_PENDING,
    JoinEnrollmentRequest,
    KeyHierarchyAuditFinding,
    KeyHierarchyAuditReport,
    LOCAL_KEY_PROTECTION_CLASS,
    NODE_ENROLLMENT_ALGORITHM,
    NODE_KEY_ALGORITHM,
    NodeEnrollmentContext,
    NodeEnrollmentDescriptor,
    LOCAL_PAYLOAD_AEAD_ALGORITHM,
    LOCAL_WRAPPED_KEY_FORMAT_VERSION,
    PROFILE_KEY_ALGORITHM,
    RECOVERY_KDF_PBKDF2_SHA256,
    RECOVERY_METHOD_PASSPHRASE,
    ProfileKeyContext,
    ProtectedStorageClass,
    RecoveryKeyMetadata,
    ServerNodeKeyContext,
    WrappedKeyMaterialBlob,
    WrappedProfileKeyEnvelope,
    default_storage_protection_plan,
)

if TYPE_CHECKING:
    from ..storage.store_manager import BrizelHealthStoreManager


class HomeAssistantKeyHierarchyRepository:
    """Persist key hierarchy metadata and secret material separately."""

    def __init__(self, store_manager: "BrizelHealthStoreManager") -> None:
        self._store_manager = store_manager

    def storage_plan(self) -> tuple[ProtectedStorageClass, ...]:
        return default_storage_protection_plan()

    def _security(self) -> dict[str, object]:
        security = self._store_manager.data.setdefault("security", {})
        if not isinstance(security, dict):
            self._store_manager.data["security"] = {}
            security = self._store_manager.data["security"]
        return security

    def _metadata(self) -> dict[str, object]:
        metadata = self._security().setdefault("metadata", {})
        if not isinstance(metadata, dict):
            self._security()["metadata"] = {}
            metadata = self._security()["metadata"]
        metadata.setdefault("format_version", 1)
        metadata.setdefault("storage_plan_version", 1)
        metadata.setdefault("server_node", None)
        metadata.setdefault("server_enrollment", None)
        metadata.setdefault("profile_keys", {})
        metadata.setdefault("key_envelopes", {})
        metadata.setdefault("recovery_keys", {})
        metadata.setdefault("join_requests", {})
        return metadata

    def _secrets(self) -> dict[str, object]:
        secrets = self._security().setdefault("secrets", {})
        if not isinstance(secrets, dict):
            self._security()["secrets"] = {}
            secrets = self._security()["secrets"]
        secrets.setdefault("format_version", 1)
        secrets.setdefault("server_node_keys", {})
        secrets.setdefault("server_enrollment_private_keys", {})
        secrets.setdefault("profile_keys", {})
        secrets.setdefault("wrapped_profile_keys", {})
        return secrets

    def _profile_keys(self) -> dict[str, dict]:
        profile_keys = self._metadata().setdefault("profile_keys", {})
        if not isinstance(profile_keys, dict):
            self._metadata()["profile_keys"] = {}
            profile_keys = self._metadata()["profile_keys"]
        return profile_keys

    def _envelopes(self) -> dict[str, dict]:
        envelopes = self._metadata().setdefault("key_envelopes", {})
        if not isinstance(envelopes, dict):
            self._metadata()["key_envelopes"] = {}
            envelopes = self._metadata()["key_envelopes"]
        return envelopes

    def _recovery_keys(self) -> dict[str, dict]:
        recovery_keys = self._metadata().setdefault("recovery_keys", {})
        if not isinstance(recovery_keys, dict):
            self._metadata()["recovery_keys"] = {}
            recovery_keys = self._metadata()["recovery_keys"]
        return recovery_keys

    def _join_requests(self) -> dict[str, dict]:
        join_requests = self._metadata().setdefault("join_requests", {})
        if not isinstance(join_requests, dict):
            self._metadata()["join_requests"] = {}
            join_requests = self._metadata()["join_requests"]
        return join_requests

    def _server_node_key_materials(self) -> dict[str, str]:
        materials = self._secrets().setdefault("server_node_keys", {})
        if not isinstance(materials, dict):
            self._secrets()["server_node_keys"] = {}
            materials = self._secrets()["server_node_keys"]
        return materials

    def _server_enrollment_private_key_materials(self) -> dict[str, str]:
        materials = self._secrets().setdefault("server_enrollment_private_keys", {})
        if not isinstance(materials, dict):
            self._secrets()["server_enrollment_private_keys"] = {}
            materials = self._secrets()["server_enrollment_private_keys"]
        return materials

    def _profile_key_materials(self) -> dict[str, str]:
        materials = self._secrets().setdefault("profile_keys", {})
        if not isinstance(materials, dict):
            self._secrets()["profile_keys"] = {}
            materials = self._secrets()["profile_keys"]
        return materials

    def _wrapped_profile_key_materials(self) -> dict[str, str]:
        materials = self._secrets().setdefault("wrapped_profile_keys", {})
        if not isinstance(materials, dict):
            self._secrets()["wrapped_profile_keys"] = {}
            materials = self._secrets()["wrapped_profile_keys"]
        return materials

    def get_server_node_context(self) -> ServerNodeKeyContext | None:
        raw = self._metadata().get("server_node")
        if not isinstance(raw, dict):
            return None
        context = ServerNodeKeyContext.from_dict(raw)
        if not context.node_id or not context.node_key_id:
            return None
        return context

    async def ensure_server_node_context(self) -> ServerNodeKeyContext:
        existing = self.get_server_node_context()
        materials = self._server_node_key_materials()
        if existing is not None and existing.node_key_id in materials:
            return existing

        now = datetime.now(UTC)
        context = ServerNodeKeyContext(
            node_id=(
                existing.node_id
                if existing is not None and existing.node_id
                else f"node-ha-{uuid4()}"
            ),
            node_key_id=f"node-key-{uuid4()}",
            key_version=1,
            algorithm=NODE_KEY_ALGORITHM,
            protection_class=LOCAL_KEY_PROTECTION_CLASS,
            created_at=now,
            updated_at=now,
        )
        self._metadata()["server_node"] = context.to_dict()
        materials[context.node_key_id] = _random_base64url(32)
        await self._store_manager.async_save()
        return context

    def get_server_enrollment_context(self) -> NodeEnrollmentContext | None:
        raw = self._metadata().get("server_enrollment")
        if not isinstance(raw, dict):
            return None
        context = NodeEnrollmentContext.from_dict(raw)
        if not context.node_id or not context.recipient_key_id or not context.public_key_b64:
            return None
        return context

    async def ensure_server_enrollment_context(self) -> NodeEnrollmentContext:
        server_node = await self.ensure_server_node_context()
        existing = self.get_server_enrollment_context()
        materials = self._server_enrollment_private_key_materials()
        if (
            existing is not None
            and existing.node_id == server_node.node_id
            and existing.public_key_b64
            and existing.recipient_key_id in materials
        ):
            return existing

        private_key = x25519.X25519PrivateKey.generate()
        public_key_bytes = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        private_key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        now = datetime.now(UTC)
        context = NodeEnrollmentContext(
            node_id=server_node.node_id,
            recipient_key_id=f"node-enroll-{uuid4()}",
            key_version=1,
            algorithm=NODE_ENROLLMENT_ALGORITHM,
            public_key_b64=_randomless_base64url(public_key_bytes),
            created_at=now,
            updated_at=now,
        )
        self._metadata()["server_enrollment"] = context.to_dict()
        materials[context.recipient_key_id] = _randomless_base64url(private_key_bytes)
        await self._store_manager.async_save()
        return context

    def get_server_enrollment_descriptor(self) -> NodeEnrollmentDescriptor | None:
        context = self.get_server_enrollment_context()
        return context.to_descriptor() if context is not None else None

    def get_profile_key_context(self, profile_id: str) -> ProfileKeyContext | None:
        normalized_profile_id = str(profile_id).strip()
        if not normalized_profile_id:
            return None
        raw = self._profile_keys().get(normalized_profile_id)
        if not isinstance(raw, dict):
            return None
        return ProfileKeyContext.from_dict(raw)

    async def ensure_profile_key_context(self, profile_id: str) -> ProfileKeyContext:
        normalized_profile_id = str(profile_id).strip()
        if not normalized_profile_id:
            raise ValueError("profile_id must not be empty.")

        server_node = await self.ensure_server_node_context()
        server_node_key_material = self.get_server_node_key_material(server_node.node_key_id)
        if not server_node_key_material:
            raise ValueError("Server node key material is missing.")
        materials = self._profile_key_materials()
        wrapped_materials = self._wrapped_profile_key_materials()
        existing = self.get_profile_key_context(normalized_profile_id)
        now = datetime.now(UTC)
        created_new_context = False

        if existing is not None and (
            existing.profile_key_id in materials
            or self._find_node_envelope(
                profile_key_id=existing.profile_key_id,
                recipient_id=server_node.node_key_id,
                material_state=ENVELOPE_MATERIAL_STATE_LOCAL_DIRECT,
            )
            is not None
        ):
            context = existing
        else:
            context = ProfileKeyContext(
                profile_id=normalized_profile_id,
                profile_key_id=f"profile-key-{uuid4()}",
                key_version=1,
                algorithm=PROFILE_KEY_ALGORITHM,
                created_at=now,
                updated_at=now,
            )
            self._profile_keys()[normalized_profile_id] = context.to_dict()
            created_new_context = True
            envelope_id = f"env-{uuid4()}"
            wrapped_material_id = envelope_id
            wrapped_materials[wrapped_material_id] = json.dumps(
                _wrap_key_material(
                    profile_key_bytes=token_bytes(32),
                    wrapping_key_bytes=_decode_b64(server_node_key_material),
                    aad_context={
                        "kind": "profile_key_local_direct_access",
                        "node_id": server_node.node_id,
                        "node_key_id": server_node.node_key_id,
                        "profile_key_id": context.profile_key_id,
                        "profile_key_version": context.key_version,
                    },
                ).to_dict()
            )
            self._envelopes()[envelope_id] = WrappedProfileKeyEnvelope(
                envelope_id=envelope_id,
                profile_key_id=context.profile_key_id,
                profile_key_version=context.key_version,
                recipient_kind=ENVELOPE_RECIPIENT_NODE,
                recipient_id=server_node.node_key_id,
                wrap_mechanism=ENVELOPE_WRAP_MECHANISM_LOCAL_DIRECT,
                material_state=ENVELOPE_MATERIAL_STATE_LOCAL_DIRECT,
                wrapped_key_material_id=wrapped_material_id,
                wrapped_key_material=None,
                metadata={
                    "node_id": server_node.node_id,
                    "node_key_id": server_node.node_key_id,
                    "access_scope": "current_home_assistant_installation",
                },
                created_at=now,
                updated_at=now,
            ).to_dict()

        if not created_new_context:
            envelope = self._find_node_envelope(
                profile_key_id=context.profile_key_id,
                recipient_id=server_node.node_key_id,
                material_state=ENVELOPE_MATERIAL_STATE_LOCAL_DIRECT,
            )
            if envelope is None:
                envelope = WrappedProfileKeyEnvelope(
                    envelope_id=f"env-{uuid4()}",
                    profile_key_id=context.profile_key_id,
                    profile_key_version=context.key_version,
                    recipient_kind=ENVELOPE_RECIPIENT_NODE,
                    recipient_id=server_node.node_key_id,
                    wrap_mechanism=ENVELOPE_WRAP_MECHANISM_LOCAL_DIRECT,
                    material_state=ENVELOPE_MATERIAL_STATE_LOCAL_DIRECT,
                    wrapped_key_material_id=None,
                    wrapped_key_material=None,
                    metadata={
                        "node_id": server_node.node_id,
                        "node_key_id": server_node.node_key_id,
                        "access_scope": "current_home_assistant_installation",
                    },
                    created_at=now,
                    updated_at=now,
                )
                self._envelopes()[envelope.envelope_id] = envelope.to_dict()

        await self._store_manager.async_save()
        return context

    def get_server_node_key_material(self, node_key_id: str) -> str | None:
        normalized_node_key_id = str(node_key_id).strip()
        if not normalized_node_key_id:
            return None
        return self._server_node_key_materials().get(normalized_node_key_id)

    def get_server_enrollment_private_key_material(
        self,
        recipient_key_id: str,
    ) -> str | None:
        normalized_recipient_key_id = str(recipient_key_id).strip()
        if not normalized_recipient_key_id:
            return None
        return self._server_enrollment_private_key_materials().get(
            normalized_recipient_key_id
        )

    def get_profile_key_material(self, profile_key_id: str) -> str | None:
        normalized_profile_key_id = str(profile_key_id).strip()
        if not normalized_profile_key_id:
            return None
        return self._profile_key_materials().get(normalized_profile_key_id)

    def get_wrapped_key_material(self, wrapped_key_material_id: str) -> str | None:
        normalized_material_id = str(wrapped_key_material_id).strip()
        if not normalized_material_id:
            return None
        return self._wrapped_profile_key_materials().get(normalized_material_id)

    async def set_wrapped_key_material(
        self,
        wrapped_key_material_id: str,
        wrapped_key_material: str,
    ) -> None:
        normalized_material_id = str(wrapped_key_material_id).strip()
        if not normalized_material_id:
            raise ValueError("wrapped_key_material_id must not be empty.")
        self._wrapped_profile_key_materials()[normalized_material_id] = wrapped_key_material
        await self._store_manager.async_save()

    async def remove_wrapped_key_material(self, wrapped_key_material_id: str) -> None:
        normalized_material_id = str(wrapped_key_material_id).strip()
        if not normalized_material_id:
            return
        materials = self._wrapped_profile_key_materials()
        if normalized_material_id not in materials:
            return
        del materials[normalized_material_id]
        await self._store_manager.async_save()

    async def remove_profile_key_material(self, profile_key_id: str) -> None:
        normalized_profile_key_id = str(profile_key_id).strip()
        if not normalized_profile_key_id:
            return
        materials = self._profile_key_materials()
        if normalized_profile_key_id not in materials:
            return
        del materials[normalized_profile_key_id]
        await self._store_manager.async_save()

    def find_local_direct_envelope(
        self,
        *,
        profile_key_id: str,
        node_key_id: str,
    ) -> WrappedProfileKeyEnvelope | None:
        return self._find_node_envelope(
            profile_key_id=profile_key_id,
            recipient_id=node_key_id,
            material_state=ENVELOPE_MATERIAL_STATE_LOCAL_DIRECT,
        )

    async def upsert_envelope(self, envelope: WrappedProfileKeyEnvelope) -> None:
        self._envelopes()[envelope.envelope_id] = envelope.to_dict()
        await self._store_manager.async_save()

    def get_recovery_key_metadata(self, recovery_id: str) -> RecoveryKeyMetadata | None:
        normalized_recovery_id = str(recovery_id).strip()
        if not normalized_recovery_id:
            return None
        raw = self._recovery_keys().get(normalized_recovery_id)
        if not isinstance(raw, dict):
            return None
        return RecoveryKeyMetadata.from_dict(raw)

    async def upsert_recovery_key_metadata(
        self,
        recovery_key: RecoveryKeyMetadata,
    ) -> None:
        self._recovery_keys()[recovery_key.recovery_id] = recovery_key.to_dict()
        await self._store_manager.async_save()

    def get_join_request(
        self,
        request_id: str,
        *,
        now: datetime | None = None,
    ) -> JoinEnrollmentRequest | None:
        normalized_request_id = str(request_id).strip()
        if not normalized_request_id:
            return None
        raw = self._join_requests().get(normalized_request_id)
        if not isinstance(raw, dict):
            return None
        request = JoinEnrollmentRequest.from_dict(raw)
        return self._with_effective_join_status(request, now=now)

    def list_join_requests(
        self,
        *,
        profile_id: str | None = None,
        now: datetime | None = None,
    ) -> tuple[JoinEnrollmentRequest, ...]:
        normalized_profile_id = str(profile_id or "").strip() or None
        requests: list[JoinEnrollmentRequest] = []
        for raw in self._join_requests().values():
            if not isinstance(raw, dict):
                continue
            request = self._with_effective_join_status(
                JoinEnrollmentRequest.from_dict(raw),
                now=now,
            )
            if normalized_profile_id is not None and request.profile_id != normalized_profile_id:
                continue
            requests.append(request)
        requests.sort(
            key=lambda entry: (
                _join_request_status_rank(entry.status),
                -entry.requested_at.timestamp(),
            )
        )
        return tuple(requests)

    async def create_join_request(
        self,
        request: JoinEnrollmentRequest,
    ) -> JoinEnrollmentRequest:
        if not request.request_id:
            raise ValueError("request_id must not be empty.")
        if self.get_join_request(request.request_id) is not None:
            raise ValueError("join request already exists.")
        self._join_requests()[request.request_id] = request.to_dict()
        await self._store_manager.async_save()
        return request

    async def upsert_join_request(
        self,
        request: JoinEnrollmentRequest,
    ) -> JoinEnrollmentRequest:
        if not request.request_id:
            raise ValueError("request_id must not be empty.")
        self._join_requests()[request.request_id] = request.to_dict()
        await self._store_manager.async_save()
        return request

    async def expire_join_request(
        self,
        request_id: str,
        *,
        now: datetime | None = None,
    ) -> JoinEnrollmentRequest | None:
        request = self.get_join_request(request_id, now=now)
        if request is None:
            return None
        if request.status in (
            JOIN_REQUEST_STATUS_COMPLETED,
            JOIN_REQUEST_STATUS_INVALIDATED,
            JOIN_REQUEST_STATUS_EXPIRED,
        ):
            return request
        effective_now = now or datetime.now(UTC)
        if request.expires_at > effective_now:
            return request
        expired = JoinEnrollmentRequest(
            request_id=request.request_id,
            profile_id=request.profile_id,
            requesting_node_id=request.requesting_node_id,
            recipient=request.recipient,
            requested_at=request.requested_at,
            expires_at=request.expires_at,
            status=JOIN_REQUEST_STATUS_EXPIRED,
            approval_id=request.approval_id,
            approval_envelope_id=request.approval_envelope_id,
            approved_by_node_id=request.approved_by_node_id,
            approved_by_node_key_id=request.approved_by_node_key_id,
            approved_at=request.approved_at,
            completed_at=request.completed_at,
            invalidated_at=effective_now,
            invalidation_reason=request.invalidation_reason or "expired",
        )
        return await self.upsert_join_request(expired)

    async def prepare_authorized_node_envelope(
        self,
        *,
        profile_id: str,
        recipient_node_id: str,
        recipient_node_key_id: str,
    ) -> WrappedProfileKeyEnvelope:
        context = await self.ensure_profile_key_context(profile_id)
        server_node = await self.ensure_server_node_context()
        existing = self._find_node_envelope(
            profile_key_id=context.profile_key_id,
            recipient_id=recipient_node_key_id,
            material_state=None,
        )
        if existing is not None:
            return existing

        now = datetime.now(UTC)
        envelope = WrappedProfileKeyEnvelope(
            envelope_id=f"env-{uuid4()}",
            profile_key_id=context.profile_key_id,
            profile_key_version=context.key_version,
            recipient_kind=ENVELOPE_RECIPIENT_NODE,
            recipient_id=str(recipient_node_key_id).strip(),
            wrap_mechanism=ENVELOPE_WRAP_MECHANISM_NODE_PREPARED,
            material_state=ENVELOPE_MATERIAL_STATE_PENDING_WRAP,
            wrapped_key_material_id=None,
            wrapped_key_material=None,
            metadata={
                "recipient_node_id": str(recipient_node_id).strip(),
                "recipient_node_key_id": str(recipient_node_key_id).strip(),
                "authorized_by_node_id": server_node.node_id,
                "authorized_by_node_key_id": server_node.node_key_id,
            },
            created_at=now,
            updated_at=now,
        )
        self._envelopes()[envelope.envelope_id] = envelope.to_dict()
        await self._store_manager.async_save()
        return envelope

    async def prepare_recovery_passphrase_envelope(
        self,
        *,
        profile_id: str,
        iterations: int = 210000,
    ) -> tuple[WrappedProfileKeyEnvelope, RecoveryKeyMetadata]:
        context = await self.ensure_profile_key_context(profile_id)
        now = datetime.now(UTC)
        recovery_key = RecoveryKeyMetadata(
            recovery_id=f"recovery-{uuid4()}",
            kind=RECOVERY_METHOD_PASSPHRASE,
            kdf_algorithm=RECOVERY_KDF_PBKDF2_SHA256,
            iterations=iterations,
            salt_b64=_random_base64url(16),
            created_at=now,
            updated_at=now,
        )
        envelope = WrappedProfileKeyEnvelope(
            envelope_id=f"env-{uuid4()}",
            profile_key_id=context.profile_key_id,
            profile_key_version=context.key_version,
            recipient_kind=ENVELOPE_RECIPIENT_RECOVERY,
            recipient_id=recovery_key.recovery_id,
            wrap_mechanism=ENVELOPE_WRAP_MECHANISM_RECOVERY_PREPARED,
            material_state=ENVELOPE_MATERIAL_STATE_PENDING_WRAP,
            wrapped_key_material_id=None,
            wrapped_key_material=None,
            metadata={
                "recovery_id": recovery_key.recovery_id,
                "recovery_kind": recovery_key.kind,
                "kdf_algorithm": recovery_key.kdf_algorithm,
                "iterations": recovery_key.iterations,
                "salt_b64": recovery_key.salt_b64,
            },
            created_at=now,
            updated_at=now,
        )
        self._recovery_keys()[recovery_key.recovery_id] = recovery_key.to_dict()
        self._envelopes()[envelope.envelope_id] = envelope.to_dict()
        await self._store_manager.async_save()
        return envelope, recovery_key

    def list_envelopes(self) -> tuple[WrappedProfileKeyEnvelope, ...]:
        return tuple(
            WrappedProfileKeyEnvelope.from_dict(data)
            for data in self._envelopes().values()
            if isinstance(data, dict)
        )

    def audit_key_hierarchy(
        self,
        *,
        now: datetime | None = None,
    ) -> KeyHierarchyAuditReport:
        effective_now = now or datetime.now(UTC)
        server_node = self.get_server_node_context()
        profile_keys = tuple(
            ProfileKeyContext.from_dict(data)
            for data in self._profile_keys().values()
            if isinstance(data, dict)
        )
        envelopes = self.list_envelopes()
        recovery_keys = tuple(
            RecoveryKeyMetadata.from_dict(data)
            for data in self._recovery_keys().values()
            if isinstance(data, dict)
        )
        join_requests = tuple(
            self._with_effective_join_status(
                JoinEnrollmentRequest.from_dict(data),
                now=effective_now,
            )
            for data in self._join_requests().values()
            if isinstance(data, dict)
        )
        raw_profile_key_materials = dict(self._profile_key_materials())
        wrapped_profile_key_materials = dict(self._wrapped_profile_key_materials())
        findings: list[KeyHierarchyAuditFinding] = []
        referenced_wrapped_material_ids: set[str] = set()

        def add_finding(
            *,
            severity: str,
            kind: str,
            code: str,
            description: str,
            profile_key_id: str | None = None,
            envelope_id: str | None = None,
            recovery_id: str | None = None,
            request_id: str | None = None,
            wrapped_key_material_id: str | None = None,
            details: dict[str, object] | None = None,
        ) -> None:
            findings.append(
                KeyHierarchyAuditFinding(
                    severity=severity,
                    kind=kind,
                    code=code,
                    description=description,
                    profile_key_id=profile_key_id,
                    envelope_id=envelope_id,
                    recovery_id=recovery_id,
                    request_id=request_id,
                    wrapped_key_material_id=wrapped_key_material_id,
                    details=dict(details or {}),
                )
            )

        def envelope_has_material(envelope: WrappedProfileKeyEnvelope) -> bool:
            return _lookup_wrapped_material_json(
                wrapped_materials=wrapped_profile_key_materials,
                envelope=envelope,
            ) is not None

        recovery_envelopes_by_id: dict[str, list[WrappedProfileKeyEnvelope]] = {}

        for envelope in envelopes:
            material_json = _lookup_wrapped_material_json(
                wrapped_materials=wrapped_profile_key_materials,
                envelope=envelope,
            )
            material_present = material_json is not None
            if envelope.wrapped_key_material_id:
                referenced_wrapped_material_ids.add(envelope.wrapped_key_material_id)
                if envelope.wrapped_key_material_id not in wrapped_profile_key_materials:
                    add_finding(
                        severity=AUDIT_SEVERITY_ERROR,
                        kind="missing_reference",
                        code="envelope_missing_wrapped_material",
                        description=(
                            "Envelope verweist auf wrapped_key_material_id, "
                            "aber das Material fehlt."
                        ),
                        profile_key_id=envelope.profile_key_id,
                        envelope_id=envelope.envelope_id,
                        wrapped_key_material_id=envelope.wrapped_key_material_id,
                    )

            if envelope.material_state == ENVELOPE_MATERIAL_STATE_PENDING_WRAP:
                if material_present:
                    add_finding(
                        severity=AUDIT_SEVERITY_WARNING,
                        kind="state_mismatch",
                        code="pending_envelope_has_material",
                        description=(
                            "Envelope ist noch pending_wrap, hat aber bereits "
                            "Wrapped Material."
                        ),
                        profile_key_id=envelope.profile_key_id,
                        envelope_id=envelope.envelope_id,
                        wrapped_key_material_id=envelope.wrapped_key_material_id,
                    )
            elif not material_present:
                has_legacy_raw_profile_key = (
                    envelope.material_state == ENVELOPE_MATERIAL_STATE_LOCAL_DIRECT
                    and envelope.profile_key_id in raw_profile_key_materials
                )
                if has_legacy_raw_profile_key:
                    add_finding(
                        severity=AUDIT_SEVERITY_WARNING,
                        kind="legacy_material",
                        code="legacy_local_direct_envelope_requires_migration",
                        description=(
                            "Lokaler Direct-Access-Envelope hat noch kein "
                            "Wrapped Material und verlaesst sich auf Legacy-Raw-Material."
                        ),
                        profile_key_id=envelope.profile_key_id,
                        envelope_id=envelope.envelope_id,
                    )
                else:
                    add_finding(
                        severity=AUDIT_SEVERITY_ERROR,
                        kind="state_mismatch",
                        code="envelope_material_state_without_material",
                        description=(
                            "Envelope-Zustand erwartet Material, aber es ist "
                            "kein Wrapped Material vorhanden."
                        ),
                        profile_key_id=envelope.profile_key_id,
                        envelope_id=envelope.envelope_id,
                        wrapped_key_material_id=envelope.wrapped_key_material_id,
                        details={"material_state": envelope.material_state},
                    )

            if (
                server_node is not None
                and envelope.material_state == ENVELOPE_MATERIAL_STATE_LOCAL_DIRECT
            ):
                metadata_node_id = str(envelope.metadata.get("node_id") or "").strip()
                metadata_node_key_id = str(
                    envelope.metadata.get("node_key_id") or ""
                ).strip()
                if (
                    envelope.recipient_kind != ENVELOPE_RECIPIENT_NODE
                    or envelope.recipient_id != server_node.node_key_id
                    or metadata_node_id != server_node.node_id
                    or metadata_node_key_id != server_node.node_key_id
                ):
                    add_finding(
                        severity=AUDIT_SEVERITY_ERROR,
                        kind="recipient_mismatch",
                        code="local_direct_envelope_recipient_mismatch",
                        description=(
                            "Lokaler Direct-Access-Envelope passt nicht sauber "
                            "zum aktuellen Server-Node-Key."
                        ),
                        profile_key_id=envelope.profile_key_id,
                        envelope_id=envelope.envelope_id,
                        details={
                            "recipient_kind": envelope.recipient_kind,
                            "recipient_id": envelope.recipient_id,
                            "metadata_node_id": metadata_node_id,
                            "metadata_node_key_id": metadata_node_key_id,
                            "expected_node_id": server_node.node_id,
                            "expected_node_key_id": server_node.node_key_id,
                        },
                    )

            if envelope.recipient_kind == ENVELOPE_RECIPIENT_RECOVERY:
                recovery_envelopes_by_id.setdefault(envelope.recipient_id, []).append(
                    envelope
                )
                if (
                    envelope.material_state != ENVELOPE_MATERIAL_STATE_PENDING_WRAP
                    and not material_present
                ):
                    add_finding(
                        severity=AUDIT_SEVERITY_ERROR,
                        kind="missing_reference",
                        code="recovery_envelope_missing_wrapped_material",
                        description=(
                            "Recovery-Envelope erwartet Wrapped Material, aber "
                            "es fehlt."
                        ),
                        profile_key_id=envelope.profile_key_id,
                        envelope_id=envelope.envelope_id,
                        recovery_id=envelope.recipient_id,
                        wrapped_key_material_id=envelope.wrapped_key_material_id,
                    )

        for wrapped_key_material_id in wrapped_profile_key_materials:
            if wrapped_key_material_id not in referenced_wrapped_material_ids:
                add_finding(
                    severity=AUDIT_SEVERITY_WARNING,
                    kind="orphan_material",
                    code="orphan_wrapped_material",
                    description=(
                        "Wrapped Key Material existiert, aber kein Envelope "
                        "referenziert es."
                    ),
                    wrapped_key_material_id=wrapped_key_material_id,
                )

        for profile_key in profile_keys:
            local_direct_envelopes = [
                envelope
                for envelope in envelopes
                if envelope.profile_key_id == profile_key.profile_key_id
                and envelope.recipient_kind == ENVELOPE_RECIPIENT_NODE
                and envelope.material_state == ENVELOPE_MATERIAL_STATE_LOCAL_DIRECT
            ]
            if not local_direct_envelopes:
                add_finding(
                    severity=AUDIT_SEVERITY_ERROR,
                    kind="missing_reference",
                    code="profile_key_missing_local_direct_envelope",
                    description=(
                        "ProfileKeyContext existiert ohne lokalen "
                        "Direct-Access-Envelope."
                    ),
                    profile_key_id=profile_key.profile_key_id,
                )
            elif server_node is not None and not any(
                envelope.recipient_id == server_node.node_key_id
                for envelope in local_direct_envelopes
            ):
                add_finding(
                    severity=AUDIT_SEVERITY_ERROR,
                    kind="missing_reference",
                    code="profile_key_missing_current_node_local_direct_envelope",
                    description=(
                        "ProfileKeyContext hat keinen lokalen Direct-Access-Envelope "
                        "fuer den aktuellen Server-Node-Key."
                    ),
                    profile_key_id=profile_key.profile_key_id,
                )

            if profile_key.profile_key_id in raw_profile_key_materials and any(
                envelope.profile_key_id == profile_key.profile_key_id
                and envelope_has_material(envelope)
                for envelope in envelopes
            ):
                add_finding(
                    severity=AUDIT_SEVERITY_WARNING,
                    kind="legacy_material",
                    code="raw_profile_key_material_still_present_after_wrap",
                    description=(
                        "Legacy-Raw-Profile-Key-Material existiert noch, obwohl "
                        "fuer denselben Profile-Key schon Wrapped Material vorliegt."
                    ),
                    profile_key_id=profile_key.profile_key_id,
                )

        for recovery_key in recovery_keys:
            if not recovery_envelopes_by_id.get(recovery_key.recovery_id):
                add_finding(
                    severity=AUDIT_SEVERITY_ERROR,
                    kind="missing_reference",
                    code="recovery_key_missing_envelope",
                    description=(
                        "RecoveryKeyMetadata existiert ohne passendes "
                        "Recovery-Envelope."
                    ),
                    recovery_id=recovery_key.recovery_id,
                )

        for join_request in join_requests:
            if join_request.status not in (
                JOIN_REQUEST_STATUS_APPROVED,
                JOIN_REQUEST_STATUS_COMPLETED,
            ):
                continue
            approval_envelope_id = (join_request.approval_envelope_id or "").strip()
            approval_envelope = (
                self.get_envelope(approval_envelope_id)
                if approval_envelope_id
                else None
            )
            if approval_envelope is None:
                add_finding(
                    severity=AUDIT_SEVERITY_ERROR,
                    kind="missing_reference",
                    code="join_request_missing_approval_envelope",
                    description=(
                        "Join-Request ist approved/completed, aber das "
                        "Approval-Envelope fehlt."
                    ),
                    request_id=join_request.request_id,
                    envelope_id=approval_envelope_id or None,
                )

        return KeyHierarchyAuditReport(findings=tuple(findings))

    def get_envelope(self, envelope_id: str) -> WrappedProfileKeyEnvelope | None:
        normalized_envelope_id = str(envelope_id).strip()
        if not normalized_envelope_id:
            return None
        raw = self._envelopes().get(normalized_envelope_id)
        if not isinstance(raw, dict):
            return None
        return WrappedProfileKeyEnvelope.from_dict(raw)

    def _find_node_envelope(
        self,
        *,
        profile_key_id: str,
        recipient_id: str,
        material_state: str | None,
    ) -> WrappedProfileKeyEnvelope | None:
        for data in self._envelopes().values():
            if not isinstance(data, dict):
                continue
            envelope = WrappedProfileKeyEnvelope.from_dict(data)
            if envelope.profile_key_id != profile_key_id:
                continue
            if envelope.recipient_kind != ENVELOPE_RECIPIENT_NODE:
                continue
            if envelope.recipient_id != recipient_id:
                continue
            if material_state is not None and envelope.material_state != material_state:
                continue
            return envelope
        return None

    def _with_effective_join_status(
        self,
        request: JoinEnrollmentRequest,
        *,
        now: datetime | None = None,
    ) -> JoinEnrollmentRequest:
        effective_now = now or datetime.now(UTC)
        if request.status in (
            JOIN_REQUEST_STATUS_COMPLETED,
            JOIN_REQUEST_STATUS_INVALIDATED,
            JOIN_REQUEST_STATUS_EXPIRED,
        ):
            return request
        if request.expires_at <= effective_now:
            return JoinEnrollmentRequest(
                request_id=request.request_id,
                profile_id=request.profile_id,
                requesting_node_id=request.requesting_node_id,
                recipient=request.recipient,
                requested_at=request.requested_at,
                expires_at=request.expires_at,
                status=JOIN_REQUEST_STATUS_EXPIRED,
                approval_id=request.approval_id,
                approval_envelope_id=request.approval_envelope_id,
                approved_by_node_id=request.approved_by_node_id,
                approved_by_node_key_id=request.approved_by_node_key_id,
                approved_at=request.approved_at,
                completed_at=request.completed_at,
                invalidated_at=request.invalidated_at or effective_now,
                invalidation_reason=request.invalidation_reason or "expired",
            )
        return request


def _randomless_base64url(value: bytes) -> str:
    return urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _random_base64url(length: int) -> str:
    return urlsafe_b64encode(token_bytes(length)).decode("ascii").rstrip("=")


def _wrap_key_material(
    *,
    profile_key_bytes: bytes,
    wrapping_key_bytes: bytes,
    aad_context: dict[str, object],
) -> WrappedKeyMaterialBlob:
    canonical_aad = _canonicalize_json(aad_context)
    nonce = token_bytes(12)
    secret_box = AESGCM(wrapping_key_bytes).encrypt(
        nonce=nonce,
        data=profile_key_bytes,
        associated_data=_aad_bytes(canonical_aad),
    )
    return WrappedKeyMaterialBlob(
        format_version=LOCAL_WRAPPED_KEY_FORMAT_VERSION,
        algorithm=LOCAL_PAYLOAD_AEAD_ALGORITHM,
        nonce_b64=_encode_b64(nonce),
        cipher_text_b64=_encode_b64(secret_box[:-16]),
        mac_b64=_encode_b64(secret_box[-16:]),
        aad_context=canonical_aad,
    )


def _canonicalize_json(value: dict[str, object]) -> dict[str, object]:
    return {key: _canonicalize_value(value[key]) for key in sorted(value.keys())}


def _canonicalize_value(value: object) -> object:
    if isinstance(value, dict):
        return _canonicalize_json(dict(value))
    if isinstance(value, list):
        return [_canonicalize_value(item) for item in value]
    return value


def _aad_bytes(aad_context: dict[str, object]) -> bytes:
    return json.dumps(
        _canonicalize_json(aad_context),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _encode_b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _decode_b64(value: str) -> bytes:
    normalized = value.strip().replace("-", "+").replace("_", "/")
    padding = "=" * (-len(normalized) % 4)
    return base64.b64decode(f"{normalized}{padding}")


def _join_request_status_rank(status: str) -> int:
    if status == JOIN_REQUEST_STATUS_APPROVED:
        return 0
    if status == JOIN_REQUEST_STATUS_PENDING:
        return 1
    if status == JOIN_REQUEST_STATUS_EXPIRED:
        return 2
    if status == JOIN_REQUEST_STATUS_INVALIDATED:
        return 3
    if status == JOIN_REQUEST_STATUS_COMPLETED:
        return 4
    return 5


def _lookup_wrapped_material_json(
    *,
    wrapped_materials: dict[str, str],
    envelope: WrappedProfileKeyEnvelope,
) -> str | None:
    wrapped_material_id = (envelope.wrapped_key_material_id or "").strip()
    if wrapped_material_id:
        referenced = wrapped_materials.get(wrapped_material_id)
        if referenced and referenced.strip():
            return referenced
    inline_material = (envelope.wrapped_key_material or "").strip()
    return inline_material or None
