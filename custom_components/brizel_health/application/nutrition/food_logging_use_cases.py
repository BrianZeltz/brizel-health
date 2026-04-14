"""Application use cases for the Food Logging UI flow."""

from __future__ import annotations

from dataclasses import dataclass

from ...core.interfaces.user_repository import UserRepository
from ...domains.nutrition.errors import BrizelImportedFoodValidationError
from ...domains.nutrition.interfaces.food_entry_repository import FoodEntryRepository
from ...domains.nutrition.interfaces.food_repository import FoodRepository
from ...domains.nutrition.interfaces.imported_food_cache_repository import (
    ImportedFoodCacheRepository,
)
from ...domains.nutrition.interfaces.recent_food_repository import (
    RecentFoodRepository,
)
from ...domains.nutrition.models.food import Food
from ...domains.nutrition.models.food_entry import FoodEntry
from .food_entry_use_cases import create_food_entry
from .food_import_use_cases import fetch_imported_food, import_food_from_registry
from .food_logging_queries import get_logging_unit_option
from .source_registry import FoodSourceRegistry


def _validate_logging_amount(amount: float | int) -> float:
    """Validate one requested logging amount."""
    normalized_amount = float(amount)
    if normalized_amount <= 0:
        raise BrizelImportedFoodValidationError("amount must be greater than 0.")
    return normalized_amount


def _round_logged_grams(grams: float) -> float:
    """Round converted gram values conservatively for storage and UX."""
    return round(float(grams), 2)


@dataclass(slots=True)
class LoggedExternalFoodEntryResult:
    """Result of logging one externally sourced food into the internal diary."""

    food: Food
    food_entry: FoodEntry
    amount: float
    unit: str
    logged_grams: float


async def log_external_food_entry_from_registry(
    registry: FoodSourceRegistry,
    food_repository: FoodRepository,
    cache_repository: ImportedFoodCacheRepository,
    food_entry_repository: FoodEntryRepository,
    user_repository: UserRepository,
    recent_food_repository: RecentFoodRepository | None,
    *,
    profile_id: str,
    source_name: str,
    source_id: str,
    amount: float | int,
    unit: str | None = None,
    consumed_at: str | None = None,
    meal_type: str | None = None,
    source: str | None = None,
    recent_food_max_items: int = 20,
) -> LoggedExternalFoodEntryResult:
    """Import one external food if needed and immediately create a food entry."""
    normalized_amount = _validate_logging_amount(amount)
    source_definition = registry.get_source(source_name)
    if source_definition is None or not source_definition.enabled:
        raise BrizelImportedFoodValidationError(
            "Source is not registered or is disabled."
        )

    imported_food = await fetch_imported_food(source_definition.adapter, source_id)
    selected_unit_option = get_logging_unit_option(imported_food, unit)
    if selected_unit_option is None:
        raise BrizelImportedFoodValidationError(
            "The requested logging unit is not supported for this food."
        )

    normalized_unit = selected_unit_option.unit
    logged_grams = _round_logged_grams(
        normalized_amount * selected_unit_option.grams_per_unit
    )

    food = await import_food_from_registry(
        registry=registry,
        food_repository=food_repository,
        cache_repository=cache_repository,
        source_name=source_name,
        source_id=source_id,
        imported_food=imported_food,
    )
    food_entry = await create_food_entry(
        repository=food_entry_repository,
        user_repository=user_repository,
        food_repository=food_repository,
        recent_food_repository=recent_food_repository,
        profile_id=profile_id,
        food_id=food.food_id,
        grams=logged_grams,
        consumed_at=consumed_at,
        meal_type=meal_type,
        source=source,
        recent_food_max_items=recent_food_max_items,
    )

    return LoggedExternalFoodEntryResult(
        food=food,
        food_entry=food_entry,
        amount=normalized_amount,
        unit=normalized_unit,
        logged_grams=logged_grams,
    )
