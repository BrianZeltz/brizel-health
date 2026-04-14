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
        last_logged_grams: float | int | None = None,
        last_meal_type: str | None = None,
        max_items: int = 20,
    ) -> list[RecentFoodReference]:
        """Move a food to the front of a profile's recent-food list."""
        incoming_reference = RecentFoodReference.create(
            food_id=food_id,
            last_used_at=used_at,
            last_logged_grams=last_logged_grams,
            last_meal_type=last_meal_type,
        )
        profile_bucket = self._recent_foods().setdefault(profile_id, [])

        existing_references = [
            RecentFoodReference.from_dict(item) for item in profile_bucket
        ]
        existing_reference = next(
            (
                item
                for item in existing_references
                if item.food_id == incoming_reference.food_id
            ),
            None,
        )
        merged_reference = RecentFoodReference.create(
            food_id=incoming_reference.food_id,
            last_used_at=incoming_reference.last_used_at,
            use_count=(existing_reference.use_count + 1)
            if existing_reference is not None
            else 1,
            last_logged_grams=incoming_reference.last_logged_grams
            if incoming_reference.last_logged_grams is not None
            else (
                existing_reference.last_logged_grams
                if existing_reference is not None
                else None
            ),
            last_meal_type=incoming_reference.last_meal_type
            if incoming_reference.last_meal_type is not None
            else (
                existing_reference.last_meal_type
                if existing_reference is not None
                else None
            ),
            is_favorite=existing_reference.is_favorite
            if existing_reference is not None
            else False,
        )

        updated_references = [merged_reference] + [
            item
            for item in existing_references
            if item.food_id != merged_reference.food_id
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
