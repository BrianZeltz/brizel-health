"""Tests for imported food use cases."""

from __future__ import annotations

import pytest

from custom_components.brizel_health.application.nutrition.food_import_use_cases import (
    get_cached_imported_food,
    import_food_from_registry,
    import_food_from_source,
    search_external_foods,
)
from custom_components.brizel_health.application.nutrition.source_registry import (
    FoodSourceRegistry,
)
from custom_components.brizel_health.domains.nutrition.errors import (
    BrizelFoodNotFoundError,
)
from custom_components.brizel_health.domains.nutrition.models.food import (
    Food,
    HYDRATION_KIND_FOOD,
    HYDRATION_SOURCE_EXPLICIT,
)
from custom_components.brizel_health.domains.nutrition.models.food_compatibility import (
    FOOD_COMPATIBILITY_SOURCE_EXPLICIT,
    FoodCompatibilityMetadata,
)
from custom_components.brizel_health.domains.nutrition.models.external_food_search_result import (
    ExternalFoodSearchResult,
)
from custom_components.brizel_health.domains.nutrition.models.imported_food_cache_entry import (
    ImportedFoodCacheEntry,
)
from custom_components.brizel_health.domains.nutrition.models.imported_food_data import (
    ImportedFoodData,
)
from custom_components.brizel_health.domains.nutrition.services.water import (
    INTERNAL_WATER_FOOD_ID,
    build_internal_water_food,
)


class InMemoryFoodRepository:
    """Simple in-memory repository for imported food tests."""

    def __init__(self, foods: list[Food] | None = None) -> None:
        self._foods = {food.food_id: food for food in foods or []}

    async def add(self, food: Food) -> Food:
        self._foods[food.food_id] = food
        return food

    async def update(self, food: Food) -> Food:
        self._foods[food.food_id] = food
        return food

    async def delete(self, food_id: str) -> None:
        del self._foods[food_id]

    def get_food_by_id(self, food_id: str) -> Food:
        food = self._foods.get(food_id)
        if food is None:
            raise BrizelFoodNotFoundError(
                f"No food found for food_id '{food_id}'."
            )
        return food

    def get_all_foods(self) -> list[Food]:
        return list(self._foods.values())

    def food_name_exists(
        self,
        name: str,
        brand: str | None,
        exclude_food_id: str | None = None,
    ) -> bool:
        return False

    def barcode_exists(
        self,
        barcode: str | None,
        exclude_food_id: str | None = None,
    ) -> bool:
        return False


class InMemoryImportedFoodCacheRepository:
    """Simple in-memory cache repository for imported food tests."""

    def __init__(
        self,
        entries: list[ImportedFoodCacheEntry] | None = None,
    ) -> None:
        self._entries = {
            (entry.source_name, entry.source_id): entry for entry in entries or []
        }

    def get_by_source_ref(
        self,
        source_name: str,
        source_id: str,
    ) -> ImportedFoodCacheEntry | None:
        return self._entries.get((source_name.strip().lower(), source_id.strip()))

    async def upsert(
        self,
        cache_entry: ImportedFoodCacheEntry,
    ) -> ImportedFoodCacheEntry:
        self._entries[(cache_entry.source_name, cache_entry.source_id)] = cache_entry
        return cache_entry


class FixtureExternalFoodSourceAdapter:
    """Simple fixture-backed adapter for imported food use case tests."""

    source_name = "fixture"

    def __init__(self, imported_foods: list[ImportedFoodData]) -> None:
        self._foods = {food.source_id: food for food in imported_foods}
        if imported_foods:
            self.source_name = imported_foods[0].source_name

    async def fetch_food_by_id(self, source_id: str) -> ImportedFoodData | None:
        return self._foods.get(source_id.strip())

    async def search_foods(
        self,
        query: str,
        limit: int = 10,
    ) -> list[ExternalFoodSearchResult]:
        normalized_query = query.strip().lower()
        matches = [
            food
            for food in self._foods.values()
            if normalized_query in food.name.lower()
        ]
        return [
            ExternalFoodSearchResult.create(
                source_name=food.source_name,
                source_id=food.source_id,
                name=food.name,
                brand=food.brand,
                barcode=food.barcode,
                kcal_per_100g=food.kcal_per_100g,
                protein_per_100g=food.protein_per_100g,
                carbs_per_100g=food.carbs_per_100g,
                fat_per_100g=food.fat_per_100g,
                hydration_ml_per_100g=food.hydration_ml_per_100g,
            )
            for food in matches[:limit]
        ]


@pytest.mark.asyncio
async def test_import_food_from_source_creates_food_and_cache_entry() -> None:
    """Imported food data should create an internal food and a cache record."""
    imported_food = ImportedFoodData.create(
        source_name="open_food_facts",
        source_id="off-1",
        name="Mineral Water",
        brand="Brizel",
        barcode="400000000001",
        kcal_per_100g=0,
        protein_per_100g=0,
        carbs_per_100g=0,
        fat_per_100g=0,
        labels=["vegan"],
        labels_known=True,
        allergens=[],
        allergens_known=True,
        hydration_kind="drink",
        hydration_ml_per_100g=100,
        market_country_codes=["DE"],
        market_region_codes=["EU"],
        fetched_at="2026-04-05T10:00:00+00:00",
    )
    food_repository = InMemoryFoodRepository()
    cache_repository = InMemoryImportedFoodCacheRepository()
    adapter = FixtureExternalFoodSourceAdapter([imported_food])

    food = await import_food_from_source(
        food_repository=food_repository,
        cache_repository=cache_repository,
        adapter=adapter,
        source_id="off-1",
    )

    cached_imported_food = await get_cached_imported_food(
        cache_repository,
        "open_food_facts",
        "off-1",
    )

    assert food.name == "Mineral Water"
    assert food.barcode == "400000000001"
    assert food.hydration_kind == "drink"
    assert food.hydration_source == "imported"
    assert food.compatibility is not None
    assert food.compatibility.source == "imported"
    assert cached_imported_food.market_country_codes == ("de",)
    assert cached_imported_food.market_region_codes == ("eu",)


@pytest.mark.asyncio
async def test_import_food_from_source_updates_existing_food_without_overwriting_explicit_internal_metadata() -> None:
    """Imported refreshes should keep explicit internal enrichment untouched."""
    existing_food = Food.create(
        name="Greek Yogurt",
        brand="Old Brand",
        barcode="012345678905",
        kcal_per_100g=85,
        protein_per_100g=8.5,
        carbs_per_100g=4.5,
        fat_per_100g=3.5,
        hydration_kind=HYDRATION_KIND_FOOD,
        hydration_ml_per_100g=60,
        hydration_source=HYDRATION_SOURCE_EXPLICIT,
        compatibility=FoodCompatibilityMetadata.create(
            labels=["vegetarian"],
            labels_known=True,
            source=FOOD_COMPATIBILITY_SOURCE_EXPLICIT,
        ),
    )
    imported_food = ImportedFoodData.create(
        source_name="open_food_facts",
        source_id="off-2",
        name="Greek Yogurt Updated",
        brand="Sample Dairy",
        barcode="012345678905",
        kcal_per_100g=97,
        protein_per_100g=9,
        carbs_per_100g=3.9,
        fat_per_100g=5,
        allergens=["milk"],
        allergens_known=True,
        labels=[],
        labels_known=True,
        hydration_kind="drink",
        hydration_ml_per_100g=100,
        fetched_at="2026-04-05T11:00:00+00:00",
    )
    food_repository = InMemoryFoodRepository([existing_food])
    cache_repository = InMemoryImportedFoodCacheRepository()
    adapter = FixtureExternalFoodSourceAdapter([imported_food])

    updated_food = await import_food_from_source(
        food_repository=food_repository,
        cache_repository=cache_repository,
        adapter=adapter,
        source_id="off-2",
    )

    assert updated_food.food_id == existing_food.food_id
    assert updated_food.name == "Greek Yogurt Updated"
    assert updated_food.brand == "Sample Dairy"
    assert updated_food.kcal_per_100g == 97
    assert updated_food.hydration_kind == HYDRATION_KIND_FOOD
    assert updated_food.hydration_ml_per_100g == 60
    assert updated_food.hydration_source == HYDRATION_SOURCE_EXPLICIT
    assert updated_food.compatibility is not None
    assert updated_food.compatibility.source == FOOD_COMPATIBILITY_SOURCE_EXPLICIT


@pytest.mark.asyncio
async def test_import_food_from_source_does_not_reuse_internal_water_food() -> None:
    """Imported foods must not overwrite the protected internal water shortcut food."""
    imported_food = ImportedFoodData.create(
        source_name="open_food_facts",
        source_id="off-water",
        name="Water",
        brand=None,
        barcode=None,
        kcal_per_100g=0,
        protein_per_100g=0,
        carbs_per_100g=0,
        fat_per_100g=0,
        hydration_kind="drink",
        hydration_ml_per_100g=100,
        fetched_at="2026-04-05T12:00:00+00:00",
    )
    internal_water = build_internal_water_food()
    food_repository = InMemoryFoodRepository([internal_water])
    cache_repository = InMemoryImportedFoodCacheRepository()
    adapter = FixtureExternalFoodSourceAdapter([imported_food])

    imported_result = await import_food_from_source(
        food_repository=food_repository,
        cache_repository=cache_repository,
        adapter=adapter,
        source_id="off-water",
    )

    assert imported_result.food_id != INTERNAL_WATER_FOOD_ID
    assert food_repository.get_food_by_id(INTERNAL_WATER_FOOD_ID).food_id == (
        INTERNAL_WATER_FOOD_ID
    )


@pytest.mark.asyncio
async def test_import_food_from_source_keeps_usda_water_measurement_out_of_internal_hydration_until_kind_is_known() -> None:
    """Raw USDA water values should stay cached/imported without becoming trusted hydration metadata."""
    imported_food = ImportedFoodData.create(
        source_name="usda",
        source_id="123456",
        name="Apple, raw",
        brand=None,
        barcode=None,
        kcal_per_100g=52,
        protein_per_100g=0.3,
        carbs_per_100g=14,
        fat_per_100g=0.2,
        hydration_ml_per_100g=85.6,
        fetched_at="2026-04-05T12:00:00+00:00",
    )
    food_repository = InMemoryFoodRepository()
    cache_repository = InMemoryImportedFoodCacheRepository()
    adapter = FixtureExternalFoodSourceAdapter([imported_food])

    imported_result = await import_food_from_source(
        food_repository=food_repository,
        cache_repository=cache_repository,
        adapter=adapter,
        source_id="123456",
    )

    cached_imported_food = await get_cached_imported_food(
        cache_repository,
        "usda",
        "123456",
    )

    assert imported_result.hydration_kind is None
    assert imported_result.hydration_ml_per_100g is None
    assert imported_result.hydration_source is None
    assert cached_imported_food.hydration_ml_per_100g == 85.6
    assert cached_imported_food.hydration_kind is None


@pytest.mark.asyncio
async def test_search_external_foods_returns_adapter_results() -> None:
    """Search use case should delegate to the source adapter contract."""
    adapter = FixtureExternalFoodSourceAdapter(
        [
            ImportedFoodData.create(
                source_name="open_food_facts",
                source_id="off-1",
                name="Tomato Soup",
                brand="Brizel",
                barcode=None,
                kcal_per_100g=40,
                protein_per_100g=1,
                carbs_per_100g=7,
                fat_per_100g=1,
                fetched_at="2026-04-05T10:00:00+00:00",
            ),
            ImportedFoodData.create(
                source_name="open_food_facts",
                source_id="off-2",
                name="Apple Juice",
                brand="Brizel",
                barcode=None,
                kcal_per_100g=46,
                protein_per_100g=0.1,
                carbs_per_100g=11,
                fat_per_100g=0.1,
                fetched_at="2026-04-05T10:00:00+00:00",
            ),
        ]
    )

    results = await search_external_foods(adapter, "juice")

    assert [result.source_id for result in results] == ["off-2"]


@pytest.mark.asyncio
async def test_import_food_from_registry_uses_the_registered_source() -> None:
    """Registry-backed import should resolve one enabled source and import through it."""
    imported_food = ImportedFoodData.create(
        source_name="usda",
        source_id="123456",
        name="Apple, raw",
        brand=None,
        barcode=None,
        kcal_per_100g=52,
        protein_per_100g=0.3,
        carbs_per_100g=14,
        fat_per_100g=0.2,
        fetched_at="2026-04-05T10:00:00+00:00",
    )
    registry = FoodSourceRegistry()
    registry.register_source(
        "usda",
        FixtureExternalFoodSourceAdapter([imported_food]),
        enabled=True,
    )

    imported_result = await import_food_from_registry(
        registry=registry,
        food_repository=InMemoryFoodRepository(),
        cache_repository=InMemoryImportedFoodCacheRepository(),
        source_name="usda",
        source_id="123456",
    )

    assert imported_result.name == "Apple, raw"
