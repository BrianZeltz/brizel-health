"""Read use cases for the nutrition food catalog."""

from __future__ import annotations

from ...domains.nutrition.errors import BrizelFoodValidationError
from ...domains.nutrition.interfaces.food_repository import FoodRepository
from ...domains.nutrition.models.food import Food


def get_food(repository: FoodRepository, food_id: str) -> Food:
    """Return a single food from the catalog."""
    normalized_food_id = food_id.strip()
    if not normalized_food_id:
        raise BrizelFoodValidationError("A food ID is required.")
    return repository.get_food_by_id(normalized_food_id)


def get_foods(repository: FoodRepository) -> list[Food]:
    """Return all foods from the catalog."""
    return repository.get_all_foods()
