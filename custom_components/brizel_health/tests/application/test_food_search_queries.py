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
from custom_components.brizel_health.application.nutrition.search_context import (
    build_food_search_context,
)
from custom_components.brizel_health.application.nutrition.search_intelligence import (
    normalize_search_text_for_matching,
)
from custom_components.brizel_health.application.nutrition.source_registry import (
    FoodSourceRegistry,
)
from custom_components.brizel_health.domains.nutrition.models.external_food_search_result import (
    ExternalFoodSearchResult,
)
from custom_components.brizel_health.infrastructure.external_food_sources.bls_adapter import (
    BlsAdapter,
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

        normalized_query = normalize_search_text_for_matching(query)
        return [
            result
            for result in self._results
            if normalized_query in normalize_search_text_for_matching(result.name)
            or normalized_query in normalize_search_text_for_matching(result.brand or "")
        ][:limit]


class QuerySensitiveSearchAdapter:
    """Adapter stub returning different results per normalized query."""

    def __init__(
        self,
        source_name: str,
        results_by_query: dict[str, list[ExternalFoodSearchResult]],
    ) -> None:
        self.source_name = source_name
        self._results_by_query = {
            normalize_search_text_for_matching(query): results
            for query, results in results_by_query.items()
        }

    async def fetch_food_by_id(self, source_id: str):
        return None

    async def search_foods(
        self,
        query: str,
        limit: int = 10,
    ) -> list[ExternalFoodSearchResult]:
        normalized_query = normalize_search_text_for_matching(query)
        return list(self._results_by_query.get(normalized_query, []))[:limit]


def _germany_context():
    """Build one conservative Germany search context for ranking tests."""
    return build_food_search_context(
        profile_id="profile-de",
        profile=None,
        hass_language="de-DE",
        hass_time_zone="Europe/Berlin",
        hass_country="DE",
        hass_units_hint="metric",
        recent_foods=None,
    )


def _usa_context():
    """Build one conservative USA search context for regression tests."""
    return build_food_search_context(
        profile_id=None,
        profile=None,
        hass_language="en-US",
        hass_time_zone="America/New_York",
        hass_country="US",
        hass_units_hint=None,
        recent_foods=None,
    )


def _eu_context():
    """Build one conservative EU search context for ranking tests."""
    return build_food_search_context(
        profile_id=None,
        profile=None,
        hass_language="en-GB",
        hass_time_zone="Europe/Amsterdam",
        hass_country="NL",
        hass_units_hint="metric",
        recent_foods=None,
    )


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
                    market_country_codes=["us"],
                    market_region_codes=["na"],
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
                    market_country_codes=["en:germany"],
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
async def test_search_foods_from_sources_aggregated_uses_language_fallbacks() -> None:
    """A German query should still find an English source result through search intelligence."""
    registry = FoodSourceRegistry()
    registry.register_source(
        "usda",
        FixtureSearchAdapter(
            "usda",
            [
                ExternalFoodSearchResult.create(
                    source_name="usda",
                    source_id="usda-apple",
                    name="Apple, raw",
                    kcal_per_100g=52,
                    market_country_codes=["us"],
                    market_region_codes=["na"],
                )
            ],
        ),
        enabled=True,
        priority=10,
    )

    result = await search_foods_from_sources_aggregated(registry, "Apfel")

    assert result.status == SEARCH_STATUS_SUCCESS
    assert [item.source_id for item in result.results] == ["usda-apple"]


@pytest.mark.asyncio
async def test_search_foods_from_sources_aggregated_deduplicates_hits_found_via_multiple_variants() -> None:
    """The same source item should not appear multiple times when several variants match it."""
    registry = FoodSourceRegistry()
    registry.register_source(
        "open_food_facts",
        FixtureSearchAdapter(
            "open_food_facts",
            [
                ExternalFoodSearchResult.create(
                    source_name="open_food_facts",
                    source_id="off-roll",
                    name="Bread Roll",
                    brand="Bakery",
                    kcal_per_100g=260,
                    market_country_codes=["en:germany"],
                )
            ],
        ),
        enabled=True,
        priority=20,
    )

    result = await search_foods_from_sources_aggregated(registry, "Br\u00f6tchen")

    assert result.status == SEARCH_STATUS_SUCCESS
    assert [item.source_id for item in result.results] == ["off-roll"]


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


@pytest.mark.asyncio
async def test_germany_context_prefers_german_market_gouda_results() -> None:
    """Germany-first ranking should lift sensible German/EU Gouda hits above US-brand noise."""
    registry = FoodSourceRegistry()
    registry.register_source(
        "usda",
        FixtureSearchAdapter(
            "usda",
            [
                ExternalFoodSearchResult.create(
                    source_name="usda",
                    source_id="us-gouda-snack",
                    name="Smoked Gouda Snack Bites",
                    brand="Texas Joe's",
                    kcal_per_100g=410,
                    protein_per_100g=14,
                    carbs_per_100g=18,
                    fat_per_100g=32,
                    market_country_codes=["us"],
                    market_region_codes=["na"],
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
                    source_id="de-gouda",
                    name="Gouda jung",
                    brand="ja!",
                    kcal_per_100g=356,
                    protein_per_100g=24,
                    carbs_per_100g=0.1,
                    fat_per_100g=28,
                    market_country_codes=["en:germany"],
                    market_region_codes=["eu"],
                )
            ],
        ),
        enabled=True,
        priority=20,
    )

    result = await search_foods_from_sources_aggregated(
        registry,
        "Gouda",
        search_context=_germany_context(),
    )

    assert result.status == SEARCH_STATUS_SUCCESS
    assert [item.source_id for item in result.results] == ["de-gouda", "us-gouda-snack"]


@pytest.mark.asyncio
async def test_germany_context_prefers_bls_for_generic_gouda_queries() -> None:
    """Germany-context generic queries should lift BLS above OFF and USDA noise."""
    registry = FoodSourceRegistry()
    registry.register_source(
        "bls",
        BlsAdapter(
            records=[
                {
                    "source_id": "bls-gouda",
                    "name": "Gouda",
                    "name_en": "Gouda cheese",
                    "kcal_per_100g": 356,
                    "protein_per_100g": 24.0,
                    "carbs_per_100g": 0.1,
                    "fat_per_100g": 28.0,
                    "hydration_ml_per_100g": 42.0,
                }
            ]
        ),
        enabled=True,
        priority=15,
    )
    registry.register_source(
        "open_food_facts",
        FixtureSearchAdapter(
            "open_food_facts",
            [
                ExternalFoodSearchResult.create(
                    source_name="open_food_facts",
                    source_id="off-gouda",
                    name="Gouda jung",
                    brand="ja!",
                    kcal_per_100g=356,
                    protein_per_100g=24,
                    carbs_per_100g=0.1,
                    fat_per_100g=28,
                    market_country_codes=["en:germany"],
                    market_region_codes=["eu"],
                )
            ],
        ),
        enabled=True,
        priority=20,
    )
    registry.register_source(
        "usda",
        FixtureSearchAdapter(
            "usda",
            [
                ExternalFoodSearchResult.create(
                    source_name="usda",
                    source_id="us-gouda-snack",
                    name="Smoked Gouda Snack Bites",
                    brand="Texas Joe's",
                    kcal_per_100g=410,
                    protein_per_100g=14,
                    carbs_per_100g=18,
                    fat_per_100g=32,
                    market_country_codes=["us"],
                    market_region_codes=["na"],
                )
            ],
        ),
        enabled=True,
        priority=10,
    )

    result = await search_foods_from_sources_aggregated(
        registry,
        "Gouda",
        search_context=_germany_context(),
    )

    assert result.status == SEARCH_STATUS_SUCCESS
    assert [item.source_id for item in result.results] == [
        "bls-gouda",
        "off-gouda",
        "us-gouda-snack",
    ]


@pytest.mark.asyncio
async def test_germany_context_prefers_exact_german_brand_product_matches() -> None:
    """German brand/product queries should prefer exact phrase and brand hits."""
    registry = FoodSourceRegistry()
    registry.register_source(
        "usda",
        FixtureSearchAdapter(
            "usda",
            [
                ExternalFoodSearchResult.create(
                    source_name="usda",
                    source_id="us-country-bar",
                    name="Country Chocolate Bar",
                    brand="Sweet Valley",
                    kcal_per_100g=520,
                    protein_per_100g=6,
                    carbs_per_100g=58,
                    fat_per_100g=29,
                    market_country_codes=["us"],
                    market_region_codes=["na"],
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
                    source_id="off-kinder-country",
                    name="Kinder Country",
                    brand="Kinder",
                    kcal_per_100g=560,
                    protein_per_100g=8,
                    carbs_per_100g=52,
                    fat_per_100g=35,
                    market_country_codes=["en:germany"],
                    market_region_codes=["eu"],
                )
            ],
        ),
        enabled=True,
        priority=20,
    )

    result = await search_foods_from_sources_aggregated(
        registry,
        "Kinder Country",
        search_context=_germany_context(),
    )

    assert result.status == SEARCH_STATUS_SUCCESS
    assert result.results[0].source_id == "off-kinder-country"


@pytest.mark.asyncio
async def test_germany_context_prefers_generic_food_for_moehre_queries() -> None:
    """Generic German food queries should not default to branded products."""
    registry = FoodSourceRegistry()
    registry.register_source(
        "usda",
        FixtureSearchAdapter(
            "usda",
            [
                ExternalFoodSearchResult.create(
                    source_name="usda",
                    source_id="us-carrot-snack",
                    name="Carrot Cake Snack",
                    brand="US Treats",
                    kcal_per_100g=420,
                    protein_per_100g=4,
                    carbs_per_100g=55,
                    fat_per_100g=20,
                    market_country_codes=["us"],
                    market_region_codes=["na"],
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
                        source_id="off-moehre",
                        name="Möhre, roh",
                        brand=None,
                        kcal_per_100g=41,
                        protein_per_100g=0.9,
                        carbs_per_100g=10,
                    fat_per_100g=0.2,
                    market_country_codes=["en:germany"],
                    market_region_codes=["eu"],
                )
            ],
        ),
        enabled=True,
        priority=20,
    )

    result = await search_foods_from_sources_aggregated(
        registry,
        "M\u00f6hre",
        search_context=_germany_context(),
    )

    assert result.status == SEARCH_STATUS_SUCCESS
    assert result.results[0].source_id == "off-moehre"


@pytest.mark.asyncio
async def test_germany_context_lets_bls_cover_generic_moehre_queries() -> None:
    """BLS should provide a strong generic result for German carrot queries."""
    registry = FoodSourceRegistry()
    registry.register_source(
        "bls",
        BlsAdapter(
            records=[
                {
                    "source_id": "bls-karotte",
                    "name": "Karotte, roh",
                    "name_en": "Carrot, raw",
                    "kcal_per_100g": 41,
                    "protein_per_100g": 0.9,
                    "carbs_per_100g": 10,
                    "fat_per_100g": 0.2,
                    "hydration_ml_per_100g": 88.0,
                }
            ]
        ),
        enabled=True,
        priority=15,
    )
    registry.register_source(
        "usda",
        FixtureSearchAdapter(
            "usda",
            [
                ExternalFoodSearchResult.create(
                    source_name="usda",
                    source_id="us-carrot-snack",
                    name="Carrot Cake Snack",
                    brand="US Treats",
                    kcal_per_100g=420,
                    protein_per_100g=4,
                    carbs_per_100g=55,
                    fat_per_100g=20,
                    market_country_codes=["us"],
                    market_region_codes=["na"],
                )
            ],
        ),
        enabled=True,
        priority=10,
    )

    result = await search_foods_from_sources_aggregated(
        registry,
        "M\u00f6hre",
        search_context=_germany_context(),
    )

    assert result.status == SEARCH_STATUS_SUCCESS
    assert result.results[0].source_id == "bls-karotte"


@pytest.mark.asyncio
async def test_usa_context_keeps_usda_results_viable() -> None:
    """USA-context searches should continue to behave sensibly for USDA-backed queries."""
    registry = FoodSourceRegistry()
    registry.register_source(
        "usda",
        FixtureSearchAdapter(
            "usda",
            [
                ExternalFoodSearchResult.create(
                    source_name="usda",
                    source_id="us-apple",
                    name="Apple, raw",
                    kcal_per_100g=52,
                    market_country_codes=["us"],
                    market_region_codes=["na"],
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
                    source_id="eu-apple",
                    name="Apple Juice",
                    brand="Brizel",
                    kcal_per_100g=46,
                    market_country_codes=["en:germany"],
                    market_region_codes=["eu"],
                )
            ],
        ),
        enabled=True,
        priority=20,
    )

    result = await search_foods_from_sources_aggregated(
        registry,
        "apple",
        search_context=_usa_context(),
    )

    assert result.status == SEARCH_STATUS_SUCCESS
    assert result.results[0].source_id == "us-apple"


@pytest.mark.asyncio
async def test_usa_context_prefers_usda_over_bls_for_generic_apple_queries() -> None:
    """USA-context generic queries should keep USDA above BLS."""
    registry = FoodSourceRegistry()
    registry.register_source(
        "bls",
        BlsAdapter(
            records=[
                {
                    "source_id": "bls-apfel",
                    "name": "Apfel, roh",
                    "name_en": "Apple, raw",
                    "kcal_per_100g": 52,
                    "protein_per_100g": 0.3,
                    "carbs_per_100g": 14,
                    "fat_per_100g": 0.2,
                    "hydration_ml_per_100g": 85.6,
                }
            ]
        ),
        enabled=True,
        priority=15,
    )
    registry.register_source(
        "usda",
        FixtureSearchAdapter(
            "usda",
            [
                ExternalFoodSearchResult.create(
                    source_name="usda",
                    source_id="us-apple",
                    name="Apple, raw",
                    kcal_per_100g=52,
                    market_country_codes=["us"],
                    market_region_codes=["na"],
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
                    source_id="off-apple",
                    name="Apple Juice",
                    brand="Brizel",
                    kcal_per_100g=46,
                    market_country_codes=["en:germany"],
                    market_region_codes=["eu"],
                )
            ],
        ),
        enabled=True,
        priority=20,
    )

    result = await search_foods_from_sources_aggregated(
        registry,
        "apple",
        search_context=_usa_context(),
    )

    assert result.status == SEARCH_STATUS_SUCCESS
    assert result.results[0].source_id == "us-apple"


@pytest.mark.asyncio
async def test_product_queries_keep_off_high_globally() -> None:
    """OFF should stay the primary product source outside pure Germany-specific logic."""
    registry = FoodSourceRegistry()
    registry.register_source(
        "bls",
        BlsAdapter(
            records=[
                {
                    "source_id": "bls-cocoa-spread",
                    "name": "Schokoaufstrich",
                    "name_en": "Chocolate spread",
                    "kcal_per_100g": 510,
                    "protein_per_100g": 5.0,
                    "carbs_per_100g": 56.0,
                    "fat_per_100g": 29.0,
                    "hydration_ml_per_100g": 8.0,
                }
            ]
        ),
        enabled=True,
        priority=15,
    )
    registry.register_source(
        "open_food_facts",
        FixtureSearchAdapter(
            "open_food_facts",
            [
                ExternalFoodSearchResult.create(
                    source_name="open_food_facts",
                    source_id="off-nutella",
                    name="Nutella",
                    brand="Ferrero",
                    kcal_per_100g=539,
                    protein_per_100g=6.3,
                    carbs_per_100g=57.5,
                    fat_per_100g=30.9,
                    market_country_codes=["en:france"],
                    market_region_codes=["eu"],
                )
            ],
        ),
        enabled=True,
        priority=20,
    )

    result = await search_foods_from_sources_aggregated(
        registry,
        "Nutella",
        search_context=_eu_context(),
    )

    assert result.status == SEARCH_STATUS_SUCCESS
    assert result.results[0].source_id == "off-nutella"


@pytest.mark.asyncio
async def test_brand_product_queries_can_fall_back_to_brand_without_losing_exact_product() -> None:
    """A product phrase should still find the exact OFF product if the upstream search only matches the brand."""
    registry = FoodSourceRegistry()
    registry.register_source(
        "open_food_facts",
        QuerySensitiveSearchAdapter(
            "open_food_facts",
            {
                "kinder": [
                    ExternalFoodSearchResult.create(
                        source_name="open_food_facts",
                        source_id="off-kinder-country",
                        name="Kinder Country",
                        brand="Kinder",
                        kcal_per_100g=560,
                        protein_per_100g=8,
                        carbs_per_100g=52,
                        fat_per_100g=35,
                        market_country_codes=["en:germany"],
                        market_region_codes=["eu"],
                    )
                ],
                "kinder country": [],
            },
        ),
        enabled=True,
        priority=20,
    )
    registry.register_source(
        "usda",
        QuerySensitiveSearchAdapter(
            "usda",
            {
                "kinder country": [
                    ExternalFoodSearchResult.create(
                        source_name="usda",
                        source_id="us-country-bar",
                        name="Country Chocolate Bar",
                        brand="Sweet Valley",
                        kcal_per_100g=520,
                        protein_per_100g=6,
                        carbs_per_100g=58,
                        fat_per_100g=29,
                        market_country_codes=["us"],
                        market_region_codes=["na"],
                    )
                ]
            },
        ),
        enabled=True,
        priority=10,
    )

    result = await search_foods_from_sources_aggregated(
        registry,
        "Kinder Country",
        search_context=_germany_context(),
    )

    assert result.status == SEARCH_STATUS_SUCCESS
    assert result.results[0].source_id == "off-kinder-country"


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
