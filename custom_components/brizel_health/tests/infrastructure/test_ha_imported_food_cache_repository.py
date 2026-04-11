"""Tests for the imported food cache repository."""

from __future__ import annotations

import pytest

from custom_components.brizel_health.domains.nutrition.models.imported_food_cache_entry import (
    ImportedFoodCacheEntry,
)
from custom_components.brizel_health.domains.nutrition.models.imported_food_data import (
    ImportedFoodData,
)
from custom_components.brizel_health.infrastructure.repositories.ha_imported_food_cache_repository import (
    HomeAssistantImportedFoodCacheRepository,
)


class FakeStoreManager:
    """Minimal store manager stub for imported food cache tests."""

    def __init__(self, data: dict) -> None:
        self.data = data
        self.save_calls = 0

    async def async_save(self) -> None:
        self.save_calls += 1


def test_repository_reads_cached_imported_food_by_source_ref() -> None:
    """Repository should read cached imported food snapshots by source reference."""
    repository = HomeAssistantImportedFoodCacheRepository(
        FakeStoreManager(
            {
                "nutrition": {
                    "imported_food_cache": {
                        "open_food_facts": {
                            "off-1": {
                                "source_name": "open_food_facts",
                                "source_id": "off-1",
                                "food_id": "food-1",
                                "last_synced_at": "2026-04-05T10:00:00+00:00",
                                "imported_food": {
                                    "source_name": "open_food_facts",
                                    "source_id": "off-1",
                                    "name": "Mineral Water",
                                    "brand": "Brizel",
                                    "barcode": "400000000001",
                                    "kcal_per_100g": 0,
                                    "protein_per_100g": 0,
                                    "carbs_per_100g": 0,
                                    "fat_per_100g": 0,
                                    "labels_known": True,
                                    "labels": ["vegan"],
                                    "ingredients_known": False,
                                    "allergens_known": False,
                                    "market_country_codes": ["en:germany"],
                                    "market_region_codes": [],
                                    "fetched_at": "2026-04-05T10:00:00+00:00",
                                },
                            }
                        }
                    }
                }
            }
        )
    )

    cache_entry = repository.get_by_source_ref("open_food_facts", "off-1")

    assert cache_entry is not None
    assert cache_entry.food_id == "food-1"
    assert cache_entry.imported_food.name == "Mineral Water"
    assert cache_entry.imported_food.market_country_codes == ("en:germany",)


@pytest.mark.asyncio
async def test_repository_upsert_persists_cache_entry_in_nested_storage_shape() -> None:
    """Repository should persist imported cache entries by source name and source ID."""
    store_manager = FakeStoreManager({"nutrition": {}})
    repository = HomeAssistantImportedFoodCacheRepository(store_manager)
    imported_food = ImportedFoodData.create(
        source_name="usda",
        source_id="123",
        name="Greek Yogurt",
        brand="Sample Dairy",
        barcode="012345678905",
        kcal_per_100g=97,
        protein_per_100g=9,
        carbs_per_100g=3.9,
        fat_per_100g=5,
        allergens=["milk"],
        allergens_known=True,
        fetched_at="2026-04-05T10:00:00+00:00",
    )
    imported_food_cache_entry = ImportedFoodCacheEntry.create(
        source_name="usda",
        source_id="123",
        food_id="food-1",
        imported_food=imported_food,
    )

    cache_entry = await repository.upsert(imported_food_cache_entry)

    assert cache_entry.food_id == "food-1"
    assert store_manager.data["nutrition"]["imported_food_cache"]["usda"]["123"] == (
        imported_food_cache_entry.to_dict()
    )
    assert store_manager.save_calls == 1
