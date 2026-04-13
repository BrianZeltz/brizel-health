"""Tests for external food search queries."""

from __future__ import annotations

import pytest

from custom_components.brizel_health.application.nutrition.food_search_queries import (
    FoodSourceSearchResult,
    SEARCH_STATUS_EMPTY,
    SEARCH_STATUS_FAILURE,
    SEARCH_STATUS_SUCCESS,
    aggregate_food_search_results,
    search_foods_from_sources,
    search_foods_from_sources_aggregated,
)
from custom_components.brizel_health.application.nutrition.source_registry import (
    FoodSourceRegistry,
)
from custom_components.brizel_health.domains.nutrition.models.external_food_search_result import (
    ExternalFoodSearchResult,
)


class FixtureSearchAdapter:
    """Simple async adapter for search-query tests."""

    def __init__(
        self,
        source_name: str,
        results: list[ExternalFoodSearchResult] | None = None,
        error_message: str | None = None,
    ) -> None:
        self.source_name = source_name
        self._results = results or []
        self._error_message = error_message

    async def fetch_food_by_id(self, source_id: str):
        return None

    async def search_foods(
        self,
        query: str,
        limit: int = 10,
    ) -> list[ExternalFoodSearchResult]:
        if self._error_message is not None:
            raise RuntimeError(self._error_message)
        normalized_query = query.strip().lower()
        return [
            result
            for result in self._results
            if normalized_query in result.name.lower()
        ][:limit]


@pytest.mark.asyncio
async def test_search_foods_from_sources_returns_results_for_selected_sources() -> None:
    """Search should return per-source result buckets for enabled sources."""
    registry = FoodSourceRegistry()
    registry.register_source(
        "usda",
        FixtureSearchAdapter(
            "usda",
            [
                ExternalFoodSearchResult.create(
                    source_name="usda",
                    source_id="123",
                    name="Apple, raw",
                    kcal_per_100g=52,
                )
            ],
        ),
        enabled=True,
        priority=10,
    )

    results = await search_foods_from_sources(
        registry,
        "apple",
        requested_source_names=["usda"],
    )

    assert len(results) == 1
    assert results[0].status == SEARCH_STATUS_SUCCESS
    assert [result.source_id for result in results[0].results] == ["123"]


@pytest.mark.asyncio
async def test_search_foods_from_sources_reports_source_failures_without_blocking() -> None:
    """Search should isolate failures per source."""
    registry = FoodSourceRegistry()
    registry.register_source(
        "usda",
        FixtureSearchAdapter(
            "usda",
            [
                ExternalFoodSearchResult.create(
                    source_name="usda",
                    source_id="123",
                    name="Apple, raw",
                )
            ],
        ),
        enabled=True,
        priority=10,
    )
    registry.register_source(
        "open_food_facts",
        FixtureSearchAdapter(
            "open_food_facts",
            error_message="Search not supported",
        ),
        enabled=True,
        priority=20,
    )

    results = await search_foods_from_sources(registry, "apple")

    assert [result.source_name for result in results] == ["usda", "open_food_facts"]
    assert results[0].status == SEARCH_STATUS_SUCCESS
    assert results[1].status == SEARCH_STATUS_FAILURE
    assert results[1].error == "Search not supported"


@pytest.mark.asyncio
async def test_search_foods_from_sources_aggregated_combines_and_ranks_results() -> None:
    """Combined search should merge successful sources into one ranked result list."""
    registry = FoodSourceRegistry()
    registry.register_source(
        "usda",
        FixtureSearchAdapter(
            "usda",
            [
                ExternalFoodSearchResult.create(
                    source_name="usda",
                    source_id="usda-1",
                    name="Apple, raw",
                    kcal_per_100g=52,
                    protein_per_100g=0.3,
                    carbs_per_100g=14,
                    fat_per_100g=0.2,
                )
            ],
        ),
        enabled=True,
        priority=10,
    )
    registry.register_source(
        "open_food_facts",
        FixtureSearchAdapter(
            "open_food_facts",
            [
                ExternalFoodSearchResult.create(
                    source_name="open_food_facts",
                    source_id="off-1",
                    name="Apple Juice",
                    brand="Brizel",
                    kcal_per_100g=46,
                    protein_per_100g=0.1,
                    carbs_per_100g=11,
                    fat_per_100g=0.1,
                )
            ],
        ),
        enabled=True,
        priority=20,
    )

    result = await search_foods_from_sources_aggregated(registry, "apple")

    assert result.status == SEARCH_STATUS_SUCCESS
    assert [item.source_id for item in result.results] == ["usda-1", "off-1"]
    assert [item.source_name for item in result.source_results] == [
        "usda",
        "open_food_facts",
    ]


@pytest.mark.asyncio
async def test_search_foods_from_sources_aggregated_keeps_empty_when_one_source_succeeds_without_hits() -> None:
    """A mixed success/failure search should stay empty instead of surfacing a total failure."""
    registry = FoodSourceRegistry()
    registry.register_source(
        "usda",
        FixtureSearchAdapter("usda", []),
        enabled=True,
        priority=10,
    )
    registry.register_source(
        "open_food_facts",
        FixtureSearchAdapter(
            "open_food_facts",
            error_message="Open Food Facts unavailable",
        ),
        enabled=True,
        priority=20,
    )

    result = await search_foods_from_sources_aggregated(registry, "apple")

    assert result.status == SEARCH_STATUS_EMPTY
    assert result.results == []
    assert result.error is None


def test_aggregate_food_search_results_reports_total_failure_when_all_sources_fail() -> None:
    """If every source fails, the aggregated response should expose one clean failure."""
    registry = FoodSourceRegistry()
    source_results = [
        FoodSourceSearchResult(
            source_name="usda",
            status=SEARCH_STATUS_FAILURE,
            results=[],
            error="USDA unavailable",
        ),
        FoodSourceSearchResult(
            source_name="open_food_facts",
            status=SEARCH_STATUS_FAILURE,
            results=[],
            error="OFF unavailable",
        ),
    ]

    result = aggregate_food_search_results(registry, "apple", source_results)

    assert result.status == SEARCH_STATUS_FAILURE
    assert result.results == []
    assert result.error == "All requested food sources failed."
