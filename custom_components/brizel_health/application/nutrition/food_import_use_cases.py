"""Use cases for importing foods from external source adapters."""

from __future__ import annotations

from ...domains.nutrition.common import normalize_optional_text
from ...domains.nutrition.errors import (
    BrizelFoodNotFoundError,
    BrizelImportedFoodNotFoundError,
    BrizelImportedFoodValidationError,
)
from ...domains.nutrition.interfaces.external_food_source_adapter import (
    ExternalFoodSourceAdapter,
)
from ...domains.nutrition.interfaces.food_repository import FoodRepository
from ...domains.nutrition.interfaces.imported_food_cache_repository import (
    ImportedFoodCacheRepository,
)
from ...domains.nutrition.models.external_food_search_result import (
    ExternalFoodSearchResult,
)
from ...domains.nutrition.models.food import Food, normalize_food_name
from ...domains.nutrition.models.imported_food_cache_entry import (
    ImportedFoodCacheEntry,
)
from ...domains.nutrition.models.imported_food_data import ImportedFoodData
from ...domains.nutrition.services.import_enrichment import (
    create_food_from_imported_food,
    enrich_imported_food,
    merge_imported_food_into_existing_food,
)
from ...domains.nutrition.services.water import is_internal_water_food
from .source_registry import FoodSourceRegistry


async def fetch_imported_food(
    adapter: ExternalFoodSourceAdapter,
    source_id: str,
) -> ImportedFoodData:
    """Fetch a single imported food from a source adapter."""
    normalized_source_id = source_id.strip()
    if not normalized_source_id:
        raise BrizelImportedFoodValidationError("A source_id is required.")

    imported_food = await adapter.fetch_food_by_id(normalized_source_id)
    if imported_food is None:
        raise BrizelImportedFoodNotFoundError(
            f"No imported food found for source '{adapter.source_name}' and source_id '{normalized_source_id}'."
        )

    return imported_food


async def search_external_foods(
    adapter: ExternalFoodSourceAdapter,
    query: str,
    limit: int = 10,
) -> list[ExternalFoodSearchResult]:
    """Search a source adapter for imported foods."""
    normalized_query = query.strip()
    if not normalized_query:
        raise BrizelImportedFoodValidationError("A search query is required.")
    if limit <= 0:
        raise BrizelImportedFoodValidationError("limit must be greater than 0.")

    return await adapter.search_foods(normalized_query, limit=limit)


def _find_food_by_barcode(
    repository: FoodRepository,
    barcode: str | None,
) -> Food | None:
    """Return an existing food with the same barcode if one exists."""
    normalized_barcode = normalize_optional_text(barcode)
    if normalized_barcode is None:
        return None

    for food in repository.get_all_foods():
        if normalize_optional_text(food.barcode) == normalized_barcode:
            return food

    return None


def _find_food_by_name_and_brand(
    repository: FoodRepository,
    name: str,
    brand: str | None,
) -> Food | None:
    """Return an existing food with the same normalized name and brand."""
    normalized_name = normalize_food_name(name).casefold()
    normalized_brand = normalize_optional_text(brand)
    normalized_brand_casefold = (
        normalized_brand.casefold() if normalized_brand is not None else None
    )

    for food in repository.get_all_foods():
        existing_brand = normalize_optional_text(food.brand)
        existing_brand_casefold = (
            existing_brand.casefold() if existing_brand is not None else None
        )
        if (
            normalize_food_name(food.name).casefold() == normalized_name
            and existing_brand_casefold == normalized_brand_casefold
        ):
            return food

    return None


def _find_existing_food_for_import(
    food_repository: FoodRepository,
    cache_repository: ImportedFoodCacheRepository,
    imported_food: ImportedFoodData,
) -> Food | None:
    """Resolve which internal food should receive imported data."""
    cache_entry = cache_repository.get_by_source_ref(
        imported_food.source_name,
        imported_food.source_id,
    )
    if cache_entry is not None:
        try:
            cached_food = food_repository.get_food_by_id(cache_entry.food_id)
            if not is_internal_water_food(cached_food):
                return cached_food
        except BrizelFoodNotFoundError:
            pass

    food = _find_food_by_barcode(food_repository, imported_food.barcode)
    if food is not None and not is_internal_water_food(food):
        return food

    food = _find_food_by_name_and_brand(
        food_repository,
        imported_food.name,
        imported_food.brand,
    )
    if food is not None and not is_internal_water_food(food):
        return food

    return None


async def import_food_from_source(
    food_repository: FoodRepository,
    cache_repository: ImportedFoodCacheRepository,
    adapter: ExternalFoodSourceAdapter,
    source_id: str,
) -> Food:
    """Import or refresh a food from a source adapter."""
    imported_food = await fetch_imported_food(adapter, source_id)
    enrichment = enrich_imported_food(imported_food)

    existing_food = _find_existing_food_for_import(
        food_repository,
        cache_repository,
        imported_food,
    )
    if existing_food is None:
        food = create_food_from_imported_food(imported_food, enrichment)
        persisted_food = await food_repository.add(food)
    else:
        food = merge_imported_food_into_existing_food(
            existing_food,
            imported_food,
            enrichment,
        )
        persisted_food = await food_repository.update(food)

    await cache_repository.upsert(
        ImportedFoodCacheEntry.create(
            source_name=imported_food.source_name,
            source_id=imported_food.source_id,
            food_id=persisted_food.food_id,
            imported_food=imported_food,
            last_synced_at=imported_food.fetched_at,
        )
    )

    return persisted_food


async def import_food_from_registry(
    registry: FoodSourceRegistry,
    food_repository: FoodRepository,
    cache_repository: ImportedFoodCacheRepository,
    *,
    source_name: str,
    source_id: str,
) -> Food:
    """Import one food from a registered and enabled source."""
    source = registry.get_source(source_name)
    if source is None or not source.enabled:
        raise BrizelImportedFoodValidationError(
            "Source is not registered or is disabled."
        )

    return await import_food_from_source(
        food_repository=food_repository,
        cache_repository=cache_repository,
        adapter=source.adapter,
        source_id=source_id,
    )


async def get_cached_imported_food(
    cache_repository: ImportedFoodCacheRepository,
    source_name: str,
    source_id: str,
) -> ImportedFoodData:
    """Return a cached imported food snapshot."""
    normalized_source_name = source_name.strip().lower()
    normalized_source_id = source_id.strip()
    if not normalized_source_name:
        raise BrizelImportedFoodValidationError("A source_name is required.")
    if not normalized_source_id:
        raise BrizelImportedFoodValidationError("A source_id is required.")

    cache_entry = cache_repository.get_by_source_ref(
        normalized_source_name,
        normalized_source_id,
    )
    if cache_entry is None:
        raise BrizelImportedFoodNotFoundError(
            f"No cached imported food found for source '{normalized_source_name}' and source_id '{normalized_source_id}'."
        )

    return cache_entry.imported_food
