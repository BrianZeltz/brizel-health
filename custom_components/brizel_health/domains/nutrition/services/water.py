"""Water helpers built on top of the food catalog."""

from __future__ import annotations

from datetime import UTC, datetime

from ..models.food import (
    Food,
    HYDRATION_KIND_DRINK,
    HYDRATION_SOURCE_INTERNAL,
)

INTERNAL_WATER_FOOD_ID = "brizel_internal_water"
INTERNAL_WATER_FOOD_NAME = "Water"
DEFAULT_WATER_AMOUNT_ML = 250.0
INTERNAL_WATER_HYDRATION_ML_PER_100G = 100.0


def build_internal_water_food() -> Food:
    """Build the canonical internal water food."""
    return Food.from_dict(
        {
            "food_id": INTERNAL_WATER_FOOD_ID,
            "name": INTERNAL_WATER_FOOD_NAME,
            "brand": None,
            "barcode": None,
            "kcal_per_100g": 0,
            "protein_per_100g": 0,
            "carbs_per_100g": 0,
            "fat_per_100g": 0,
            "hydration_kind": HYDRATION_KIND_DRINK,
            "hydration_ml_per_100g": INTERNAL_WATER_HYDRATION_ML_PER_100G,
            "hydration_source": HYDRATION_SOURCE_INTERNAL,
            "created_at": datetime.now(UTC).isoformat(),
        }
    )


def matches_internal_water_definition(food: Food) -> bool:
    """Return whether a food matches the canonical water definition."""
    return (
        food.name == INTERNAL_WATER_FOOD_NAME
        and food.brand is None
        and food.barcode is None
        and food.kcal_per_100g == 0
        and food.protein_per_100g == 0
        and food.carbs_per_100g == 0
        and food.fat_per_100g == 0
        and food.hydration_kind == HYDRATION_KIND_DRINK
        and food.hydration_ml_per_100g == INTERNAL_WATER_HYDRATION_ML_PER_100G
        and food.hydration_source == HYDRATION_SOURCE_INTERNAL
    )


def is_internal_water_food_id(food_id: str) -> bool:
    """Return whether a food ID is reserved for the internal water food."""
    return food_id.strip() == INTERNAL_WATER_FOOD_ID


def is_internal_water_food(food: Food) -> bool:
    """Return whether a food should be treated as protected internal water."""
    return is_internal_water_food_id(food.food_id) or matches_internal_water_definition(
        food
    )
