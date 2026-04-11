"""Tests for food compatibility queries."""

from __future__ import annotations

from custom_components.brizel_health.application.queries.compatibility_queries import (
    get_food_compatibility,
)
from custom_components.brizel_health.domains.body.models.dietary_restrictions import (
    DIETARY_PATTERN_VEGETARIAN,
    DIETARY_PATTERN_VEGAN,
    DietaryRestrictions,
)
from custom_components.brizel_health.domains.nutrition.errors import (
    BrizelFoodNotFoundError,
)
from custom_components.brizel_health.domains.nutrition.models.food import Food
from custom_components.brizel_health.domains.nutrition.models.food_compatibility import (
    FOOD_COMPATIBILITY_SOURCE_EXPLICIT,
    FoodCompatibilityMetadata,
)


class InMemoryFoodRepository:
    """Simple in-memory repository for compatibility query tests."""

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


def test_dietary_restrictions_normalize_values() -> None:
    """Body-owned dietary restrictions should normalize stable values."""
    restrictions = DietaryRestrictions.create(
        dietary_pattern=" Vegetarian ",
        allergens=[" Milk ", "milk", " Egg "],
        intolerances=[" Lactose ", "lactose"],
    )

    assert restrictions.dietary_pattern == DIETARY_PATTERN_VEGETARIAN
    assert restrictions.allergens == ("milk", "egg")
    assert restrictions.intolerances == ("lactose",)


def test_get_food_compatibility_marks_known_allergen_as_incompatible() -> None:
    """Known food allergens should make a conflicting food incompatible."""
    food = Food.create(
        name="Yogurt",
        brand=None,
        barcode=None,
        kcal_per_100g=61,
        protein_per_100g=3.5,
        carbs_per_100g=4.7,
        fat_per_100g=3.3,
        compatibility=FoodCompatibilityMetadata.create(
            allergens=["milk"],
            allergens_known=True,
            source=FOOD_COMPATIBILITY_SOURCE_EXPLICIT,
        ),
    )
    repository = InMemoryFoodRepository([food])

    assessment = get_food_compatibility(
        repository=repository,
        food_id=food.food_id,
        restrictions=DietaryRestrictions.create(allergens=["milk"]),
    )

    assert assessment == {
        "food_id": food.food_id,
        "food_name": "Yogurt",
        "food_brand": None,
        "status": "incompatible",
        "compatibility_source": FOOD_COMPATIBILITY_SOURCE_EXPLICIT,
        "incompatible_reasons": [{"kind": "allergen", "value": "milk"}],
        "unknown_reasons": [],
    }


def test_get_food_compatibility_returns_unknown_when_metadata_is_missing() -> None:
    """Missing trusted metadata should keep compatibility evaluation conservative."""
    food = Food.create(
        name="Mystery Bowl",
        brand=None,
        barcode=None,
        kcal_per_100g=120,
        protein_per_100g=4,
        carbs_per_100g=18,
        fat_per_100g=3,
    )
    repository = InMemoryFoodRepository([food])

    assessment = get_food_compatibility(
        repository=repository,
        food_id=food.food_id,
        restrictions=DietaryRestrictions.create(dietary_pattern=DIETARY_PATTERN_VEGAN),
    )

    assert assessment == {
        "food_id": food.food_id,
        "food_name": "Mystery Bowl",
        "food_brand": None,
        "status": "unknown",
        "compatibility_source": None,
        "incompatible_reasons": [],
        "unknown_reasons": [{"kind": "dietary_pattern", "value": "vegan"}],
    }


def test_get_food_compatibility_can_be_compatible_with_trusted_metadata() -> None:
    """Trusted metadata should allow an honestly compatible result."""
    food = Food.create(
        name="Salad",
        brand="Brizel",
        barcode=None,
        kcal_per_100g=42,
        protein_per_100g=1.2,
        carbs_per_100g=7.5,
        fat_per_100g=1.0,
        compatibility=FoodCompatibilityMetadata.create(
            allergens=[],
            allergens_known=True,
            labels=["vegetarian"],
            labels_known=True,
            source=FOOD_COMPATIBILITY_SOURCE_EXPLICIT,
        ),
    )
    repository = InMemoryFoodRepository([food])

    assessment = get_food_compatibility(
        repository=repository,
        food_id=food.food_id,
        restrictions=DietaryRestrictions.create(
            dietary_pattern=DIETARY_PATTERN_VEGETARIAN,
            allergens=["milk"],
        ),
    )

    assert assessment == {
        "food_id": food.food_id,
        "food_name": "Salad",
        "food_brand": "Brizel",
        "status": "compatible",
        "compatibility_source": FOOD_COMPATIBILITY_SOURCE_EXPLICIT,
        "incompatible_reasons": [],
        "unknown_reasons": [],
    }


def test_get_food_compatibility_uses_known_ingredients_for_intolerances() -> None:
    """Known ingredients can drive incompatibility for intolerance-style restrictions."""
    food = Food.create(
        name="Milkshake",
        brand=None,
        barcode=None,
        kcal_per_100g=90,
        protein_per_100g=3.0,
        carbs_per_100g=12.0,
        fat_per_100g=3.0,
        compatibility=FoodCompatibilityMetadata.create(
            ingredients=["milk", "lactose"],
            ingredients_known=True,
            source=FOOD_COMPATIBILITY_SOURCE_EXPLICIT,
        ),
    )
    repository = InMemoryFoodRepository([food])

    assessment = get_food_compatibility(
        repository=repository,
        food_id=food.food_id,
        restrictions=DietaryRestrictions.create(intolerances=["lactose"]),
    )

    assert assessment == {
        "food_id": food.food_id,
        "food_name": "Milkshake",
        "food_brand": None,
        "status": "incompatible",
        "compatibility_source": FOOD_COMPATIBILITY_SOURCE_EXPLICIT,
        "incompatible_reasons": [{"kind": "ingredient", "value": "lactose"}],
        "unknown_reasons": [],
    }
