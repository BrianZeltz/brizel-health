"""Home Assistant backed repository for body profiles."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...domains.security.models.key_hierarchy import (
    EncryptedPayloadEnvelope,
    PROTECTED_DATA_CLASS_PROFILE_CONTEXT,
)
from ...domains.body.models.body_profile import BodyProfile
from ..security.ha_local_crypto_service import HomeAssistantLocalCryptoService
from .ha_key_hierarchy_repository import HomeAssistantKeyHierarchyRepository

if TYPE_CHECKING:
    from ..storage.store_manager import BrizelHealthStoreManager


class HomeAssistantBodyProfileRepository:
    """Persist per-profile body data inside the integration store."""

    def __init__(self, store_manager: "BrizelHealthStoreManager") -> None:
        """Initialize the repository."""
        self._store_manager = store_manager
        self._key_hierarchy_repository = HomeAssistantKeyHierarchyRepository(
            store_manager
        )
        self._crypto_service = HomeAssistantLocalCryptoService(
            self._key_hierarchy_repository
        )

    def _profiles(self) -> dict[str, dict]:
        """Return the mutable body profile bucket."""
        body = self._store_manager.data.setdefault("body", {})
        return body.setdefault("profiles", {})

    async def upsert(self, body_profile: BodyProfile) -> BodyProfile:
        """Insert or replace one body profile."""
        self._profiles()[body_profile.profile_id] = await self._serialize_profile(
            body_profile
        )
        await self._store_manager.async_save()
        return body_profile

    def get_by_profile_id(self, profile_id: str) -> BodyProfile | None:
        """Return the stored body profile for one profile, if present."""
        stored_profile = self._profiles().get(profile_id)
        if stored_profile is None:
            return None
        return self._deserialize_profile(stored_profile)

    async def migrate_legacy_plaintext_profiles(self) -> int:
        """Re-write legacy plaintext body profiles into encrypted payload form."""
        profiles = self._profiles()
        migrated = 0
        replacements: dict[str, dict[str, object]] = {}

        for profile_id, data in profiles.items():
            if not isinstance(data, dict):
                continue
            if isinstance(data.get("encrypted_payload"), dict):
                continue
            profile = self._deserialize_profile(data)
            replacements[profile_id] = await self._serialize_profile(profile)
            migrated += 1

        if migrated:
            profiles.update(replacements)
            await self._store_manager.async_save()
        return migrated

    async def _serialize_profile(self, body_profile: BodyProfile) -> dict[str, object]:
        envelope = await self._crypto_service.encrypt_profile_payload(
            profile_id=body_profile.profile_id,
            data_class_id=PROTECTED_DATA_CLASS_PROFILE_CONTEXT,
            payload={
                "birth_date": body_profile.birth_date,
                "date_of_birth": body_profile.birth_date,
                "age_years": body_profile.age_years,
                "sex": body_profile.sex,
                "height_cm": body_profile.height_cm,
                "weight_kg": body_profile.weight_kg,
                "activity_level": body_profile.activity_level,
            },
            aad_context=_body_profile_payload_aad_context(
                profile_id=body_profile.profile_id
            ),
        )
        return {
            "profile_id": body_profile.profile_id,
            "encrypted_payload": envelope.to_dict(),
        }

    def _deserialize_profile(self, data: dict[str, object]) -> BodyProfile:
        encrypted_payload = data.get("encrypted_payload")
        if not isinstance(encrypted_payload, dict):
            return BodyProfile.from_dict(data)
        profile_id = str(data.get("profile_id") or "").strip()
        payload = self._crypto_service.decrypt_profile_payload_sync(
            profile_id=profile_id,
            envelope=EncryptedPayloadEnvelope.from_dict(encrypted_payload),
            expected_aad_context=_body_profile_payload_aad_context(
                profile_id=profile_id
            ),
        )
        merged = dict(data)
        merged.update(payload)
        return BodyProfile.from_dict(merged)


def _body_profile_payload_aad_context(*, profile_id: str) -> dict[str, object]:
    return {
        "data_class_id": PROTECTED_DATA_CLASS_PROFILE_CONTEXT,
        "storage": "body.profiles",
        "profile_id": profile_id,
    }
