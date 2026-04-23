"""Local at-rest AES-GCM encryption for pilot data classes."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import replace
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ...domains.security.models.key_hierarchy import (
    ENVELOPE_MATERIAL_STATE_LOCAL_DIRECT,
    ENVELOPE_RECIPIENT_NODE,
    ENVELOPE_WRAP_MECHANISM_LOCAL_DIRECT,
    LOCAL_PAYLOAD_AEAD_ALGORITHM,
    LOCAL_PAYLOAD_FORMAT_VERSION,
    LOCAL_WRAPPED_KEY_FORMAT_VERSION,
    EncryptedPayloadEnvelope,
    ProfileKeyContext,
    WrappedKeyMaterialBlob,
    WrappedProfileKeyEnvelope,
)
from ..repositories.ha_key_hierarchy_repository import HomeAssistantKeyHierarchyRepository


class HomeAssistantLocalCryptoService:
    """Resolve local profile keys and encrypt/decrypt at-rest payloads."""

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
        if context.profile_key_id != envelope.profile_key_id:
            raise ValueError(
                "Profile key context does not match encrypted payload envelope."
            )
        expected_aad = _canonicalize_json(expected_aad_context)
        stored_aad = _canonicalize_json(envelope.aad_context)
        if expected_aad != stored_aad:
            raise ValueError("Encrypted payload AAD context mismatch.")
        cleartext = AESGCM(profile_key_bytes).decrypt(
            nonce=_decode_b64(envelope.nonce_b64),
            data=_decode_b64(envelope.cipher_text_b64)
            + _decode_b64(envelope.mac_b64),
            associated_data=_aad_bytes(stored_aad),
        )
        decoded = json.loads(cleartext.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("Encrypted payload did not decode to a JSON object.")
        return dict(decoded)

    def decrypt_profile_payload_sync(
        self,
        *,
        profile_id: str,
        envelope: EncryptedPayloadEnvelope,
        expected_aad_context: dict[str, Any],
    ) -> dict[str, Any]:
        context, profile_key_bytes = self._resolve_existing_profile_key(profile_id)
        if context.profile_key_id != envelope.profile_key_id:
            raise ValueError(
                "Profile key context does not match encrypted payload envelope."
            )
        expected_aad = _canonicalize_json(expected_aad_context)
        stored_aad = _canonicalize_json(envelope.aad_context)
        if expected_aad != stored_aad:
            raise ValueError("Encrypted payload AAD context mismatch.")
        cleartext = AESGCM(profile_key_bytes).decrypt(
            nonce=_decode_b64(envelope.nonce_b64),
            data=_decode_b64(envelope.cipher_text_b64)
            + _decode_b64(envelope.mac_b64),
            associated_data=_aad_bytes(stored_aad),
        )
        decoded = json.loads(cleartext.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("Encrypted payload did not decode to a JSON object.")
        return dict(decoded)

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
        if local_envelope is not None and local_envelope.wrapped_key_material:
            blob = WrappedKeyMaterialBlob.from_dict(
                json.loads(local_envelope.wrapped_key_material)
            )
            cleartext = AESGCM(_decode_b64(node_key_material)).decrypt(
                nonce=_decode_b64(blob.nonce_b64),
                data=_decode_b64(blob.cipher_text_b64) + _decode_b64(blob.mac_b64),
                associated_data=_aad_bytes(blob.aad_context),
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
        wrapped_blob = await self._wrap_local_direct_profile_key(
            server_node_id=server_node.node_id,
            server_node_key_id=server_node.node_key_id,
            profile_key_id=context.profile_key_id,
            profile_key_version=context.key_version,
            profile_key_bytes=raw_profile_key_bytes,
            node_key_bytes=_decode_b64(node_key_material),
        )
        updated_envelope = local_envelope or WrappedProfileKeyEnvelope(
            envelope_id=f"env-{context.profile_key_id}-local",
            profile_key_id=context.profile_key_id,
            profile_key_version=context.key_version,
            recipient_kind=ENVELOPE_RECIPIENT_NODE,
            recipient_id=server_node.node_key_id,
            wrap_mechanism=ENVELOPE_WRAP_MECHANISM_LOCAL_DIRECT,
            material_state=ENVELOPE_MATERIAL_STATE_LOCAL_DIRECT,
            wrapped_key_material=None,
            metadata={
                "node_id": server_node.node_id,
                "node_key_id": server_node.node_key_id,
                "access_scope": "current_home_assistant_installation",
            },
        )
        await self._key_hierarchy_repository.upsert_envelope(
            replace(
                updated_envelope,
                wrapped_key_material=json.dumps(wrapped_blob.to_dict()),
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
        if local_envelope is None or not local_envelope.wrapped_key_material:
            raise ValueError("Local direct-access envelope is missing.")
        blob = WrappedKeyMaterialBlob.from_dict(
            json.loads(local_envelope.wrapped_key_material)
        )
        cleartext = AESGCM(_decode_b64(node_key_material)).decrypt(
            nonce=_decode_b64(blob.nonce_b64),
            data=_decode_b64(blob.cipher_text_b64) + _decode_b64(blob.mac_b64),
            associated_data=_aad_bytes(blob.aad_context),
        )
        return context, cleartext

    async def _wrap_local_direct_profile_key(
        self,
        *,
        server_node_id: str,
        server_node_key_id: str,
        profile_key_id: str,
        profile_key_version: int,
        profile_key_bytes: bytes,
        node_key_bytes: bytes,
    ) -> WrappedKeyMaterialBlob:
        aad_context = {
            "kind": "profile_key_local_direct_access",
            "node_id": server_node_id,
            "node_key_id": server_node_key_id,
            "profile_key_id": profile_key_id,
            "profile_key_version": profile_key_version,
        }
        nonce = os.urandom(12)
        secret_box = AESGCM(node_key_bytes).encrypt(
            nonce=nonce,
            data=profile_key_bytes,
            associated_data=_aad_bytes(aad_context),
        )
        return WrappedKeyMaterialBlob(
            format_version=LOCAL_WRAPPED_KEY_FORMAT_VERSION,
            algorithm=LOCAL_PAYLOAD_AEAD_ALGORITHM,
            nonce_b64=_encode_b64(nonce),
            cipher_text_b64=_encode_b64(secret_box[:-16]),
            mac_b64=_encode_b64(secret_box[-16:]),
            aad_context=aad_context,
        )


def _canonicalize_json(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: _canonicalize_value(value[key])
        for key in sorted(value.keys())
    }


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
