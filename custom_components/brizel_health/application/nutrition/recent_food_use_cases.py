"""Use cases for per-profile recent foods."""

from __future__ import annotations

from ...domains.nutrition.errors import (
    BrizelFoodNotFoundError,
    BrizelFoodValidationError,
)
from ...domains.nutrition.interfaces.food_repository import FoodRepository
from ...domains.nutrition.interfaces.recent_food_repository import (
    RecentFoodRepository,
)
from ...domains.nutrition.models.food import Food
from ...domains.nutrition.models.recent_food_reference import RecentFoodReference


async def remember_recent_food(
    recent_food_repository: RecentFoodRepository,
    food_repository: FoodRepository,
    profile_id: str,
    food_id: str,
    used_at: str | None = None,
    max_items: int = 20,
) -> list[RecentFoodReference]:
    """Store a food reference in the profile-scoped recent-food list."""
    normalized_profile_id = profile_id.strip()
    normalized_food_id = food_id.strip()

    if not normalized_profile_id:
        raise BrizelFoodValidationError("A profile ID is required.")
    if not normalized_food_id:
        raise BrizelFoodValidationError("A food ID is required.")
    if max_items <= 0:
        raise BrizelFoodValidationError("max_items must be greater than 0.")

    food_repository.get_food_by_id(normalized_food_id)

    return await recent_food_repository.touch(
        profile_id=normalized_profile_id,
        food_id=normalized_food_id,
        used_at=used_at,
        max_items=max_items,
    )


def get_recent_foods(
    recent_food_repository: RecentFoodRepository,
    food_repository: FoodRepository,
    profile_id: str,
    limit: int = 10,
) -> list[Food]:
    """Resolve recent-food references into current catalog foods."""
    normalized_profile_id = profile_id.strip()
    if not normalized_profile_id:
        raise BrizelFoodValidationError("A profile ID is required.")
    if limit <= 0:
        raise BrizelFoodValidationError("limit must be greater than 0.")

    recent_references = recent_food_repository.get_recent(
        normalized_profile_id,
        limit=limit,
    )

    foods: list[Food] = []
    for reference in recent_references:
        try:
            foods.append(food_repository.get_food_by_id(reference.food_id))
        except BrizelFoodNotFoundError:
            continue

    return foods
