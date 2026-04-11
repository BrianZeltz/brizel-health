"""Home Assistant backed repository for profile recent foods."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...domains.nutrition.models.recent_food_reference import RecentFoodReference

if TYPE_CHECKING:
    from ..storage.store_manager import BrizelHealthStoreManager


class HomeAssistantRecentFoodRepository:
    """Persist profile recent-food references inside the integration store."""

    def __init__(self, store_manager: "BrizelHealthStoreManager") -> None:
        """Initialize the repository."""
        self._store_manager = store_manager

    def _recent_foods(self) -> dict[str, list[dict]]:
        """Return the mutable per-profile recent-food bucket."""
        nutrition = self._store_manager.data.setdefault("nutrition", {})
        return nutrition.setdefault("recent_foods_by_profile", {})

    async def touch(
        self,
        profile_id: str,
        food_id: str,
        used_at: str | None = None,
        max_items: int = 20,
    ) -> list[RecentFoodReference]:
        """Move a food to the front of a profile's recent-food list."""
        reference = RecentFoodReference.create(
            food_id=food_id,
            last_used_at=used_at,
        )
        profile_bucket = self._recent_foods().setdefault(profile_id, [])

        filtered_items = [
            item
            for item in profile_bucket
            if str(item.get("food_id", "")).strip() != reference.food_id
        ]
        updated_references = [reference] + [
            RecentFoodReference.from_dict(item)
            for item in filtered_items
        ]
        updated_references = updated_references[:max_items]

        self._recent_foods()[profile_id] = [
            item.to_dict() for item in updated_references
        ]
        await self._store_manager.async_save()
        return updated_references

    def get_recent(
        self,
        profile_id: str,
        limit: int = 10,
    ) -> list[RecentFoodReference]:
        """Return recent-food references for a profile."""
        profile_bucket = self._recent_foods().get(profile_id, [])
        return [
            RecentFoodReference.from_dict(item)
            for item in profile_bucket[:limit]
        ]
