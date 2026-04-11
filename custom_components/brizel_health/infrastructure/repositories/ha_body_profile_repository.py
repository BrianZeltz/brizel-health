"""Home Assistant backed repository for body profiles."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...domains.body.models.body_profile import BodyProfile

if TYPE_CHECKING:
    from ..storage.store_manager import BrizelHealthStoreManager


class HomeAssistantBodyProfileRepository:
    """Persist per-profile body data inside the integration store."""

    def __init__(self, store_manager: "BrizelHealthStoreManager") -> None:
        """Initialize the repository."""
        self._store_manager = store_manager

    def _profiles(self) -> dict[str, dict]:
        """Return the mutable body profile bucket."""
        body = self._store_manager.data.setdefault("body", {})
        return body.setdefault("profiles", {})

    async def upsert(self, body_profile: BodyProfile) -> BodyProfile:
        """Insert or replace one body profile."""
        self._profiles()[body_profile.profile_id] = body_profile.to_dict()
        await self._store_manager.async_save()
        return body_profile

    def get_by_profile_id(self, profile_id: str) -> BodyProfile | None:
        """Return the stored body profile for one profile, if present."""
        stored_profile = self._profiles().get(profile_id)
        if stored_profile is None:
            return None
        return BodyProfile.from_dict(stored_profile)
