"""Cross-module compatibility queries that combine body rules and nutrition data."""

from __future__ import annotations

from ...domains.body.models.dietary_restrictions import DietaryRestrictions
from ...domains.nutrition.interfaces.food_repository import FoodRepository
from ...domains.nutrition.services.food_compatibility import (
    FoodCompatibilityAssessment,
    evaluate_food_compatibility,
)
from ..nutrition.food_queries import get_food


def get_food_compatibility(
    repository: FoodRepository,
    food_id: str,
    restrictions: DietaryRestrictions,
) -> FoodCompatibilityAssessment:
    """Evaluate one food against body-owned dietary restrictions."""
    food = get_food(repository, food_id)
    return evaluate_food_compatibility(
        food=food,
        dietary_pattern=restrictions.dietary_pattern,
        allergens=restrictions.allergens,
        intolerances=restrictions.intolerances,
    )
