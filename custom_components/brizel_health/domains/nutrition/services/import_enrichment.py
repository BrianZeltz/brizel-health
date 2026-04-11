"""Internal enrichment and merge helpers for imported foods."""

from __future__ import annotations

from dataclasses import dataclass

from ..errors import BrizelImportedFoodValidationError
from ..models.food import (
    Food,
    HYDRATION_SOURCE_IMPORTED,
)
from ..models.food_compatibility import (
    FOOD_COMPATIBILITY_SOURCE_IMPORTED,
    FoodCompatibilityMetadata,
)
from ..models.imported_food_data import ImportedFoodData


@dataclass(slots=True)
class ImportedFoodEnrichment:
    """Internal enrichment derived from imported food data."""

    hydration_kind: str | None
    hydration_ml_per_100g: float | None
    hydration_source: str | None
    compatibility: FoodCompatibilityMetadata | None

    def has_hydration_metadata(self) -> bool:
        """Return whether imported hydration metadata is available."""
        return (
            self.hydration_kind is not None
            and self.hydration_ml_per_100g is not None
        )


def enrich_imported_food(imported_food: ImportedFoodData) -> ImportedFoodEnrichment:
    """Build internal enrichment data from a source-neutral imported food."""
    compatibility = None
    if (
        imported_food.ingredients_known
        or imported_food.allergens_known
        or imported_food.labels_known
    ):
        compatibility = FoodCompatibilityMetadata.create(
            ingredients=imported_food.ingredients,
            ingredients_known=imported_food.ingredients_known,
            allergens=imported_food.allergens,
            allergens_known=imported_food.allergens_known,
            labels=imported_food.labels,
            labels_known=imported_food.labels_known,
            source=FOOD_COMPATIBILITY_SOURCE_IMPORTED,
        )

    if (
        imported_food.hydration_kind is not None
        and imported_food.hydration_ml_per_100g is not None
    ):
        hydration_kind = imported_food.hydration_kind
        hydration_ml_per_100g = imported_food.hydration_ml_per_100g
        hydration_source = HYDRATION_SOURCE_IMPORTED
    else:
        hydration_kind = None
        hydration_ml_per_100g = None
        hydration_source = None

    return ImportedFoodEnrichment(
        hydration_kind=hydration_kind,
        hydration_ml_per_100g=hydration_ml_per_100g,
        hydration_source=hydration_source,
        compatibility=compatibility,
    )


def create_food_from_imported_food(
    imported_food: ImportedFoodData,
    enrichment: ImportedFoodEnrichment,
) -> Food:
    """Create a new internal food from imported data and enrichment."""
    if not imported_food.has_complete_nutrition():
        raise BrizelImportedFoodValidationError(
            "Imported food data must contain kcal, protein, carbs and fat per 100g."
        )

    return Food.create(
        name=imported_food.name,
        brand=imported_food.brand,
        barcode=imported_food.barcode,
        kcal_per_100g=imported_food.kcal_per_100g,
        protein_per_100g=imported_food.protein_per_100g,
        carbs_per_100g=imported_food.carbs_per_100g,
        fat_per_100g=imported_food.fat_per_100g,
        hydration_kind=enrichment.hydration_kind,
        hydration_ml_per_100g=enrichment.hydration_ml_per_100g,
        hydration_source=enrichment.hydration_source,
        compatibility=enrichment.compatibility,
    )


def _resolve_hydration_for_merge(
    food: Food,
    enrichment: ImportedFoodEnrichment,
) -> tuple[str | None, float | None, str | None]:
    """Merge imported hydration metadata without clobbering trusted internal data."""
    if food.has_hydration_data() and food.hydration_source != HYDRATION_SOURCE_IMPORTED:
        return (
            food.hydration_kind,
            food.hydration_ml_per_100g,
            food.hydration_source,
        )

    if enrichment.has_hydration_metadata():
        return (
            enrichment.hydration_kind,
            enrichment.hydration_ml_per_100g,
            enrichment.hydration_source,
        )

    if food.hydration_source == HYDRATION_SOURCE_IMPORTED:
        return None, None, None

    return (
        food.hydration_kind,
        food.hydration_ml_per_100g,
        food.hydration_source,
    )


def _resolve_compatibility_for_merge(
    food: Food,
    enrichment: ImportedFoodEnrichment,
) -> FoodCompatibilityMetadata | None:
    """Merge imported compatibility metadata without clobbering trusted internal data."""
    if (
        food.compatibility is not None
        and food.compatibility.source != FOOD_COMPATIBILITY_SOURCE_IMPORTED
    ):
        return food.compatibility

    if enrichment.compatibility is not None:
        return enrichment.compatibility

    if (
        food.compatibility is not None
        and food.compatibility.source == FOOD_COMPATIBILITY_SOURCE_IMPORTED
    ):
        return None

    return food.compatibility


def merge_imported_food_into_existing_food(
    food: Food,
    imported_food: ImportedFoodData,
    enrichment: ImportedFoodEnrichment,
) -> Food:
    """Apply imported catalog data to an existing internal food."""
    if not imported_food.has_complete_nutrition():
        raise BrizelImportedFoodValidationError(
            "Imported food data must contain kcal, protein, carbs and fat per 100g."
        )

    (
        hydration_kind,
        hydration_ml_per_100g,
        hydration_source,
    ) = _resolve_hydration_for_merge(food, enrichment)
    compatibility = _resolve_compatibility_for_merge(food, enrichment)

    food.update(
        name=imported_food.name,
        brand=imported_food.brand,
        barcode=imported_food.barcode,
        kcal_per_100g=imported_food.kcal_per_100g,
        protein_per_100g=imported_food.protein_per_100g,
        carbs_per_100g=imported_food.carbs_per_100g,
        fat_per_100g=imported_food.fat_per_100g,
        hydration_kind=hydration_kind,
        hydration_ml_per_100g=hydration_ml_per_100g,
        hydration_source=hydration_source,
        compatibility=compatibility,
    )
    return food
