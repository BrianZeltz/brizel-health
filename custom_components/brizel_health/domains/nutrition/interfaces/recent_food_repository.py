"""Repository contract for recent foods per profile."""

from __future__ import annotations

from typing import Protocol

from ..models.recent_food_reference import RecentFoodReference


class RecentFoodRepository(Protocol):
    """Persistence contract for profile-scoped recent foods."""

    async def touch(
        self,
        profile_id: str,
        food_id: str,
        used_at: str | None = None,
        max_items: int = 20,
    ) -> list[RecentFoodReference]:
        """Move a food to the front of a profile's recent-food list."""

    def get_recent(
        self,
        profile_id: str,
        limit: int = 10,
    ) -> list[RecentFoodReference]:
        """Return recent-food references for a profile."""
