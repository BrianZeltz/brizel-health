"""Home Assistant backed user repository."""

from __future__ import annotations

from ...core.users.brizel_user import BrizelUser, normalize_display_name
from ...core.users.errors import BrizelUserNotFoundError
from ..storage.store_manager import BrizelHealthStoreManager


class HomeAssistantUserRepository:
    """Persist users inside the integration store."""

    def __init__(self, store_manager: BrizelHealthStoreManager) -> None:
        """Initialize the repository."""
        self._store_manager = store_manager

    def _profiles(self) -> dict[str, dict]:
        """Return the mutable profile bucket."""
        return self._store_manager.data.setdefault("profiles", {})

    async def add(self, user: BrizelUser) -> BrizelUser:
        """Persist a new user."""
        self._profiles()[user.user_id] = user.to_dict()
        await self._store_manager.async_save()
        return user

    async def update(self, user: BrizelUser) -> BrizelUser:
        """Persist an existing user."""
        self.get_by_id(user.user_id)
        self._profiles()[user.user_id] = user.to_dict()
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
        return BrizelUser.from_dict(user_data)

    def get_all(self) -> list[BrizelUser]:
        """Load all users."""
        return [BrizelUser.from_dict(data) for data in self._profiles().values()]

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
                str(data.get("display_name", ""))
            ).casefold()
            if existing_name == normalized_name:
                return True

        return False
