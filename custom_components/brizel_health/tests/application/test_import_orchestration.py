"""Tests for central multi-source import orchestration."""

from __future__ import annotations

import pytest

from custom_components.brizel_health.application.nutrition.import_orchestration import (
    IMPORT_STATUS_FAILURE,
    IMPORT_STATUS_SUCCESS,
    FoodSourceImportRequest,
    import_food_from_sources,
)
from custom_components.brizel_health.application.nutrition.source_registry import (
    FoodSourceRegistry,
)
from custom_components.brizel_health.domains.nutrition.errors import (
    BrizelFoodNotFoundError,
)
from custom_components.brizel_health.domains.nutrition.models.food import Food
from custom_components.brizel_health.domains.nutrition.models.imported_food_cache_entry import (
    ImportedFoodCacheEntry,
)
from custom_components.brizel_health.domains.nutrition.models.imported_food_data import (
    ImportedFoodData,
)


class InMemoryFoodRepository:
    """Simple in-memory repository for source orchestration tests."""

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
    """Simple in-memory cache repository for orchestration tests."""

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
    """Simple fixture-backed adapter for orchestration tests."""

    def __init__(
        self,
        source_name: str,
        imported_foods: list[ImportedFoodData] | None = None,
        error_message: str | None = None,
    ) -> None:
        self.source_name = source_name
        self._foods = {food.source_id: food for food in imported_foods or []}
        self._error_message = error_message

    async def fetch_food_by_id(self, source_id: str) -> ImportedFoodData | None:
        if self._error_message is not None:
            raise RuntimeError(self._error_message)
        return self._foods.get(source_id.strip())

    async def search_foods(
        self,
        query: str,
        limit: int = 10,
    ) -> list[ImportedFoodData]:
        return []


@pytest.mark.asyncio
async def test_import_food_from_sources_processes_multiple_sources_and_keeps_results_separate() -> None:
    """Central orchestration should process multiple sources and keep per-source results."""
    registry = FoodSourceRegistry()
    registry.register_source(
        "open_food_facts",
        FixtureExternalFoodSourceAdapter(
            "open_food_facts",
            [
                ImportedFoodData.create(
                    source_name="open_food_facts",
                    source_id="off-1",
                    name="Chocolate Bar",
                    brand="Example Brand",
                    barcode=None,
                    kcal_per_100g=550,
                    protein_per_100g=5,
                    carbs_per_100g=50,
                    fat_per_100g=35,
                    labels=["vegan"],
                    labels_known=True,
                    fetched_at="2026-04-05T10:00:00+00:00",
                )
            ],
        ),
        priority=10,
    )
    registry.register_source(
        "usda",
        FixtureExternalFoodSourceAdapter(
            "usda",
            [
                ImportedFoodData.create(
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
                    fetched_at="2026-04-05T10:00:00+00:00",
                )
            ],
        ),
        priority=20,
    )
    food_repository = InMemoryFoodRepository()
    cache_repository = InMemoryImportedFoodCacheRepository()

    results = await import_food_from_sources(
        registry=registry,
        food_repository=food_repository,
        cache_repository=cache_repository,
        source_requests=[
            FoodSourceImportRequest.create("open_food_facts", "off-1"),
            FoodSourceImportRequest.create("usda", "123456"),
        ],
    )

    assert [result.source_name for result in results] == [
        "open_food_facts",
        "usda",
    ]
    assert [result.status for result in results] == [
        IMPORT_STATUS_SUCCESS,
        IMPORT_STATUS_SUCCESS,
    ]
    assert all(result.food_id is not None for result in results)
    assert cache_repository.get_by_source_ref("open_food_facts", "off-1") is not None
    assert cache_repository.get_by_source_ref("usda", "123456") is not None


@pytest.mark.asyncio
async def test_import_food_from_sources_keeps_going_when_one_source_fails() -> None:
    """A failure in one source should not block imports from the other sources."""
    registry = FoodSourceRegistry()
    registry.register_source(
        "open_food_facts",
        FixtureExternalFoodSourceAdapter(
            "open_food_facts",
            [
                ImportedFoodData.create(
                    source_name="open_food_facts",
                    source_id="off-1",
                    name="Chocolate Bar",
                    brand="Example Brand",
                    barcode=None,
                    kcal_per_100g=550,
                    protein_per_100g=5,
                    carbs_per_100g=50,
                    fat_per_100g=35,
                    fetched_at="2026-04-05T10:00:00+00:00",
                )
            ],
        ),
        priority=10,
    )
    registry.register_source(
        "usda",
        FixtureExternalFoodSourceAdapter(
            "usda",
            error_message="Temporary source failure",
        ),
        priority=20,
    )
    food_repository = InMemoryFoodRepository()
    cache_repository = InMemoryImportedFoodCacheRepository()

    results = await import_food_from_sources(
        registry=registry,
        food_repository=food_repository,
        cache_repository=cache_repository,
        source_requests=[
            FoodSourceImportRequest.create("open_food_facts", "off-1"),
            FoodSourceImportRequest.create("usda", "123456"),
        ],
    )

    assert results[0].status == IMPORT_STATUS_SUCCESS
    assert results[0].food_id is not None
    assert results[0].error is None
    assert results[1].status == IMPORT_STATUS_FAILURE
    assert results[1].food_id is None
    assert results[1].error == "Temporary source failure"
    assert cache_repository.get_by_source_ref("open_food_facts", "off-1") is not None
    assert cache_repository.get_by_source_ref("usda", "123456") is None


@pytest.mark.asyncio
async def test_import_food_from_sources_reports_unregistered_or_disabled_sources() -> None:
    """Registry-based orchestration should report sources that are unavailable for use."""
    registry = FoodSourceRegistry()
    registry.register_source(
        "open_food_facts",
        FixtureExternalFoodSourceAdapter("open_food_facts"),
        enabled=False,
    )
    food_repository = InMemoryFoodRepository()
    cache_repository = InMemoryImportedFoodCacheRepository()

    results = await import_food_from_sources(
        registry=registry,
        food_repository=food_repository,
        cache_repository=cache_repository,
        source_requests=[
            FoodSourceImportRequest.create("open_food_facts", "off-1"),
            FoodSourceImportRequest.create("usda", "123456"),
        ],
    )

    assert [result.source_name for result in results] == [
        "open_food_facts",
        "usda",
    ]
    assert all(result.status == IMPORT_STATUS_FAILURE for result in results)
    assert results[0].error == "Source is not registered or is disabled."
    assert results[1].error == "Source is not registered or is disabled."
