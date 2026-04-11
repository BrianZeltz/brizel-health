"""Write use cases for the nutrition food catalog."""

from __future__ import annotations

from ...domains.nutrition.errors import (
    BrizelFoodAlreadyExistsError,
    BrizelFoodValidationError,
)
from ...domains.nutrition.interfaces.food_repository import FoodRepository
from ...domains.nutrition.models.food import Food
from ...domains.nutrition.models.food_compatibility import (
    FoodCompatibilityMetadata,
)
from ...domains.nutrition.services.water import (
    is_internal_water_food,
    is_internal_water_food_id,
)


async def create_food(
    repository: FoodRepository,
    name: str,
    kcal_per_100g: float | int,
    protein_per_100g: float | int,
    carbs_per_100g: float | int,
    fat_per_100g: float | int,
    brand: str | None = None,
    barcode: str | None = None,
) -> Food:
    """Create a new food in the catalog."""
    food = Food.create(
        name=name,
        kcal_per_100g=kcal_per_100g,
        protein_per_100g=protein_per_100g,
        carbs_per_100g=carbs_per_100g,
        fat_per_100g=fat_per_100g,
        brand=brand,
        barcode=barcode,
    )

    if repository.food_name_exists(food.name, food.brand):
        if food.brand:
            raise BrizelFoodAlreadyExistsError(
                f"A food named '{food.name}' from brand '{food.brand}' already exists."
            )
        raise BrizelFoodAlreadyExistsError(
            f"A food named '{food.name}' already exists."
        )

    if repository.barcode_exists(food.barcode):
        raise BrizelFoodAlreadyExistsError(
            f"A food with barcode '{food.barcode}' already exists."
        )

    return await repository.add(food)


async def update_food(
    repository: FoodRepository,
    food_id: str,
    name: str,
    kcal_per_100g: float | int,
    protein_per_100g: float | int,
    carbs_per_100g: float | int,
    fat_per_100g: float | int,
    brand: str | None = None,
    barcode: str | None = None,
) -> Food:
    """Update an existing catalog food."""
    normalized_food_id = food_id.strip()
    if not normalized_food_id:
        raise BrizelFoodValidationError("A food ID is required.")

    food = repository.get_food_by_id(normalized_food_id)
    if is_internal_water_food(food):
        raise BrizelFoodValidationError(
            "The internal water food cannot be updated directly."
        )
    food.update(
        name=name,
        kcal_per_100g=kcal_per_100g,
        protein_per_100g=protein_per_100g,
        carbs_per_100g=carbs_per_100g,
        fat_per_100g=fat_per_100g,
        brand=brand,
        barcode=barcode,
    )

    if repository.food_name_exists(
        food.name,
        food.brand,
        exclude_food_id=food.food_id,
    ):
        if food.brand:
            raise BrizelFoodAlreadyExistsError(
                f"A food named '{food.name}' from brand '{food.brand}' already exists."
            )
        raise BrizelFoodAlreadyExistsError(
            f"A food named '{food.name}' already exists."
        )

    if repository.barcode_exists(
        food.barcode,
        exclude_food_id=food.food_id,
    ):
        raise BrizelFoodAlreadyExistsError(
            f"A food with barcode '{food.barcode}' already exists."
        )

    return await repository.update(food)


async def delete_food(
    repository: FoodRepository,
    food_id: str,
) -> None:
    """Delete a food from the catalog."""
    normalized_food_id = food_id.strip()
    if not normalized_food_id:
        raise BrizelFoodValidationError("A food ID is required.")
    food = repository.get_food_by_id(normalized_food_id)
    if is_internal_water_food(food):
        raise BrizelFoodValidationError(
            "The internal water food cannot be deleted directly."
        )
    await repository.delete(normalized_food_id)


async def update_food_hydration_metadata(
    repository: FoodRepository,
    food_id: str,
    hydration_kind: str | None,
    hydration_ml_per_100g: float | int | None,
    hydration_source: str | None,
) -> Food:
    """Update only the hydration metadata of an existing food."""
    normalized_food_id = food_id.strip()
    if not normalized_food_id:
        raise BrizelFoodValidationError("A food ID is required.")
    if is_internal_water_food_id(normalized_food_id):
        raise BrizelFoodValidationError(
            "The internal water food hydration metadata cannot be updated directly."
        )

    food = repository.get_food_by_id(normalized_food_id)
    if is_internal_water_food(food):
        raise BrizelFoodValidationError(
            "The internal water food hydration metadata cannot be updated directly."
        )

    food.set_hydration_metadata(
        hydration_kind=hydration_kind,
        hydration_ml_per_100g=hydration_ml_per_100g,
        hydration_source=hydration_source,
    )
    return await repository.update(food)


async def clear_food_hydration_metadata(
    repository: FoodRepository,
    food_id: str,
) -> Food:
    """Remove hydration metadata from an existing food."""
    normalized_food_id = food_id.strip()
    if not normalized_food_id:
        raise BrizelFoodValidationError("A food ID is required.")
    if is_internal_water_food_id(normalized_food_id):
        raise BrizelFoodValidationError(
            "The internal water food hydration metadata cannot be cleared directly."
        )

    food = repository.get_food_by_id(normalized_food_id)
    if is_internal_water_food(food):
        raise BrizelFoodValidationError(
            "The internal water food hydration metadata cannot be cleared directly."
        )

    food.clear_hydration_metadata()
    return await repository.update(food)


async def update_food_compatibility_metadata(
    repository: FoodRepository,
    food_id: str,
    compatibility: FoodCompatibilityMetadata,
) -> Food:
    """Update only the compatibility metadata of an existing food."""
    normalized_food_id = food_id.strip()
    if not normalized_food_id:
        raise BrizelFoodValidationError("A food ID is required.")
    if is_internal_water_food_id(normalized_food_id):
        raise BrizelFoodValidationError(
            "The internal water food compatibility metadata cannot be updated directly."
        )

    food = repository.get_food_by_id(normalized_food_id)
    if is_internal_water_food(food):
        raise BrizelFoodValidationError(
            "The internal water food compatibility metadata cannot be updated directly."
        )

    food.set_compatibility_metadata(compatibility)
    return await repository.update(food)


async def clear_food_compatibility_metadata(
    repository: FoodRepository,
    food_id: str,
) -> Food:
    """Remove compatibility metadata from an existing food."""
    normalized_food_id = food_id.strip()
    if not normalized_food_id:
        raise BrizelFoodValidationError("A food ID is required.")
    if is_internal_water_food_id(normalized_food_id):
        raise BrizelFoodValidationError(
            "The internal water food compatibility metadata cannot be cleared directly."
        )

    food = repository.get_food_by_id(normalized_food_id)
    if is_internal_water_food(food):
        raise BrizelFoodValidationError(
            "The internal water food compatibility metadata cannot be cleared directly."
        )

    food.clear_compatibility_metadata()
    return await repository.update(food)
