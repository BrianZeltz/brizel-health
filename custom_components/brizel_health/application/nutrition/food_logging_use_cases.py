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
from .food_import_use_cases import import_food_from_registry
from .source_registry import FoodSourceRegistry

_ALLOWED_LOGGING_UNITS = {"g"}


def _validate_logging_amount(amount: float | int) -> float:
    """Validate one requested logging amount."""
    normalized_amount = float(amount)
    if normalized_amount <= 0:
        raise BrizelImportedFoodValidationError("amount must be greater than 0.")
    return normalized_amount


def _normalize_logging_unit(unit: str | None) -> str:
    """Normalize one requested logging unit."""
    normalized_unit = (unit or "g").strip().lower()
    if normalized_unit not in _ALLOWED_LOGGING_UNITS:
        raise BrizelImportedFoodValidationError(
            "Only gram-based logging is currently supported for external food search results."
        )
    return normalized_unit


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
    recent_food_max_items: int = 20,
) -> LoggedExternalFoodEntryResult:
    """Import one external food if needed and immediately create a food entry."""
    normalized_amount = _validate_logging_amount(amount)
    normalized_unit = _normalize_logging_unit(unit)

    food = await import_food_from_registry(
        registry=registry,
        food_repository=food_repository,
        cache_repository=cache_repository,
        source_name=source_name,
        source_id=source_id,
    )
    food_entry = await create_food_entry(
        repository=food_entry_repository,
        user_repository=user_repository,
        food_repository=food_repository,
        recent_food_repository=recent_food_repository,
        profile_id=profile_id,
        food_id=food.food_id,
        grams=normalized_amount,
        consumed_at=consumed_at,
        source="manual",
        recent_food_max_items=recent_food_max_items,
    )

    return LoggedExternalFoodEntryResult(
        food=food,
        food_entry=food_entry,
        amount=normalized_amount,
        unit=normalized_unit,
        logged_grams=normalized_amount,
    )
