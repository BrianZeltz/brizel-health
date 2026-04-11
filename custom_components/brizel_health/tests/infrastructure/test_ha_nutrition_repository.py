"""Tests for the Home Assistant nutrition repository."""

from __future__ import annotations

import pytest

from custom_components.brizel_health.domains.nutrition.errors import (
    BrizelFoodNotFoundError,
)
from custom_components.brizel_health.domains.nutrition.models.food import Food
from custom_components.brizel_health.domains.nutrition.models.food_compatibility import (
    FoodCompatibilityMetadata,
)
from custom_components.brizel_health.infrastructure.repositories.ha_nutrition_repository import (
    HomeAssistantNutritionRepository,
)


class FakeStoreManager:
    """Minimal store manager stub for repository tests."""

    def __init__(self, data: dict) -> None:
        self.data = data
        self.save_calls = 0

    async def async_save(self) -> None:
        self.save_calls += 1


def test_repository_reads_food_from_legacy_storage_shape() -> None:
    """Repository reads foods from nutrition.foods without reshaping storage."""
    repository = HomeAssistantNutritionRepository(
        FakeStoreManager(
            {
                "nutrition": {
                    "foods": {
                        "food-1": {
                            "food_id": "food-1",
                            "name": "Apple",
                            "brand": "Orchard",
                            "barcode": "12345",
                            "kcal_per_100g": 52,
                            "protein_per_100g": 0.3,
                            "carbs_per_100g": 14,
                            "fat_per_100g": 0.2,
                            "created_at": "2026-04-04T10:00:00+00:00",
                        }
                    }
                }
            }
        )
    )

    food = repository.get_food_by_id("food-1")

    assert food.food_id == "food-1"
    assert food.name == "Apple"
    assert food.to_dict()["barcode"] == "12345"


def test_repository_reads_hydration_metadata_from_legacy_storage_shape() -> None:
    """Repository should preserve hydration metadata when present in stored foods."""
    repository = HomeAssistantNutritionRepository(
        FakeStoreManager(
            {
                "nutrition": {
                    "foods": {
                        "food-watermelon": {
                            "food_id": "food-watermelon",
                            "name": "Watermelon",
                            "brand": None,
                            "barcode": None,
                            "kcal_per_100g": 30,
                            "protein_per_100g": 0.6,
                            "carbs_per_100g": 7.6,
                            "fat_per_100g": 0.2,
                            "hydration_kind": "food",
                            "hydration_ml_per_100g": 91,
                            "hydration_source": "explicit",
                            "created_at": "2026-04-04T10:00:00+00:00",
                        }
                    }
                }
            }
        )
    )

    food = repository.get_food_by_id("food-watermelon")

    assert food.hydration_kind == "food"
    assert food.hydration_ml_per_100g == 91
    assert food.hydration_source == "explicit"


def test_repository_reads_food_compatibility_metadata_from_storage_shape() -> None:
    """Repository should preserve compatibility metadata when it is stored on foods."""
    repository = HomeAssistantNutritionRepository(
        FakeStoreManager(
            {
                "nutrition": {
                    "foods": {
                        "food-1": {
                            "food_id": "food-1",
                            "name": "Salad",
                            "brand": "Brizel",
                            "barcode": None,
                            "kcal_per_100g": 42,
                            "protein_per_100g": 1.2,
                            "carbs_per_100g": 7.5,
                            "fat_per_100g": 1.0,
                            "compatibility": {
                                "labels_known": True,
                                "labels": ["vegan"],
                                "allergens_known": True,
                                "allergens": [],
                                "source": "imported",
                            },
                            "created_at": "2026-04-04T10:00:00+00:00",
                        }
                    }
                }
            }
        )
    )

    food = repository.get_food_by_id("food-1")

    assert food.compatibility is not None
    assert food.compatibility.labels == ("vegan",)
    assert food.compatibility.allergens_known is True
    assert food.compatibility.source == "imported"


def test_repository_lists_all_foods_from_legacy_storage_shape() -> None:
    """Repository returns all foods from nutrition.foods."""
    repository = HomeAssistantNutritionRepository(
        FakeStoreManager(
            {
                "nutrition": {
                    "foods": {
                        "food-1": {
                            "food_id": "food-1",
                            "name": "Apple",
                            "brand": None,
                            "barcode": None,
                            "kcal_per_100g": 52,
                            "protein_per_100g": 0.3,
                            "carbs_per_100g": 14,
                            "fat_per_100g": 0.2,
                            "created_at": "2026-04-04T10:00:00+00:00",
                        },
                        "food-2": {
                            "food_id": "food-2",
                            "name": "Rice",
                            "brand": "Brizel",
                            "barcode": "67890",
                            "kcal_per_100g": 130,
                            "protein_per_100g": 2.7,
                            "carbs_per_100g": 28,
                            "fat_per_100g": 0.3,
                            "created_at": "2026-04-04T11:00:00+00:00",
                        },
                    }
                }
            }
        )
    )

    foods = repository.get_all_foods()

    assert [food.food_id for food in foods] == ["food-1", "food-2"]


def test_repository_raises_not_found_for_unknown_food() -> None:
    """Repository keeps the legacy not-found behavior."""
    repository = HomeAssistantNutritionRepository(
        FakeStoreManager({"nutrition": {"foods": {}}})
    )

    with pytest.raises(BrizelFoodNotFoundError):
        repository.get_food_by_id("missing-food")


@pytest.mark.asyncio
async def test_repository_add_persists_food_in_legacy_storage_shape() -> None:
    """Repository writes new foods into nutrition.foods."""
    store_manager = FakeStoreManager({"nutrition": {"foods": {}}})
    repository = HomeAssistantNutritionRepository(store_manager)

    food = await repository.add(
        Food.from_dict(
            {
                "food_id": "food-1",
                "name": "Apple",
                "brand": "Orchard",
                "barcode": "12345",
                "kcal_per_100g": 52,
                "protein_per_100g": 0.3,
                "carbs_per_100g": 14,
                "fat_per_100g": 0.2,
                "created_at": "2026-04-04T10:00:00+00:00",
            }
        )
    )

    assert store_manager.data["nutrition"]["foods"]["food-1"]["name"] == "Apple"
    assert food.food_id == "food-1"
    assert store_manager.save_calls == 1


@pytest.mark.asyncio
async def test_repository_update_persists_changed_food() -> None:
    """Repository updates existing foods inside nutrition.foods."""
    store_manager = FakeStoreManager(
        {
            "nutrition": {
                "foods": {
                    "food-1": {
                        "food_id": "food-1",
                        "name": "Apple",
                        "brand": "Orchard",
                        "barcode": "12345",
                        "kcal_per_100g": 52,
                        "protein_per_100g": 0.3,
                        "carbs_per_100g": 14,
                        "fat_per_100g": 0.2,
                        "created_at": "2026-04-04T10:00:00+00:00",
                    }
                }
            }
        }
    )
    repository = HomeAssistantNutritionRepository(store_manager)
    food = repository.get_food_by_id("food-1")
    food.update(
        name="Apple Premium",
        brand="Orchard",
        barcode="12345",
        kcal_per_100g=55,
        protein_per_100g=0.4,
        carbs_per_100g=15,
        fat_per_100g=0.2,
    )

    updated = await repository.update(food)

    assert updated.name == "Apple Premium"
    assert store_manager.data["nutrition"]["foods"]["food-1"]["name"] == "Apple Premium"
    assert store_manager.save_calls == 1


@pytest.mark.asyncio
async def test_repository_update_persists_hydration_metadata() -> None:
    """Repository updates should keep hydration metadata in the legacy food storage."""
    store_manager = FakeStoreManager(
        {
            "nutrition": {
                "foods": {
                    "food-1": {
                        "food_id": "food-1",
                        "name": "Cucumber",
                        "brand": None,
                        "barcode": None,
                        "kcal_per_100g": 15,
                        "protein_per_100g": 0.7,
                        "carbs_per_100g": 3.6,
                        "fat_per_100g": 0.1,
                        "created_at": "2026-04-04T10:00:00+00:00",
                    }
                }
            }
        }
    )
    repository = HomeAssistantNutritionRepository(store_manager)
    food = repository.get_food_by_id("food-1")
    food.set_hydration_metadata(
        hydration_kind="food",
        hydration_ml_per_100g=95,
        hydration_source="explicit",
    )

    await repository.update(food)

    assert store_manager.data["nutrition"]["foods"]["food-1"] == {
        "food_id": "food-1",
        "name": "Cucumber",
        "brand": None,
        "barcode": None,
        "kcal_per_100g": 15.0,
        "protein_per_100g": 0.7,
        "carbs_per_100g": 3.6,
        "fat_per_100g": 0.1,
        "hydration_kind": "food",
        "hydration_ml_per_100g": 95.0,
        "hydration_source": "explicit",
        "created_at": "2026-04-04T10:00:00+00:00",
    }


@pytest.mark.asyncio
async def test_repository_update_persists_food_compatibility_metadata() -> None:
    """Repository updates should keep compatibility metadata in food storage."""
    store_manager = FakeStoreManager(
        {
            "nutrition": {
                "foods": {
                    "food-1": {
                        "food_id": "food-1",
                        "name": "Salad",
                        "brand": "Brizel",
                        "barcode": None,
                        "kcal_per_100g": 42,
                        "protein_per_100g": 1.2,
                        "carbs_per_100g": 7.5,
                        "fat_per_100g": 1.0,
                        "created_at": "2026-04-04T10:00:00+00:00",
                    }
                }
            }
        }
    )
    repository = HomeAssistantNutritionRepository(store_manager)
    food = repository.get_food_by_id("food-1")
    food.set_compatibility_metadata(
        FoodCompatibilityMetadata.create(
            labels=["vegetarian"],
            labels_known=True,
            allergens=[],
            allergens_known=True,
            source="explicit",
        )
    )

    await repository.update(food)

    assert store_manager.data["nutrition"]["foods"]["food-1"]["compatibility"] == {
        "allergens_known": True,
        "allergens": [],
        "labels_known": True,
        "labels": ["vegetarian"],
        "source": "explicit",
    }


@pytest.mark.asyncio
async def test_repository_delete_removes_food_from_legacy_storage_shape() -> None:
    """Repository deletes foods from nutrition.foods."""
    store_manager = FakeStoreManager(
        {
            "nutrition": {
                "foods": {
                    "food-1": {
                        "food_id": "food-1",
                        "name": "Apple",
                        "brand": "Orchard",
                        "barcode": "12345",
                        "kcal_per_100g": 52,
                        "protein_per_100g": 0.3,
                        "carbs_per_100g": 14,
                        "fat_per_100g": 0.2,
                        "created_at": "2026-04-04T10:00:00+00:00",
                    }
                }
            }
        }
    )
    repository = HomeAssistantNutritionRepository(store_manager)

    await repository.delete("food-1")

    assert store_manager.data["nutrition"]["foods"] == {}
    assert store_manager.save_calls == 1
