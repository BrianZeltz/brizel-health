"""Compatibility evaluation for foods against body-owned dietary restrictions."""

from __future__ import annotations

from typing import TypedDict

from ..models.food import Food
from ..models.food_compatibility import (
    FOOD_LABEL_VEGAN,
    FOOD_LABEL_VEGETARIAN,
)

FOOD_COMPATIBILITY_STATUS_COMPATIBLE = "compatible"
FOOD_COMPATIBILITY_STATUS_INCOMPATIBLE = "incompatible"
FOOD_COMPATIBILITY_STATUS_UNKNOWN = "unknown"


class FoodCompatibilityReason(TypedDict):
    """Single structured reason emitted by a compatibility evaluation."""

    kind: str
    value: str | None


class FoodCompatibilityAssessment(TypedDict):
    """Compatibility evaluation result for one food."""

    food_id: str
    food_name: str
    food_brand: str | None
    status: str
    compatibility_source: str | None
    incompatible_reasons: list[FoodCompatibilityReason]
    unknown_reasons: list[FoodCompatibilityReason]


def _evaluate_dietary_pattern(
    labels: tuple[str, ...],
    dietary_pattern: str | None,
    labels_known: bool,
    incompatible_reasons: list[FoodCompatibilityReason],
    unknown_reasons: list[FoodCompatibilityReason],
) -> None:
    """Evaluate the optional dietary pattern conservatively."""
    if dietary_pattern is None:
        return

    if not labels_known:
        unknown_reasons.append(
            {"kind": "dietary_pattern", "value": dietary_pattern}
        )
        return

    if dietary_pattern == FOOD_LABEL_VEGAN and FOOD_LABEL_VEGAN not in labels:
        unknown_reasons.append({"kind": "dietary_pattern", "value": FOOD_LABEL_VEGAN})
        return

    if dietary_pattern == FOOD_LABEL_VEGETARIAN and not (
        FOOD_LABEL_VEGETARIAN in labels or FOOD_LABEL_VEGAN in labels
    ):
        unknown_reasons.append(
            {"kind": "dietary_pattern", "value": FOOD_LABEL_VEGETARIAN}
        )


def _extend_unique(
    target: list[FoodCompatibilityReason],
    values: list[FoodCompatibilityReason],
) -> None:
    """Append values to a list without duplicates."""
    for value in values:
        if value not in target:
            target.append(value)


def evaluate_food_compatibility(
    food: Food,
    dietary_pattern: str | None = None,
    allergens: tuple[str, ...] = (),
    intolerances: tuple[str, ...] = (),
) -> FoodCompatibilityAssessment:
    """Evaluate one food conservatively against user-owned restrictions."""
    incompatible_reasons: list[FoodCompatibilityReason] = []
    unknown_reasons: list[FoodCompatibilityReason] = []
    compatibility = food.compatibility

    if allergens:
        if compatibility is None or not compatibility.allergens_known:
            unknown_reasons.append({"kind": "allergens", "value": None})
        else:
            matched_allergens = sorted(set(compatibility.allergens) & set(allergens))
            _extend_unique(
                incompatible_reasons,
                [
                    {"kind": "allergen", "value": allergen}
                    for allergen in matched_allergens
                ],
            )

    if intolerances:
        if compatibility is None or not compatibility.ingredients_known:
            unknown_reasons.append({"kind": "ingredients", "value": None})
        else:
            matched_ingredients = sorted(
                set(compatibility.ingredients) & set(intolerances)
            )
            _extend_unique(
                incompatible_reasons,
                [
                    {"kind": "ingredient", "value": ingredient}
                    for ingredient in matched_ingredients
                ],
            )

    if compatibility is None:
        _evaluate_dietary_pattern(
            labels=(),
            dietary_pattern=dietary_pattern,
            labels_known=False,
            incompatible_reasons=incompatible_reasons,
            unknown_reasons=unknown_reasons,
        )
    else:
        _evaluate_dietary_pattern(
            labels=compatibility.labels,
            dietary_pattern=dietary_pattern,
            labels_known=compatibility.labels_known,
            incompatible_reasons=incompatible_reasons,
            unknown_reasons=unknown_reasons,
        )

    if incompatible_reasons:
        status = FOOD_COMPATIBILITY_STATUS_INCOMPATIBLE
    elif unknown_reasons:
        status = FOOD_COMPATIBILITY_STATUS_UNKNOWN
    else:
        status = FOOD_COMPATIBILITY_STATUS_COMPATIBLE

    return {
        "food_id": food.food_id,
        "food_name": food.name,
        "food_brand": food.brand,
        "status": status,
        "compatibility_source": (
            compatibility.source if compatibility is not None else None
        ),
        "incompatible_reasons": incompatible_reasons,
        "unknown_reasons": unknown_reasons,
    }
