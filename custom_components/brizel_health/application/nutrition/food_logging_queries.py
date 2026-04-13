"""Application queries for the Food Logging UI flow."""

from __future__ import annotations

from ...domains.nutrition.errors import BrizelImportedFoodValidationError
from ...domains.nutrition.models.imported_food_data import ImportedFoodData
from .food_import_use_cases import fetch_imported_food
from .source_registry import FoodSourceRegistry


def _get_enabled_source(registry: FoodSourceRegistry, source_name: str):
    """Return one enabled source definition or raise a clear validation error."""
    source = registry.get_source(source_name)
    if source is None or not source.enabled:
        raise BrizelImportedFoodValidationError(
            "Source is not registered or is disabled."
        )
    return source


async def get_external_food_detail_from_registry(
    registry: FoodSourceRegistry,
    *,
    source_name: str,
    source_id: str,
) -> ImportedFoodData:
    """Fetch one external food detail payload from an enabled source."""
    source = _get_enabled_source(registry, source_name)
    return await fetch_imported_food(source.adapter, source_id)


def get_supported_logging_units(
    imported_food: ImportedFoodData,
) -> tuple[str, ...]:
    """Return the currently safe logging units for one imported food.

    v1 stays conservative and only exposes units with a reliable conversion into
    the existing gram-based `FoodEntry` model.
    """
    return ("g",)


def get_default_logging_unit(
    imported_food: ImportedFoodData,
) -> str:
    """Return the default unit for one imported food detail payload."""
    supported_units = get_supported_logging_units(imported_food)
    return supported_units[0]
