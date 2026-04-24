"""Local AES-GCM encryption and key rewrap helpers for Home Assistant."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from ...domains.security.models.key_hierarchy import (
    ENVELOPE_MATERIAL_STATE_LOCAL_DIRECT,
    ENVELOPE_MATERIAL_STATE_WRAPPED,
    ENVELOPE_RECIPIENT_NODE,
    ENVELOPE_RECIPIENT_RECOVERY,
    ENVELOPE_WRAP_MECHANISM_LOCAL_DIRECT,
    ENVELOPE_WRAP_MECHANISM_NODE_WRAPPED,
    ENVELOPE_WRAP_MECHANISM_RECOVERY_KEY_WRAPPED,
    ENVELOPE_WRAP_MECHANISM_RECOVERY_PASSPHRASE_WRAPPED,
    LOCAL_PAYLOAD_AEAD_ALGORITHM,
    LOCAL_PAYLOAD_FORMAT_VERSION,
    LOCAL_WRAPPED_KEY_FORMAT_VERSION,
    RECOVERY_KDF_NONE,
    RECOVERY_KDF_PBKDF2_SHA256,
    RECOVERY_METHOD_DIRECT_KEY,
    RECOVERY_METHOD_PASSPHRASE,
    EncryptedPayloadEnvelope,
    ProfileKeyContext,
    RecoveryKeyMetadata,
    WrappedKeyMaterialBlob,
    WrappedProfileKeyEnvelope,
)
from ..repositories.ha_key_hierarchy_repository import HomeAssistantKeyHierarchyRepository


class HomeAssistantLocalCryptoService:
    """Resolve local profile keys, encrypt payloads, and rewrap profile keys."""

    def __init__(
        self,
        key_hierarchy_repository: HomeAssistantKeyHierarchyRepository,
    ) -> None:
        self._key_hierarchy_repository = key_hierarchy_repository

    async def encrypt_profile_payload(
        self,
        *,
        profile_id: str,
        data_class_id: str,
        payload: dict[str, Any],
        aad_context: dict[str, Any],
    ) -> EncryptedPayloadEnvelope:
        context, profile_key_bytes = await self._resolve_profile_key(profile_id)
        canonical_aad = _canonicalize_json(aad_context)
        cleartext = json.dumps(
            _canonicalize_json(payload),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        nonce = os.urandom(12)
        secret_box = AESGCM(profile_key_bytes).encrypt(
            nonce=nonce,
            data=cleartext,
            associated_data=_aad_bytes(canonical_aad),
        )
        return EncryptedPayloadEnvelope(
            format_version=LOCAL_PAYLOAD_FORMAT_VERSION,
            algorithm=LOCAL_PAYLOAD_AEAD_ALGORITHM,
            data_class_id=data_class_id,
            profile_key_id=context.profile_key_id,
            profile_key_version=context.key_version,
            nonce_b64=_encode_b64(nonce),
            cipher_text_b64=_encode_b64(secret_box[:-16]),
            mac_b64=_encode_b64(secret_box[-16:]),
            aad_context=canonical_aad,
        )

    async def decrypt_profile_payload(
        self,
        *,
        profile_id: str,
        envelope: EncryptedPayloadEnvelope,
        expected_aad_context: dict[str, Any],
    ) -> dict[str, Any]:
        context, profile_key_bytes = await self._resolve_profile_key(profile_id)
        return _decrypt_payload(
            context=context,
            profile_key_bytes=profile_key_bytes,
            envelope=envelope,
            expected_aad_context=expected_aad_context,
        )

    def decrypt_profile_payload_sync(
        self,
        *,
        profile_id: str,
        envelope: EncryptedPayloadEnvelope,
        expected_aad_context: dict[str, Any],
    ) -> dict[str, Any]:
        context, profile_key_bytes = self._resolve_existing_profile_key(profile_id)
        return _decrypt_payload(
            context=context,
            profile_key_bytes=profile_key_bytes,
            envelope=envelope,
            expected_aad_context=expected_aad_context,
        )

    async def wrap_profile_key_for_authorized_node(
        self,
        *,
        profile_id: str,
        recipient_node_id: str,
        recipient_node_key_id: str,
        recipient_node_key_material: str,
    ) -> WrappedProfileKeyEnvelope:
        context, profile_key_bytes = await self._resolve_profile_key(profile_id)
        server_node = await self._key_hierarchy_repository.ensure_server_node_context()
        existing = next(
            (
                entry
                for entry in self._key_hierarchy_repository.list_envelopes()
                if entry.profile_key_id == context.profile_key_id
                and entry.recipient_kind == ENVELOPE_RECIPIENT_NODE
                and entry.recipient_id == recipient_node_key_id.strip()
            ),
            None,
        )
        now = datetime.now(UTC)
        envelope_id = existing.envelope_id if existing is not None else f"env-{uuid4()}"
        wrapped_material_id = (
            existing.wrapped_key_material_id
            if existing is not None and existing.wrapped_key_material_id
            else envelope_id
        )
        blob = _wrap_key_material(
            profile_key_bytes=profile_key_bytes,
            wrapping_key_bytes=_decode_b64(recipient_node_key_material),
            aad_context={
                "kind": "profile_key_authorized_node_wrap",
                "profile_key_id": context.profile_key_id,
                "profile_key_version": context.key_version,
                "recipient_node_id": recipient_node_id.strip(),
                "recipient_node_key_id": recipient_node_key_id.strip(),
                "authorized_by_node_id": server_node.node_id,
                "authorized_by_node_key_id": server_node.node_key_id,
            },
        )
        await self._key_hierarchy_repository.set_wrapped_key_material(
            wrapped_material_id,
            json.dumps(blob.to_dict()),
        )
        envelope = replace(
            existing,
            wrap_mechanism=ENVELOPE_WRAP_MECHANISM_NODE_WRAPPED,
            material_state=ENVELOPE_MATERIAL_STATE_WRAPPED,
            wrapped_key_material_id=wrapped_material_id,
            wrapped_key_material=None,
            metadata={
                **(existing.metadata if existing is not None else {}),
                "recipient_node_id": recipient_node_id.strip(),
                "recipient_node_key_id": recipient_node_key_id.strip(),
                "authorized_by_node_id": server_node.node_id,
                "authorized_by_node_key_id": server_node.node_key_id,
            },
            updated_at=now,
        ) if existing is not None else WrappedProfileKeyEnvelope(
            envelope_id=envelope_id,
            profile_key_id=context.profile_key_id,
            profile_key_version=context.key_version,
            recipient_kind=ENVELOPE_RECIPIENT_NODE,
            recipient_id=recipient_node_key_id.strip(),
            wrap_mechanism=ENVELOPE_WRAP_MECHANISM_NODE_WRAPPED,
            material_state=ENVELOPE_MATERIAL_STATE_WRAPPED,
            wrapped_key_material_id=wrapped_material_id,
            wrapped_key_material=None,
            metadata={
                "recipient_node_id": recipient_node_id.strip(),
                "recipient_node_key_id": recipient_node_key_id.strip(),
                "authorized_by_node_id": server_node.node_id,
                "authorized_by_node_key_id": server_node.node_key_id,
            },
            created_at=now,
            updated_at=now,
        )
        await self._key_hierarchy_repository.upsert_envelope(envelope)
        return envelope

    async def wrap_profile_key_for_recovery_passphrase(
        self,
        *,
        profile_id: str,
        passphrase: str,
        iterations: int = 210000,
        recovery_id: str | None = None,
    ) -> tuple[WrappedProfileKeyEnvelope, RecoveryKeyMetadata]:
        context, profile_key_bytes = await self._resolve_profile_key(profile_id)
        now = datetime.now(UTC)
        normalized_recovery_id = (recovery_id or "").strip() or None
        existing_recovery = (
            self._key_hierarchy_repository.get_recovery_key_metadata(
                normalized_recovery_id
            )
            if normalized_recovery_id is not None
            else None
        )
        recovery_key = (
            replace(
                existing_recovery,
                kind=RECOVERY_METHOD_PASSPHRASE,
                kdf_algorithm=RECOVERY_KDF_PBKDF2_SHA256,
                iterations=(
                    existing_recovery.iterations
                    if existing_recovery.iterations > 0
                    else iterations
                ),
                salt_b64=(
                    existing_recovery.salt_b64
                    if existing_recovery.salt_b64
                    else _encode_b64(os.urandom(16))
                ),
                updated_at=now,
            )
            if existing_recovery is not None
            else RecoveryKeyMetadata(
                recovery_id=normalized_recovery_id or f"recovery-{uuid4()}",
                kind=RECOVERY_METHOD_PASSPHRASE,
                kdf_algorithm=RECOVERY_KDF_PBKDF2_SHA256,
                iterations=iterations,
                salt_b64=_encode_b64(os.urandom(16)),
                created_at=now,
                updated_at=now,
            )
        )
        derived_key = _derive_passphrase_key(
            passphrase=passphrase,
            salt_b64=recovery_key.salt_b64,
            iterations=recovery_key.iterations,
        )
        existing = next(
            (
                entry
                for entry in self._key_hierarchy_repository.list_envelopes()
                if entry.profile_key_id == context.profile_key_id
                and entry.recipient_kind == ENVELOPE_RECIPIENT_RECOVERY
                and entry.recipient_id == recovery_key.recovery_id
            ),
            None,
        )
        envelope_id = existing.envelope_id if existing is not None else f"env-{uuid4()}"
        wrapped_material_id = (
            existing.wrapped_key_material_id
            if existing is not None and existing.wrapped_key_material_id
            else envelope_id
        )
        blob = _wrap_key_material(
            profile_key_bytes=profile_key_bytes,
            wrapping_key_bytes=derived_key,
            aad_context={
                "kind": "profile_key_recovery_passphrase_wrap",
                "profile_key_id": context.profile_key_id,
                "profile_key_version": context.key_version,
                "recovery_id": recovery_key.recovery_id,
                "recovery_kind": recovery_key.kind,
                "kdf_algorithm": recovery_key.kdf_algorithm,
                "iterations": recovery_key.iterations,
                "salt_b64": recovery_key.salt_b64,
            },
        )
        await self._key_hierarchy_repository.set_wrapped_key_material(
            wrapped_material_id,
            json.dumps(blob.to_dict()),
        )
        envelope = replace(
            existing,
            wrap_mechanism=ENVELOPE_WRAP_MECHANISM_RECOVERY_PASSPHRASE_WRAPPED,
            material_state=ENVELOPE_MATERIAL_STATE_WRAPPED,
            wrapped_key_material_id=wrapped_material_id,
            wrapped_key_material=None,
            metadata={
                **(existing.metadata if existing is not None else {}),
                "recovery_id": recovery_key.recovery_id,
                "recovery_kind": recovery_key.kind,
                "kdf_algorithm": recovery_key.kdf_algorithm,
                "iterations": recovery_key.iterations,
                "salt_b64": recovery_key.salt_b64,
            },
            updated_at=now,
        ) if existing is not None else WrappedProfileKeyEnvelope(
            envelope_id=envelope_id,
            profile_key_id=context.profile_key_id,
            profile_key_version=context.key_version,
            recipient_kind=ENVELOPE_RECIPIENT_RECOVERY,
            recipient_id=recovery_key.recovery_id,
            wrap_mechanism=ENVELOPE_WRAP_MECHANISM_RECOVERY_PASSPHRASE_WRAPPED,
            material_state=ENVELOPE_MATERIAL_STATE_WRAPPED,
            wrapped_key_material_id=wrapped_material_id,
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
        await self._key_hierarchy_repository.upsert_recovery_key_metadata(recovery_key)
        await self._key_hierarchy_repository.upsert_envelope(envelope)
        return envelope, recovery_key

    async def wrap_profile_key_for_recovery_key(
        self,
        *,
        profile_id: str,
        recovery_key_material: str,
        recovery_id: str | None = None,
    ) -> tuple[WrappedProfileKeyEnvelope, RecoveryKeyMetadata]:
        context, profile_key_bytes = await self._resolve_profile_key(profile_id)
        now = datetime.now(UTC)
        normalized_recovery_id = (recovery_id or "").strip() or None
        existing_recovery = (
            self._key_hierarchy_repository.get_recovery_key_metadata(
                normalized_recovery_id
            )
            if normalized_recovery_id is not None
            else None
        )
        recovery_key = (
            replace(
                existing_recovery,
                kind=RECOVERY_METHOD_DIRECT_KEY,
                kdf_algorithm=RECOVERY_KDF_NONE,
                iterations=0,
                salt_b64="",
                updated_at=now,
            )
            if existing_recovery is not None
            else RecoveryKeyMetadata(
                recovery_id=normalized_recovery_id or f"recovery-{uuid4()}",
                kind=RECOVERY_METHOD_DIRECT_KEY,
                kdf_algorithm=RECOVERY_KDF_NONE,
                iterations=0,
                salt_b64="",
                created_at=now,
                updated_at=now,
            )
        )
        existing = next(
            (
                entry
                for entry in self._key_hierarchy_repository.list_envelopes()
                if entry.profile_key_id == context.profile_key_id
                and entry.recipient_kind == ENVELOPE_RECIPIENT_RECOVERY
                and entry.recipient_id == recovery_key.recovery_id
            ),
            None,
        )
        envelope_id = existing.envelope_id if existing is not None else f"env-{uuid4()}"
        wrapped_material_id = (
            existing.wrapped_key_material_id
            if existing is not None and existing.wrapped_key_material_id
            else envelope_id
        )
        blob = _wrap_key_material(
            profile_key_bytes=profile_key_bytes,
            wrapping_key_bytes=_decode_b64(recovery_key_material),
            aad_context={
                "kind": "profile_key_recovery_key_wrap",
                "profile_key_id": context.profile_key_id,
                "profile_key_version": context.key_version,
                "recovery_id": recovery_key.recovery_id,
                "recovery_kind": recovery_key.kind,
            },
        )
        await self._key_hierarchy_repository.set_wrapped_key_material(
            wrapped_material_id,
            json.dumps(blob.to_dict()),
        )
        envelope = replace(
            existing,
            wrap_mechanism=ENVELOPE_WRAP_MECHANISM_RECOVERY_KEY_WRAPPED,
            material_state=ENVELOPE_MATERIAL_STATE_WRAPPED,
            wrapped_key_material_id=wrapped_material_id,
            wrapped_key_material=None,
            metadata={
                **(existing.metadata if existing is not None else {}),
                "recovery_id": recovery_key.recovery_id,
                "recovery_kind": recovery_key.kind,
                "kdf_algorithm": recovery_key.kdf_algorithm,
                "iterations": recovery_key.iterations,
                "salt_b64": recovery_key.salt_b64,
            },
            updated_at=now,
        ) if existing is not None else WrappedProfileKeyEnvelope(
            envelope_id=envelope_id,
            profile_key_id=context.profile_key_id,
            profile_key_version=context.key_version,
            recipient_kind=ENVELOPE_RECIPIENT_RECOVERY,
            recipient_id=recovery_key.recovery_id,
            wrap_mechanism=ENVELOPE_WRAP_MECHANISM_RECOVERY_KEY_WRAPPED,
            material_state=ENVELOPE_MATERIAL_STATE_WRAPPED,
            wrapped_key_material_id=wrapped_material_id,
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
        await self._key_hierarchy_repository.upsert_recovery_key_metadata(recovery_key)
        await self._key_hierarchy_repository.upsert_envelope(envelope)
        return envelope, recovery_key

    def unwrap_authorized_node_envelope(
        self,
        *,
        envelope: WrappedProfileKeyEnvelope,
        recipient_node_key_material: str,
    ) -> bytes:
        if envelope.recipient_kind != ENVELOPE_RECIPIENT_NODE:
            raise ValueError("Envelope is not a node wrap.")
        wrapped_material_json = _lookup_wrapped_material(
            self._key_hierarchy_repository,
            envelope,
        )
        return _unwrap_key_material(
            wrapped_material_json,
            wrapping_key_bytes=_decode_b64(recipient_node_key_material),
        )

    def unwrap_recovery_key_envelope(
        self,
        *,
        envelope: WrappedProfileKeyEnvelope,
        recovery_key_material: str,
    ) -> bytes:
        if envelope.recipient_kind != ENVELOPE_RECIPIENT_RECOVERY:
            raise ValueError("Envelope is not a recovery wrap.")
        recovery_key = self._key_hierarchy_repository.get_recovery_key_metadata(
            envelope.recipient_id
        )
        if recovery_key is None or recovery_key.kind != RECOVERY_METHOD_DIRECT_KEY:
            raise ValueError("Recovery-key metadata is missing.")
        wrapped_material_json = _lookup_wrapped_material(
            self._key_hierarchy_repository,
            envelope,
        )
        return _unwrap_key_material(
            wrapped_material_json,
            wrapping_key_bytes=_decode_b64(recovery_key_material),
        )

    def unwrap_recovery_passphrase_envelope(
        self,
        *,
        envelope: WrappedProfileKeyEnvelope,
        passphrase: str,
    ) -> bytes:
        if envelope.recipient_kind != ENVELOPE_RECIPIENT_RECOVERY:
            raise ValueError("Envelope is not a recovery wrap.")
        recovery_key = self._key_hierarchy_repository.get_recovery_key_metadata(
            envelope.recipient_id
        )
        if recovery_key is None or recovery_key.kind != RECOVERY_METHOD_PASSPHRASE:
            raise ValueError("Passphrase recovery metadata is missing.")
        derived_key = _derive_passphrase_key(
            passphrase=passphrase,
            salt_b64=recovery_key.salt_b64,
            iterations=recovery_key.iterations,
        )
        wrapped_material_json = _lookup_wrapped_material(
            self._key_hierarchy_repository,
            envelope,
        )
        return _unwrap_key_material(
            wrapped_material_json,
            wrapping_key_bytes=derived_key,
        )

    async def _resolve_profile_key(
        self,
        profile_id: str,
    ) -> tuple[ProfileKeyContext, bytes]:
        server_node = await self._key_hierarchy_repository.ensure_server_node_context()
        context = await self._key_hierarchy_repository.ensure_profile_key_context(
            profile_id
        )
        node_key_material = self._key_hierarchy_repository.get_server_node_key_material(
            server_node.node_key_id
        )
        if node_key_material is None:
            raise ValueError("Server node key material is missing.")

        local_envelope = self._key_hierarchy_repository.find_local_direct_envelope(
            profile_key_id=context.profile_key_id,
            node_key_id=server_node.node_key_id,
        )
        wrapped_material_json = (
            _lookup_wrapped_material(self._key_hierarchy_repository, local_envelope)
            if local_envelope is not None
            else None
        )
        if wrapped_material_json is not None:
            cleartext = _unwrap_key_material(
                wrapped_material_json,
                wrapping_key_bytes=_decode_b64(node_key_material),
            )
            return context, cleartext

        raw_profile_key = self._key_hierarchy_repository.get_profile_key_material(
            context.profile_key_id
        )
        if raw_profile_key is None:
            raise ValueError(
                "Profile key material is missing and no local direct envelope exists."
            )

        raw_profile_key_bytes = _decode_b64(raw_profile_key)
        if local_envelope is None:
            raise ValueError("Local direct-access envelope is missing.")
        wrapped_material_id = (
            local_envelope.wrapped_key_material_id or local_envelope.envelope_id
        )
        wrapped_blob = _wrap_key_material(
            profile_key_bytes=raw_profile_key_bytes,
            wrapping_key_bytes=_decode_b64(node_key_material),
            aad_context={
                "kind": "profile_key_local_direct_access",
                "node_id": server_node.node_id,
                "node_key_id": server_node.node_key_id,
                "profile_key_id": context.profile_key_id,
                "profile_key_version": context.key_version,
            },
        )
        await self._key_hierarchy_repository.set_wrapped_key_material(
            wrapped_material_id,
            json.dumps(wrapped_blob.to_dict()),
        )
        await self._key_hierarchy_repository.upsert_envelope(
            replace(
                local_envelope,
                wrapped_key_material_id=wrapped_material_id,
                wrapped_key_material=None,
                updated_at=datetime.now(UTC),
            )
        )
        await self._key_hierarchy_repository.remove_profile_key_material(
            context.profile_key_id
        )
        return context, raw_profile_key_bytes

    def _resolve_existing_profile_key(
        self,
        profile_id: str,
    ) -> tuple[ProfileKeyContext, bytes]:
        server_node = self._key_hierarchy_repository.get_server_node_context()
        if server_node is None:
            raise ValueError("Server node context is missing.")
        context = self._key_hierarchy_repository.get_profile_key_context(profile_id)
        if context is None:
            raise ValueError("Profile key context is missing.")
        node_key_material = self._key_hierarchy_repository.get_server_node_key_material(
            server_node.node_key_id
        )
        if node_key_material is None:
            raise ValueError("Server node key material is missing.")
        local_envelope = self._key_hierarchy_repository.find_local_direct_envelope(
            profile_key_id=context.profile_key_id,
            node_key_id=server_node.node_key_id,
        )
        if local_envelope is None:
            raise ValueError("Local direct-access envelope is missing.")
        wrapped_material_json = _lookup_wrapped_material(
            self._key_hierarchy_repository,
            local_envelope,
        )
        if wrapped_material_json is None:
            raise ValueError("Wrapped local direct-access key material is missing.")
        cleartext = _unwrap_key_material(
            wrapped_material_json,
            wrapping_key_bytes=_decode_b64(node_key_material),
        )
        return context, cleartext


def _decrypt_payload(
    *,
    context: ProfileKeyContext,
    profile_key_bytes: bytes,
    envelope: EncryptedPayloadEnvelope,
    expected_aad_context: dict[str, Any],
) -> dict[str, Any]:
    if context.profile_key_id != envelope.profile_key_id:
        raise ValueError("Profile key context does not match encrypted payload envelope.")
    expected_aad = _canonicalize_json(expected_aad_context)
    stored_aad = _canonicalize_json(envelope.aad_context)
    if expected_aad != stored_aad:
        raise ValueError("Encrypted payload AAD context mismatch.")
    cleartext = AESGCM(profile_key_bytes).decrypt(
        nonce=_decode_b64(envelope.nonce_b64),
        data=_decode_b64(envelope.cipher_text_b64) + _decode_b64(envelope.mac_b64),
        associated_data=_aad_bytes(stored_aad),
    )
    decoded = json.loads(cleartext.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("Encrypted payload did not decode to a JSON object.")
    return dict(decoded)


def _lookup_wrapped_material(
    repository: HomeAssistantKeyHierarchyRepository,
    envelope: WrappedProfileKeyEnvelope | None,
) -> str | None:
    if envelope is None:
        return None
    material_id = (envelope.wrapped_key_material_id or "").strip()
    if material_id:
        referenced = repository.get_wrapped_key_material(material_id)
        if referenced:
            return referenced
    inline = (envelope.wrapped_key_material or "").strip()
    return inline or None


def _wrap_key_material(
    *,
    profile_key_bytes: bytes,
    wrapping_key_bytes: bytes,
    aad_context: dict[str, Any],
) -> WrappedKeyMaterialBlob:
    canonical_aad = _canonicalize_json(aad_context)
    nonce = os.urandom(12)
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


def _unwrap_key_material(
    wrapped_material_json: str,
    *,
    wrapping_key_bytes: bytes,
) -> bytes:
    blob = WrappedKeyMaterialBlob.from_dict(json.loads(wrapped_material_json))
    return AESGCM(wrapping_key_bytes).decrypt(
        nonce=_decode_b64(blob.nonce_b64),
        data=_decode_b64(blob.cipher_text_b64) + _decode_b64(blob.mac_b64),
        associated_data=_aad_bytes(blob.aad_context),
    )


def _derive_passphrase_key(
    *,
    passphrase: str,
    salt_b64: str,
    iterations: int,
) -> bytes:
    normalized_passphrase = str(passphrase).strip()
    if not normalized_passphrase:
        raise ValueError("passphrase must not be empty.")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_decode_b64(salt_b64),
        iterations=iterations,
    )
    return kdf.derive(normalized_passphrase.encode("utf-8"))


def _canonicalize_json(value: dict[str, Any]) -> dict[str, Any]:
    return {key: _canonicalize_value(value[key]) for key in sorted(value.keys())}


def _canonicalize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return _canonicalize_json(dict(value))
    if isinstance(value, list):
        return [_canonicalize_value(item) for item in value]
    return value


def _aad_bytes(aad_context: dict[str, Any]) -> bytes:
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
