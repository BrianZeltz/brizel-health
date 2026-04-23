"""Home Assistant backed user repository."""

from __future__ import annotations

from ...domains.security.models.key_hierarchy import (
    EncryptedPayloadEnvelope,
    PROTECTED_DATA_CLASS_PROFILE_CONTEXT,
)
from ...core.users.brizel_user import BrizelUser, normalize_display_name
from ...core.users.errors import BrizelUserNotFoundError
from ..storage.store_manager import BrizelHealthStoreManager
from .ha_key_hierarchy_repository import HomeAssistantKeyHierarchyRepository
from ..security.ha_local_crypto_service import HomeAssistantLocalCryptoService


class HomeAssistantUserRepository:
    """Persist users inside the integration store."""

    def __init__(self, store_manager: BrizelHealthStoreManager) -> None:
        """Initialize the repository."""
        self._store_manager = store_manager
        self._key_hierarchy_repository = HomeAssistantKeyHierarchyRepository(
            store_manager
        )
        self._crypto_service = HomeAssistantLocalCryptoService(
            self._key_hierarchy_repository
        )

    def _profiles(self) -> dict[str, dict]:
        """Return the mutable profile bucket."""
        return self._store_manager.data.setdefault("profiles", {})

    async def add(self, user: BrizelUser) -> BrizelUser:
        """Persist a new user."""
        self._profiles()[user.user_id] = await self._serialize_user(user)
        await self._store_manager.async_save()
        return user

    async def update(self, user: BrizelUser) -> BrizelUser:
        """Persist an existing user."""
        self.get_by_id(user.user_id)
        self._profiles()[user.user_id] = await self._serialize_user(user)
        await self._store_manager.async_save()
        return user

    async def delete(self, user_id: str) -> BrizelUser:
        """Delete a user."""
        user = self.get_by_id(user_id)
        del self._profiles()[user_id]
        await self._store_manager.async_save()
        return user

    def get_by_id(self, user_id: str) -> BrizelUser:
        """Load a user by ID."""
        user_data = self._profiles().get(user_id)
        if user_data is None:
            raise BrizelUserNotFoundError(
                f"No profile found for profile_id '{user_id}'."
            )
        return self._deserialize_user(user_data)

    def get_all(self) -> list[BrizelUser]:
        """Load all users."""
        return [self._deserialize_user(data) for data in self._profiles().values()]

    def display_name_exists(
        self,
        display_name: str,
        exclude_user_id: str | None = None,
    ) -> bool:
        """Return whether a display name already exists."""
        normalized_name = normalize_display_name(display_name).casefold()

        for user_id, data in self._profiles().items():
            if exclude_user_id is not None and user_id == exclude_user_id:
                continue

            existing_name = normalize_display_name(
                self._deserialize_user(data).display_name
            ).casefold()
            if existing_name == normalized_name:
                return True

        return False

    async def _serialize_user(self, user: BrizelUser) -> dict[str, object]:
        envelope = await self._crypto_service.encrypt_profile_payload(
            profile_id=user.user_id,
            data_class_id=PROTECTED_DATA_CLASS_PROFILE_CONTEXT,
            payload={
                "display_name": user.display_name,
            },
            aad_context=_user_payload_aad_context(
                profile_id=user.user_id,
                updated_at=user.created_at,
            ),
        )
        return {
            "profile_id": user.user_id,
            "linked_ha_user_id": user.linked_ha_user_id,
            "preferred_language": user.preferred_language,
            "preferred_region": user.preferred_region,
            "preferred_units": user.preferred_units,
            "created_at": user.created_at,
            "encrypted_payload": envelope.to_dict(),
        }

    def _deserialize_user(self, data: dict[str, object]) -> BrizelUser:
        encrypted_payload = data.get("encrypted_payload")
        if not isinstance(encrypted_payload, dict):
            return BrizelUser.from_dict(data)
        profile_id = str(data.get("profile_id") or "").strip()
        payload = self._crypto_service.decrypt_profile_payload_sync(
            profile_id=profile_id,
            envelope=EncryptedPayloadEnvelope.from_dict(encrypted_payload),
            expected_aad_context=_user_payload_aad_context(
                profile_id=profile_id,
                updated_at=str(data.get("created_at") or ""),
            ),
        )
        merged = dict(data)
        merged.update(payload)
        return BrizelUser.from_dict(merged)


def _user_payload_aad_context(
    *,
    profile_id: str,
    updated_at: str,
) -> dict[str, object]:
    return {
        "data_class_id": PROTECTED_DATA_CLASS_PROFILE_CONTEXT,
        "storage": "profiles",
        "profile_id": profile_id,
        "updated_at": updated_at,
    }
