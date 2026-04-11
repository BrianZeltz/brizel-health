"""Water shortcut built on top of the food and food entry system."""

from __future__ import annotations

from ...core.interfaces.user_repository import UserRepository
from ...domains.nutrition.errors import (
    BrizelFoodEntryNotFoundError,
    BrizelFoodNotFoundError,
)
from ...domains.nutrition.interfaces.food_entry_repository import FoodEntryRepository
from ...domains.nutrition.interfaces.food_repository import FoodRepository
from ...domains.nutrition.interfaces.recent_food_repository import (
    RecentFoodRepository,
)
from ...domains.nutrition.models.food import (
    Food,
    HYDRATION_KIND_DRINK,
    HYDRATION_SOURCE_INTERNAL,
)
from ...domains.nutrition.models.food_entry import FoodEntry
from ...domains.nutrition.services.water import (
    DEFAULT_WATER_AMOUNT_ML,
    INTERNAL_WATER_FOOD_ID,
    INTERNAL_WATER_HYDRATION_ML_PER_100G,
    INTERNAL_WATER_FOOD_NAME,
    build_internal_water_food,
    matches_internal_water_definition,
)
from .food_entry_queries import get_food_entries_for_profile
from .food_entry_use_cases import create_food_entry, delete_food_entry


async def _ensure_internal_water_food(repository: FoodRepository) -> Food:
    """Return the canonical water food, creating or normalizing it if needed."""
    try:
        water_food = repository.get_food_by_id(INTERNAL_WATER_FOOD_ID)
    except BrizelFoodNotFoundError:
        for existing_food in repository.get_all_foods():
            if matches_internal_water_definition(existing_food):
                return existing_food

        return await repository.add(build_internal_water_food())

    if not matches_internal_water_definition(water_food):
        water_food.update(
            name=INTERNAL_WATER_FOOD_NAME,
            brand=None,
            barcode=None,
            kcal_per_100g=0,
            protein_per_100g=0,
            carbs_per_100g=0,
            fat_per_100g=0,
            hydration_kind=HYDRATION_KIND_DRINK,
            hydration_ml_per_100g=INTERNAL_WATER_HYDRATION_ML_PER_100G,
            hydration_source=HYDRATION_SOURCE_INTERNAL,
        )
        water_food = await repository.update(water_food)

    return water_food


def _find_internal_water_food(repository: FoodRepository) -> Food | None:
    """Return the current internal water food if one exists."""
    try:
        water_food = repository.get_food_by_id(INTERNAL_WATER_FOOD_ID)
    except BrizelFoodNotFoundError:
        water_food = None

    if water_food is not None and matches_internal_water_definition(water_food):
        return water_food

    for existing_food in repository.get_all_foods():
        if matches_internal_water_definition(existing_food):
            return existing_food

    return None


async def add_water(
    food_repository: FoodRepository,
    food_entry_repository: FoodEntryRepository,
    user_repository: UserRepository,
    recent_food_repository: RecentFoodRepository | None,
    profile_id: str,
    amount_ml: float | int = DEFAULT_WATER_AMOUNT_ML,
    consumed_at: str | None = None,
    recent_food_max_items: int = 20,
) -> FoodEntry:
    """Add water by creating a normal food entry for the internal water food."""
    water_food = await _ensure_internal_water_food(food_repository)

    return await create_food_entry(
        repository=food_entry_repository,
        user_repository=user_repository,
        food_repository=food_repository,
        recent_food_repository=recent_food_repository,
        profile_id=profile_id,
        food_id=water_food.food_id,
        grams=amount_ml,
        consumed_at=consumed_at,
        recent_food_max_items=recent_food_max_items,
    )


async def remove_water(
    food_repository: FoodRepository,
    food_entry_repository: FoodEntryRepository,
    user_repository: UserRepository,
    profile_id: str,
    amount_ml: float | int = DEFAULT_WATER_AMOUNT_ML,
) -> FoodEntry:
    """Remove the latest matching water entry for the given profile."""
    water_food = _find_internal_water_food(food_repository)
    if water_food is None:
        raise BrizelFoodEntryNotFoundError(
            "No water entry is available to remove."
        )

    matching_entries = [
        food_entry
        for food_entry in get_food_entries_for_profile(
            repository=food_entry_repository,
            user_repository=user_repository,
            profile_id=profile_id,
        )
        if food_entry.food_id == water_food.food_id and food_entry.grams == float(amount_ml)
    ]
    if not matching_entries:
        raise BrizelFoodEntryNotFoundError(
            f"No {float(amount_ml):g} ml water entry is available to remove."
        )

    matching_entries.sort(
        key=lambda food_entry: (
            food_entry.consumed_at,
            food_entry.created_at,
            food_entry.food_entry_id,
        ),
        reverse=True,
    )
    return await delete_food_entry(
        repository=food_entry_repository,
        food_entry_id=matching_entries[0].food_entry_id,
    )
