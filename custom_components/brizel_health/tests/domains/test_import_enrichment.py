"""Tests for imported food enrichment helpers."""

from __future__ import annotations

from custom_components.brizel_health.domains.nutrition.models.imported_food_data import (
    ImportedFoodData,
)
from custom_components.brizel_health.domains.nutrition.services.import_enrichment import (
    create_food_from_imported_food,
    enrich_imported_food,
)


def test_import_enrichment_keeps_unknown_metadata_conservative() -> None:
    """Unknown imported metadata should not be guessed into internal enrichment."""
    imported_food = ImportedFoodData.create(
        source_name="open_food_facts",
        source_id="product-1",
        name="Mystery Soup",
        brand="Brizel",
        barcode="12345",
        kcal_per_100g=50,
        protein_per_100g=2,
        carbs_per_100g=7,
        fat_per_100g=1,
        ingredients_known=False,
        allergens_known=False,
        labels_known=False,
        fetched_at="2026-04-05T10:00:00+00:00",
    )

    enrichment = enrich_imported_food(imported_food)
    food = create_food_from_imported_food(imported_food, enrichment)

    assert enrichment.compatibility is None
    assert enrichment.hydration_kind is None
    assert enrichment.hydration_ml_per_100g is None
    assert food.compatibility is None
    assert food.hydration_kind is None
    assert food.hydration_source is None


def test_import_enrichment_builds_imported_metadata_when_source_data_is_known() -> None:
    """Known imported metadata should become imported enrichment on the internal food."""
    imported_food = ImportedFoodData.create(
        source_name="open_food_facts",
        source_id="product-2",
        name="Sparkling Water",
        brand="Brizel",
        barcode="67890",
        kcal_per_100g=0,
        protein_per_100g=0,
        carbs_per_100g=0,
        fat_per_100g=0,
        allergens=[],
        allergens_known=True,
        labels=["vegan", "vegetarian"],
        labels_known=True,
        hydration_kind="drink",
        hydration_ml_per_100g=100,
        fetched_at="2026-04-05T10:00:00+00:00",
    )

    enrichment = enrich_imported_food(imported_food)
    food = create_food_from_imported_food(imported_food, enrichment)

    assert enrichment.compatibility is not None
    assert enrichment.compatibility.source == "imported"
    assert food.compatibility is not None
    assert food.compatibility.labels == ("vegan", "vegetarian")
    assert food.hydration_kind == "drink"
    assert food.hydration_ml_per_100g == 100
    assert food.hydration_source == "imported"


def test_import_enrichment_does_not_promote_raw_water_amount_without_kind() -> None:
    """A raw imported water value alone should not become trusted hydration metadata yet."""
    imported_food = ImportedFoodData.create(
        source_name="usda",
        source_id="123456",
        name="Apple, raw",
        kcal_per_100g=52,
        protein_per_100g=None,
        carbs_per_100g=None,
        fat_per_100g=None,
        hydration_ml_per_100g=85.6,
        fetched_at="2026-04-05T10:00:00+00:00",
    )

    enrichment = enrich_imported_food(imported_food)

    assert imported_food.hydration_ml_per_100g == 85.6
    assert imported_food.hydration_kind is None
    assert enrichment.hydration_kind is None
    assert enrichment.hydration_ml_per_100g is None
