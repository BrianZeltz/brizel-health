"""Tests for nutrition food write use cases."""

from __future__ import annotations

import pytest

from custom_components.brizel_health.application.nutrition.food_use_cases import (
    clear_food_compatibility_metadata,
    clear_food_hydration_metadata,
    create_food,
    delete_food,
    update_food,
    update_food_compatibility_metadata,
    update_food_hydration_metadata,
)
from custom_components.brizel_health.domains.nutrition.errors import (
    BrizelFoodAlreadyExistsError,
    BrizelFoodNotFoundError,
    BrizelFoodValidationError,
)
from custom_components.brizel_health.domains.nutrition.models.food import (
    Food,
    HYDRATION_KIND_FOOD,
    HYDRATION_SOURCE_EXPLICIT,
)
from custom_components.brizel_health.domains.nutrition.models.food_compatibility import (
    FOOD_COMPATIBILITY_SOURCE_EXPLICIT,
    FoodCompatibilityMetadata,
)
from custom_components.brizel_health.domains.nutrition.services.water import (
    build_internal_water_food,
)


class InMemoryFoodRepository:
    """Simple in-memory repository for food write tests."""

    def __init__(self, foods: list[Food] | None = None) -> None:
        self._foods = {
            food.food_id: food for food in foods or []
        }

    async def add(self, food: Food) -> Food:
        self._foods[food.food_id] = food
        return food

    async def update(self, food: Food) -> Food:
        self._foods[food.food_id] = food
        return food

    async def delete(self, food_id: str) -> None:
        if food_id not in self._foods:
            raise BrizelFoodNotFoundError(
                f"No food found for food_id '{food_id}'."
            )
        del self._foods[food_id]

    def get_food_by_id(self, food_id: str) -> Food:
        food = self._foods.get(food_id)
        if food is None:
            raise BrizelFoodNotFoundError(
                f"No food found for food_id '{food_id}'."
            )
        return food

    def get_all_foods(self) -> list[Food]:
        return list(self._foods.values())

    def food_name_exists(
        self,
        name: str,
        brand: str | None,
        exclude_food_id: str | None = None,
    ) -> bool:
        normalized_name = name.strip().casefold()
        normalized_brand = brand.strip().casefold() if brand is not None else None

        for food_id, food in self._foods.items():
            if exclude_food_id is not None and food_id == exclude_food_id:
                continue

            existing_name = food.name.strip().casefold()
            existing_brand = (
                food.brand.strip().casefold() if food.brand is not None else None
            )
            if existing_name == normalized_name and existing_brand == normalized_brand:
                return True

        return False

    def barcode_exists(
        self,
        barcode: str | None,
        exclude_food_id: str | None = None,
    ) -> bool:
        normalized_barcode = barcode.strip() if barcode is not None else None
        if not normalized_barcode:
            return False

        for food_id, food in self._foods.items():
            if exclude_food_id is not None and food_id == exclude_food_id:
                continue
            if food.barcode == normalized_barcode:
                return True

        return False


@pytest.mark.asyncio
async def test_create_food_normalizes_and_persists_catalog_entry() -> None:
    """Create use case preserves the legacy food catalog behavior."""
    repository = InMemoryFoodRepository()

    food = await create_food(
        repository=repository,
        name=" Apple ",
        brand=" Orchard ",
        barcode=" 12345 ",
        kcal_per_100g=52,
        protein_per_100g=0.3,
        carbs_per_100g=14,
        fat_per_100g=0.2,
    )

    assert food.name == "Apple"
    assert food.brand == "Orchard"
    assert food.barcode == "12345"
    assert repository.get_food_by_id(food.food_id).food_id == food.food_id


@pytest.mark.asyncio
async def test_create_food_rejects_duplicate_name_and_brand() -> None:
    """Create use case enforces legacy uniqueness rules."""
    existing = Food.from_dict(
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
    repository = InMemoryFoodRepository([existing])

    with pytest.raises(BrizelFoodAlreadyExistsError):
        await create_food(
            repository=repository,
            name=" apple ",
            brand=" orchard ",
            barcode="99999",
            kcal_per_100g=52,
            protein_per_100g=0.3,
            carbs_per_100g=14,
            fat_per_100g=0.2,
        )


@pytest.mark.asyncio
async def test_update_food_rejects_duplicate_barcode() -> None:
    """Update use case keeps barcode uniqueness."""
    apple = Food.from_dict(
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
    rice = Food.from_dict(
        {
            "food_id": "food-2",
            "name": "Rice",
            "brand": None,
            "barcode": "67890",
            "kcal_per_100g": 130,
            "protein_per_100g": 2.7,
            "carbs_per_100g": 28,
            "fat_per_100g": 0.3,
            "created_at": "2026-04-04T11:00:00+00:00",
        }
    )
    repository = InMemoryFoodRepository([apple, rice])

    with pytest.raises(BrizelFoodAlreadyExistsError):
        await update_food(
            repository=repository,
            food_id="food-2",
            name="Rice",
            brand=None,
            barcode="12345",
            kcal_per_100g=130,
            protein_per_100g=2.7,
            carbs_per_100g=28,
            fat_per_100g=0.3,
        )


@pytest.mark.asyncio
async def test_delete_food_removes_catalog_entry() -> None:
    """Delete use case removes the food from the catalog."""
    apple = Food.from_dict(
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
    repository = InMemoryFoodRepository([apple])

    await delete_food(repository, " food-1 ")

    assert repository.get_all_foods() == []


@pytest.mark.asyncio
async def test_update_food_rejects_direct_changes_to_internal_water_food() -> None:
    """The internal water food should stay protected from direct catalog edits."""
    repository = InMemoryFoodRepository([build_internal_water_food()])

    with pytest.raises(BrizelFoodValidationError):
        await update_food(
            repository=repository,
            food_id="brizel_internal_water",
            name="Sparkling Water",
            brand=None,
            barcode=None,
            kcal_per_100g=0,
            protein_per_100g=0,
            carbs_per_100g=0,
            fat_per_100g=0,
        )


@pytest.mark.asyncio
async def test_delete_food_rejects_internal_water_food() -> None:
    """The internal water food should not be deleted through normal catalog flows."""
    repository = InMemoryFoodRepository([build_internal_water_food()])

    with pytest.raises(BrizelFoodValidationError):
        await delete_food(repository, " brizel_internal_water ")


@pytest.mark.asyncio
async def test_update_food_hydration_metadata_sets_explicit_hydration_values() -> None:
    """Foods can be enriched with trusted hydration metadata without touching macros."""
    cucumber = Food.from_dict(
        {
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
    )
    repository = InMemoryFoodRepository([cucumber])

    updated = await update_food_hydration_metadata(
        repository=repository,
        food_id="food-1",
        hydration_kind=HYDRATION_KIND_FOOD,
        hydration_ml_per_100g=95,
        hydration_source=HYDRATION_SOURCE_EXPLICIT,
    )

    assert updated.hydration_kind == HYDRATION_KIND_FOOD
    assert updated.hydration_ml_per_100g == 95
    assert updated.hydration_source == HYDRATION_SOURCE_EXPLICIT
    assert updated.kcal_per_100g == 15


@pytest.mark.asyncio
async def test_clear_food_hydration_metadata_removes_existing_hydration_values() -> None:
    """Trusted hydration metadata can be removed without changing the catalog food."""
    cucumber = Food.from_dict(
        {
            "food_id": "food-1",
            "name": "Cucumber",
            "brand": None,
            "barcode": None,
            "kcal_per_100g": 15,
            "protein_per_100g": 0.7,
            "carbs_per_100g": 3.6,
            "fat_per_100g": 0.1,
            "hydration_kind": "food",
            "hydration_ml_per_100g": 95,
            "hydration_source": "explicit",
            "created_at": "2026-04-04T10:00:00+00:00",
        }
    )
    repository = InMemoryFoodRepository([cucumber])

    updated = await clear_food_hydration_metadata(repository, "food-1")

    assert updated.hydration_kind is None
    assert updated.hydration_ml_per_100g is None
    assert updated.hydration_source is None


@pytest.mark.asyncio
async def test_update_food_hydration_metadata_rejects_internal_water_variants() -> None:
    """Canonical water variants stay protected even if they do not use the reserved ID."""
    imported_water = Food.from_dict(
        {
            "food_id": "food-imported-water",
            "name": "Water",
            "brand": None,
            "barcode": None,
            "kcal_per_100g": 0,
            "protein_per_100g": 0,
            "carbs_per_100g": 0,
            "fat_per_100g": 0,
            "hydration_kind": "drink",
            "hydration_ml_per_100g": 100,
            "hydration_source": "internal",
            "created_at": "2026-04-04T10:00:00+00:00",
        }
    )
    repository = InMemoryFoodRepository([imported_water])

    with pytest.raises(BrizelFoodValidationError):
        await update_food_hydration_metadata(
            repository=repository,
            food_id="food-imported-water",
            hydration_kind=HYDRATION_KIND_FOOD,
            hydration_ml_per_100g=80,
            hydration_source=HYDRATION_SOURCE_EXPLICIT,
        )


@pytest.mark.asyncio
async def test_update_food_compatibility_metadata_sets_trusted_food_metadata() -> None:
    """Foods can be enriched with compatibility metadata without changing macros."""
    cucumber = Food.from_dict(
        {
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
    )
    repository = InMemoryFoodRepository([cucumber])

    updated = await update_food_compatibility_metadata(
        repository=repository,
        food_id="food-1",
        compatibility=FoodCompatibilityMetadata.create(
            ingredients=["cucumber"],
            ingredients_known=True,
            labels=["vegan"],
            labels_known=True,
            source=FOOD_COMPATIBILITY_SOURCE_EXPLICIT,
        ),
    )

    assert updated.compatibility is not None
    assert updated.compatibility.ingredients == ("cucumber",)
    assert updated.compatibility.labels == ("vegan",)
    assert updated.compatibility.source == FOOD_COMPATIBILITY_SOURCE_EXPLICIT
    assert updated.kcal_per_100g == 15


@pytest.mark.asyncio
async def test_clear_food_compatibility_metadata_removes_existing_values() -> None:
    """Compatibility metadata can be cleared without touching the catalog entry."""
    cucumber = Food.from_dict(
        {
            "food_id": "food-1",
            "name": "Cucumber",
            "brand": None,
            "barcode": None,
            "kcal_per_100g": 15,
            "protein_per_100g": 0.7,
            "carbs_per_100g": 3.6,
            "fat_per_100g": 0.1,
            "compatibility": {
                "ingredients_known": True,
                "ingredients": ["cucumber"],
                "labels_known": True,
                "labels": ["vegan"],
                "source": "explicit",
            },
            "created_at": "2026-04-04T10:00:00+00:00",
        }
    )
    repository = InMemoryFoodRepository([cucumber])

    updated = await clear_food_compatibility_metadata(repository, "food-1")

    assert updated.compatibility is None


@pytest.mark.asyncio
async def test_update_food_compatibility_metadata_rejects_internal_water_variants() -> None:
    """Internal water stays protected from direct compatibility enrichment."""
    imported_water = Food.from_dict(
        {
            "food_id": "food-imported-water",
            "name": "Water",
            "brand": None,
            "barcode": None,
            "kcal_per_100g": 0,
            "protein_per_100g": 0,
            "carbs_per_100g": 0,
            "fat_per_100g": 0,
            "hydration_kind": "drink",
            "hydration_ml_per_100g": 100,
            "hydration_source": "internal",
            "created_at": "2026-04-04T10:00:00+00:00",
        }
    )
    repository = InMemoryFoodRepository([imported_water])

    with pytest.raises(BrizelFoodValidationError):
        await update_food_compatibility_metadata(
            repository=repository,
            food_id="food-imported-water",
            compatibility=FoodCompatibilityMetadata.create(
                allergens=["pollen"],
                allergens_known=True,
                source=FOOD_COMPATIBILITY_SOURCE_EXPLICIT,
            ),
        )
