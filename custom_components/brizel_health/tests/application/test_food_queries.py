"""Tests for nutrition food read queries."""

from __future__ import annotations

import pytest

from custom_components.brizel_health.application.nutrition.food_queries import (
    get_food,
    get_foods,
)
from custom_components.brizel_health.domains.nutrition.errors import (
    BrizelFoodNotFoundError,
    BrizelFoodValidationError,
)
from custom_components.brizel_health.domains.nutrition.models.food import Food


class InMemoryFoodRepository:
    """Simple in-memory repository for food query tests."""

    def __init__(self, foods: list[Food]) -> None:
        self._foods = {food.food_id: food for food in foods}

    def get_food_by_id(self, food_id: str) -> Food:
        food = self._foods.get(food_id)
        if food is None:
            raise BrizelFoodNotFoundError(
                f"No food found for food_id '{food_id}'."
            )
        return food

    def get_all_foods(self) -> list[Food]:
        return list(self._foods.values())


def test_get_food_returns_catalog_item() -> None:
    """Read queries return foods as domain models."""
    apple = Food.from_dict(
        {
            "food_id": "food-1",
            "name": " Apple ",
            "brand": " Orchard ",
            "barcode": " 12345 ",
            "kcal_per_100g": 52,
            "protein_per_100g": 0.3,
            "carbs_per_100g": 14,
            "fat_per_100g": 0.2,
            "created_at": "2026-04-04T10:00:00+00:00",
        }
    )
    repository = InMemoryFoodRepository([apple])

    food = get_food(repository, " food-1 ")

    assert food.food_id == "food-1"
    assert food.name == "Apple"
    assert food.brand == "Orchard"
    assert food.barcode == "12345"


def test_get_food_validates_required_food_id() -> None:
    """Read queries reject empty food IDs before repository access."""
    repository = InMemoryFoodRepository([])

    with pytest.raises(BrizelFoodValidationError):
        get_food(repository, "   ")


def test_get_foods_returns_all_catalog_items() -> None:
    """Read queries return the full catalog."""
    repository = InMemoryFoodRepository(
        [
            Food.from_dict(
                {
                    "food_id": "food-1",
                    "name": "Apple",
                    "brand": None,
                    "barcode": None,
                    "kcal_per_100g": 52,
                    "protein_per_100g": 0.3,
                    "carbs_per_100g": 14,
                    "fat_per_100g": 0.2,
                    "created_at": "2026-04-04T10:00:00+00:00",
                }
            ),
            Food.from_dict(
                {
                    "food_id": "food-2",
                    "name": "Rice",
                    "brand": "Brizel",
                    "barcode": "67890",
                    "kcal_per_100g": 130,
                    "protein_per_100g": 2.7,
                    "carbs_per_100g": 28,
                    "fat_per_100g": 0.3,
                    "created_at": "2026-04-04T11:00:00+00:00",
                }
            ),
        ]
    )

    foods = get_foods(repository)

    assert [food.food_id for food in foods] == ["food-1", "food-2"]
