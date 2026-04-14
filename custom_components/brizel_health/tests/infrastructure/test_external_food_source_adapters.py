"""Tests for fixture-backed external food source adapters."""

from __future__ import annotations

import pytest

from custom_components.brizel_health.domains.nutrition.errors import (
    BrizelImportedFoodValidationError,
)
from custom_components.brizel_health.infrastructure.external_food_sources.bls_adapter import (
    BlsAdapter,
)
from custom_components.brizel_health.infrastructure.external_food_sources.open_food_facts_adapter import (
    OpenFoodFactsAdapter,
)
from custom_components.brizel_health.infrastructure.external_food_sources.usda_adapter import (
    UsdaAdapter,
)


class FakeUsdaClient:
    """Small fake client for live USDA adapter tests."""

    def __init__(self, detail_payload: dict, search_payloads: list[dict]) -> None:
        self._detail_payload = detail_payload
        self._search_payloads = search_payloads

    async def fetch_food_by_id(self, source_id: str, *, api_key: str):
        return self._detail_payload

    async def search_foods(self, query: str, *, api_key: str, limit: int = 10):
        return self._search_payloads[:limit]


class FakeOpenFoodFactsClient:
    """Small fake client for live OFF adapter tests."""

    def __init__(
        self,
        payload: dict | None = None,
        search_payloads: list[dict] | None = None,
    ) -> None:
        self._payload = payload
        self._search_payloads = search_payloads or []

    async def fetch_product_by_barcode(self, barcode: str):
        return self._payload

    async def search_foods(self, query: str, *, limit: int = 10):
        return self._search_payloads[:limit]


@pytest.mark.asyncio
async def test_bls_adapter_maps_local_records_to_imported_food_data() -> None:
    """BLS adapter should map local snapshot rows into importable food data."""
    adapter = BlsAdapter(
        records=[
            {
                "source_id": "BLS123",
                "name": "Gouda",
                "name_en": "Gouda cheese",
                "kcal_per_100g": 356,
                "protein_per_100g": 24,
                "carbs_per_100g": 0.1,
                "fat_per_100g": 28,
                "hydration_ml_per_100g": 42,
            }
        ],
        fetched_at="2026-04-13T08:00:00+00:00",
    )

    imported_food = await adapter.fetch_food_by_id("BLS123")

    assert imported_food is not None
    assert imported_food.source_name == "bls"
    assert imported_food.source_id == "BLS123"
    assert imported_food.name == "Gouda"
    assert imported_food.brand is None
    assert imported_food.kcal_per_100g == 356
    assert imported_food.protein_per_100g == 24
    assert imported_food.carbs_per_100g == 0.1
    assert imported_food.fat_per_100g == 28
    assert imported_food.hydration_ml_per_100g == 42
    assert imported_food.market_country_codes == ("de",)
    assert imported_food.market_region_codes == ("eu",)


@pytest.mark.asyncio
async def test_bls_adapter_searches_de_and_en_names_without_guessing_missing_fields() -> None:
    """BLS adapter should support German and English matches while keeping absent fields empty."""
    adapter = BlsAdapter(
        records=[
            {
                "source_id": "BLS234",
                "name": "Karotte, roh",
                "name_en": "Carrot, raw",
                "kcal_per_100g": 41,
                "protein_per_100g": 0.9,
                "carbs_per_100g": 10,
                "fat_per_100g": 0.2,
                "hydration_ml_per_100g": 88,
            },
            {
                "source_id": "BLS235",
                "name": "Schokoaufstrich",
                "name_en": "Chocolate spread",
                "kcal_per_100g": 510,
                "protein_per_100g": 5.0,
                "carbs_per_100g": 56.0,
                "fat_per_100g": 29.0,
                "hydration_ml_per_100g": None,
            },
        ]
    )

    carrot_results = await adapter.search_foods("Karotte")
    english_results = await adapter.search_foods("carrot")

    assert carrot_results[0].source_id == "BLS234"
    assert english_results[0].source_id == "BLS234"
    assert english_results[0].brand is None
    assert english_results[0].barcode is None


@pytest.mark.asyncio
async def test_open_food_facts_adapter_maps_fixture_to_imported_food_data() -> None:
    """Open Food Facts adapter should map source fixtures into ImportedFoodData."""
    adapter = OpenFoodFactsAdapter(
        {
            "400000000001": {
                "product": {
                    "id": "737628064502",
                    "product_name": "Chocolate Bar",
                    "brands": "Example Brand",
                    "ingredients": [
                        {"text": "Sugar"},
                        {"text": "Cocoa butter"},
                    ],
                    "allergens_tags": ["en:milk"],
                    "labels_tags": ["en:vegan"],
                    "nutriments": {
                        "energy-kcal_100g": 550,
                        "fat_100g": 35,
                        "carbohydrates_100g": 50,
                        "proteins_100g": 5,
                    },
                    "last_modified_t": 1690000000,
                    "countries_tags": ["en:germany"],
                }
            }
        }
    )

    imported_food = await adapter.fetch_food_by_id("400000000001")

    assert imported_food is not None
    assert imported_food.source_name == "open_food_facts"
    assert imported_food.source_id == "737628064502"
    assert imported_food.name == "Chocolate Bar"
    assert imported_food.brand == "Example Brand"
    assert imported_food.kcal_per_100g == 550
    assert imported_food.fat_per_100g == 35
    assert imported_food.carbs_per_100g == 50
    assert imported_food.protein_per_100g == 5
    assert imported_food.ingredients == ("sugar", "cocoa butter")
    assert imported_food.ingredients_known is True
    assert imported_food.allergens == ("milk",)
    assert imported_food.allergens_known is True
    assert imported_food.labels == ("vegan",)
    assert imported_food.labels_known is True
    assert imported_food.hydration_kind is None
    assert imported_food.hydration_ml_per_100g is None
    assert imported_food.barcode == "737628064502"
    assert imported_food.market_country_codes == ("en:germany",)
    assert imported_food.source_updated_at == "2023-07-22T04:26:40+00:00"


@pytest.mark.asyncio
async def test_open_food_facts_adapter_uses_ingredients_text_fallback_and_keeps_unknowns_honest() -> None:
    """OFF adapter should fall back to ingredients_text and keep missing sections unknown."""
    adapter = OpenFoodFactsAdapter(
        {
            "400000000002": {
                "product": {
                    "id": "400000000002",
                    "product_name": "Tomato Soup",
                    "brands": "Example Brand",
                    "ingredients_text": "Tomato, Water, Salt",
                    "nutriments": {
                        "energy-kcal_100g": 40,
                        "fat_100g": 1,
                        "carbohydrates_100g": 7,
                        "proteins_100g": 1,
                    },
                }
            }
        }
    )

    imported_food = await adapter.fetch_food_by_id("400000000002")

    assert imported_food is not None
    assert imported_food.ingredients == ("tomato", "water", "salt")
    assert imported_food.ingredients_known is True
    assert imported_food.allergens == ()
    assert imported_food.allergens_known is False
    assert imported_food.labels == ()
    assert imported_food.labels_known is False
    assert imported_food.market_country_codes == ()
    assert imported_food.barcode == "400000000002"
    assert imported_food.source_updated_at is None


@pytest.mark.asyncio
async def test_usda_adapter_maps_energy_and_water_without_guessing_other_metadata() -> None:
    """USDA adapter should map energy and water while keeping unavailable sections unknown."""
    adapter = UsdaAdapter(
        {
            "123": {
                "fdcId": 123456,
                "description": "Apple, raw",
                "foodNutrients": [
                    {"nutrientName": "Energy", "unitName": "KCAL", "value": 52},
                    {"nutrientName": "Protein", "unitName": "G", "value": 0.3},
                    {
                        "nutrientName": "Carbohydrate, by difference",
                        "unitName": "G",
                        "value": 14,
                    },
                    {"nutrientName": "Total lipid (fat)", "unitName": "G", "value": 0.2},
                    {"nutrientName": "Water", "unitName": "G", "value": 85.6},
                ],
                "publicationDate": "2020-01-01",
            }
        }
    )

    imported_food = await adapter.fetch_food_by_id("123")
    results = await adapter.search_foods("apple")

    assert imported_food is not None
    assert imported_food.source_id == "123456"
    assert imported_food.name == "Apple, raw"
    assert imported_food.kcal_per_100g == 52
    assert imported_food.hydration_ml_per_100g == 85.6
    assert imported_food.hydration_kind is None
    assert imported_food.ingredients_known is False
    assert imported_food.allergens_known is False
    assert imported_food.labels_known is False
    assert imported_food.source_updated_at == "2020-01-01T00:00:00+00:00"
    assert [result.source_id for result in results] == ["123456"]
    assert results[0].kcal_per_100g == 52
    assert results[0].hydration_ml_per_100g == 85.6
    assert results[0].market_country_codes == ("us",)
    assert results[0].market_region_codes == ("na",)


@pytest.mark.asyncio
async def test_usda_adapter_normalizes_non_iso_publication_dates() -> None:
    """USDA adapter should normalize live date strings before ImportedFoodData validation."""
    adapter = UsdaAdapter(
        {
            "125": {
                "fdcId": 125,
                "description": "Banana, raw",
                "foodNutrients": [
                    {"nutrientName": "Energy", "unitName": "KCAL", "value": 89},
                    {"nutrientName": "Protein", "unitName": "G", "value": 1.1},
                    {
                        "nutrientName": "Carbohydrate, by difference",
                        "unitName": "G",
                        "value": 22.8,
                    },
                    {"nutrientName": "Total lipid (fat)", "unitName": "G", "value": 0.3},
                ],
                "publicationDate": "04/16/2020",
            }
        }
    )

    imported_food = await adapter.fetch_food_by_id("125")

    assert imported_food is not None
    assert imported_food.source_updated_at == "2020-04-16T00:00:00+00:00"


@pytest.mark.asyncio
async def test_usda_adapter_keeps_hydration_unknown_when_water_is_missing() -> None:
    """USDA adapter should leave hydration unknown when no Water nutrient is present."""
    adapter = UsdaAdapter(
        {
            "124": {
                "fdcId": 124,
                "description": "Rice, cooked",
                "foodNutrients": [
                    {"nutrientName": "Energy", "unitName": "KCAL", "value": 130},
                    {"nutrientName": "Protein", "unitName": "G", "value": 2.7},
                    {
                        "nutrientName": "Carbohydrate, by difference",
                        "unitName": "G",
                        "value": 28.2,
                    },
                    {"nutrientName": "Total lipid (fat)", "unitName": "G", "value": 0.3},
                ],
                "publicationDate": "2020-02-01",
            }
        }
    )

    imported_food = await adapter.fetch_food_by_id("124")

    assert imported_food is not None
    assert imported_food.kcal_per_100g == 130
    assert imported_food.hydration_ml_per_100g is None
    assert imported_food.hydration_kind is None
    assert imported_food.labels_known is False
    assert imported_food.ingredients_known is False
    assert imported_food.allergens_known is False


@pytest.mark.asyncio
async def test_usda_adapter_can_use_live_client_with_api_key() -> None:
    """USDA adapter should support the live client path without changing its mapping rules."""
    adapter = UsdaAdapter(
        client=FakeUsdaClient(
            detail_payload={
                "fdcId": 123456,
                "description": "Apple, raw",
                "brandOwner": "USDA",
                "foodNutrients": [
                    {
                        "amount": 52,
                        "nutrient": {
                            "name": "Energy",
                            "unitName": "KCAL",
                        },
                    },
                    {
                        "amount": 0.3,
                        "nutrient": {
                            "name": "Protein",
                            "unitName": "G",
                        },
                    },
                    {
                        "amount": 14,
                        "nutrient": {
                            "name": "Carbohydrate, by difference",
                            "unitName": "G",
                        },
                    },
                    {
                        "amount": 0.2,
                        "nutrient": {
                            "name": "Total lipid (fat)",
                            "unitName": "G",
                        },
                    },
                    {
                        "amount": 85.6,
                        "nutrient": {
                            "name": "Water",
                            "unitName": "G",
                        },
                    },
                ],
                "publicationDate": "2020-01-01",
            },
            search_payloads=[
                {
                    "fdcId": 123456,
                    "description": "Apple, raw",
                    "brandOwner": "USDA",
                    "foodNutrients": [
                        {"name": "Energy", "unitName": "KCAL", "amount": 52},
                        {"name": "Protein", "unitName": "G", "amount": 0.3},
                        {
                            "name": "Carbohydrate, by difference",
                            "unitName": "G",
                            "amount": 14,
                        },
                        {
                            "name": "Total lipid (fat)",
                            "unitName": "G",
                            "amount": 0.2,
                        },
                        {"name": "Water", "unitName": "G", "amount": 85.6},
                    ],
                }
            ],
        ),
        api_key="demo-key",
    )

    imported_food = await adapter.fetch_food_by_id("123456")
    search_results = await adapter.search_foods("apple")

    assert imported_food is not None
    assert imported_food.source_id == "123456"
    assert imported_food.kcal_per_100g == 52
    assert imported_food.protein_per_100g == 0.3
    assert imported_food.carbs_per_100g == 14
    assert imported_food.fat_per_100g == 0.2
    assert imported_food.hydration_ml_per_100g == 85.6
    assert search_results[0].source_name == "usda"
    assert search_results[0].source_id == "123456"
    assert search_results[0].kcal_per_100g == imported_food.kcal_per_100g
    assert search_results[0].protein_per_100g == imported_food.protein_per_100g
    assert search_results[0].carbs_per_100g == imported_food.carbs_per_100g
    assert search_results[0].fat_per_100g == imported_food.fat_per_100g


@pytest.mark.asyncio
async def test_usda_adapter_raises_clear_error_when_detail_macros_are_incomplete() -> None:
    """USDA detail imports should fail clearly if required macros are missing."""
    adapter = UsdaAdapter(
        client=FakeUsdaClient(
            detail_payload={
                "fdcId": 123456,
                "description": "Apple, raw",
                "foodNutrients": [
                    {
                        "amount": 52,
                        "nutrient": {
                            "name": "Energy",
                            "unitName": "KCAL",
                        },
                    },
                    {
                        "amount": 0.3,
                        "nutrient": {
                            "name": "Protein",
                            "unitName": "G",
                        },
                    },
                ],
                "publicationDate": "2020-01-01",
            },
            search_payloads=[],
        ),
        api_key="demo-key",
    )

    with pytest.raises(
        BrizelImportedFoodValidationError,
        match="USDA detail response did not provide complete kcal, protein, carbs and fat values per 100g.",
    ):
        await adapter.fetch_food_by_id("123456")


@pytest.mark.asyncio
async def test_open_food_facts_adapter_can_use_live_lookup_client() -> None:
    """OFF adapter should support live barcode lookup without enabling live search."""
    adapter = OpenFoodFactsAdapter(
        client=FakeOpenFoodFactsClient(
            {
                "code": "3017624010701",
                "status": 1,
                "product": {
                    "id": "3017624010701",
                    "product_name": "Nutella",
                    "brands": "Ferrero",
                    "allergens_tags": ["en:milk"],
                    "labels_tags": [],
                    "nutriments": {
                        "energy-kcal_100g": 539,
                        "fat_100g": 30.9,
                        "carbohydrates_100g": 57.5,
                        "proteins_100g": 6.3,
                    },
                    "last_modified_t": 1690000000,
                    "countries_tags": ["en:germany"],
                },
            }
        )
    )

    imported_food = await adapter.fetch_food_by_id("3017624010701")

    assert imported_food is not None
    assert imported_food.source_id == "3017624010701"
    assert imported_food.name == "Nutella"
    assert imported_food.allergens == ("milk",)
    assert imported_food.barcode == "3017624010701"


@pytest.mark.asyncio
async def test_open_food_facts_adapter_can_use_live_search_client() -> None:
    """OFF adapter should support live text search and normalize results safely."""
    adapter = OpenFoodFactsAdapter(
        client=FakeOpenFoodFactsClient(
            search_payloads=[
                {
                    "code": "5449000000996",
                    "product_name": "Coca-Cola Original Taste",
                    "brands": "Coca-Cola",
                    "nutriments": {
                        "energy-kcal_100g": 42,
                        "fat_100g": 0,
                        "carbohydrates_100g": 10.6,
                        "proteins_100g": 0,
                    },
                    "last_modified_t": 1690000000,
                },
                {
                    "code": "",
                    "product_name": "",
                    "brands": "Broken Product",
                    "nutriments": {},
                },
            ]
        )
    )

    results = await adapter.search_foods("coca", limit=5)

    assert len(results) == 1
    assert results[0].source_name == "open_food_facts"
    assert results[0].source_id == "5449000000996"
    assert results[0].barcode == "5449000000996"
    assert results[0].name == "Coca-Cola Original Taste"
    assert results[0].brand == "Coca-Cola"
    assert results[0].kcal_per_100g == 42
    assert results[0].market_country_codes == ()
