"""Write use cases for nutrition food entries."""

from __future__ import annotations

from ...core.interfaces.user_repository import UserRepository
from ...domains.nutrition.errors import BrizelFoodEntryValidationError
from ...domains.nutrition.interfaces.food_entry_repository import FoodEntryRepository
from ...domains.nutrition.interfaces.food_repository import FoodRepository
from ...domains.nutrition.interfaces.recent_food_repository import (
    RecentFoodRepository,
)
from ...domains.nutrition.models.food_entry import FoodEntry
from .recent_food_use_cases import remember_recent_food
from ..users.user_use_cases import get_user


async def create_food_entry(
    repository: FoodEntryRepository,
    user_repository: UserRepository,
    food_repository: FoodRepository,
    recent_food_repository: RecentFoodRepository | None,
    profile_id: str,
    food_id: str,
    grams: float | int,
    consumed_at: str | None = None,
    meal_type: str | None = None,
    note: str | None = None,
    source: str | None = None,
    recent_food_max_items: int = 20,
) -> FoodEntry:
    """Create and persist a food entry."""
    normalized_food_id = food_id.strip()
    if not normalized_food_id:
        raise BrizelFoodEntryValidationError("A food ID is required.")

    get_user(user_repository, profile_id)
    food = food_repository.get_food_by_id(normalized_food_id)
    food_entry = FoodEntry.create(
        profile_id=profile_id,
        food=food,
        grams=grams,
        consumed_at=consumed_at,
        meal_type=meal_type,
        note=note,
        source=source,
    )
    persisted_food_entry = await repository.add(food_entry)

    if recent_food_repository is not None:
        await remember_recent_food(
            recent_food_repository=recent_food_repository,
            food_repository=food_repository,
            profile_id=persisted_food_entry.profile_id,
            food_id=persisted_food_entry.food_id,
            used_at=persisted_food_entry.consumed_at,
            last_logged_grams=persisted_food_entry.grams,
            last_meal_type=persisted_food_entry.meal_type,
            max_items=recent_food_max_items,
        )

    return persisted_food_entry


async def delete_food_entry(
    repository: FoodEntryRepository,
    food_entry_id: str,
) -> FoodEntry:
    """Delete a food entry and return the removed entry."""
    normalized_food_entry_id = food_entry_id.strip()
    if not normalized_food_entry_id:
        raise BrizelFoodEntryValidationError("A food entry ID is required.")

    return await repository.delete(normalized_food_entry_id)
