"""Home Assistant backed backup/recovery key hierarchy repository."""

from __future__ import annotations

from base64 import urlsafe_b64encode
from datetime import UTC, datetime
from secrets import token_bytes
from typing import TYPE_CHECKING
from uuid import uuid4

from ...domains.security.models.key_hierarchy import (
    ENVELOPE_MATERIAL_STATE_LOCAL_DIRECT,
    ENVELOPE_MATERIAL_STATE_PENDING_WRAP,
    ENVELOPE_RECIPIENT_NODE,
    ENVELOPE_RECIPIENT_RECOVERY,
    ENVELOPE_WRAP_MECHANISM_LOCAL_DIRECT,
    ENVELOPE_WRAP_MECHANISM_NODE_PREPARED,
    ENVELOPE_WRAP_MECHANISM_RECOVERY_PREPARED,
    LOCAL_KEY_PROTECTION_CLASS,
    NODE_KEY_ALGORITHM,
    PROFILE_KEY_ALGORITHM,
    RECOVERY_KDF_PBKDF2_SHA256,
    RECOVERY_METHOD_PASSPHRASE,
    ProfileKeyContext,
    ProtectedStorageClass,
    RecoveryKeyMetadata,
    ServerNodeKeyContext,
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
        metadata.setdefault("profile_keys", {})
        metadata.setdefault("key_envelopes", {})
        metadata.setdefault("recovery_keys", {})
        return metadata

    def _secrets(self) -> dict[str, object]:
        secrets = self._security().setdefault("secrets", {})
        if not isinstance(secrets, dict):
            self._security()["secrets"] = {}
            secrets = self._security()["secrets"]
        secrets.setdefault("format_version", 1)
        secrets.setdefault("server_node_keys", {})
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

    def _server_node_key_materials(self) -> dict[str, str]:
        materials = self._secrets().setdefault("server_node_keys", {})
        if not isinstance(materials, dict):
            self._secrets()["server_node_keys"] = {}
            materials = self._secrets()["server_node_keys"]
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
        materials = self._profile_key_materials()
        existing = self.get_profile_key_context(normalized_profile_id)
        now = datetime.now(UTC)

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
            materials[context.profile_key_id] = _random_base64url(32)

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


def _random_base64url(length: int) -> str:
    return urlsafe_b64encode(token_bytes(length)).decode("ascii").rstrip("=")
