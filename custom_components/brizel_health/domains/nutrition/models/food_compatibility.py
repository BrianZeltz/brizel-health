"""Food compatibility metadata for later import enrichment and evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from ..errors import BrizelFoodValidationError

FOOD_COMPATIBILITY_SOURCE_EXPLICIT = "explicit"
FOOD_COMPATIBILITY_SOURCE_IMPORTED = "imported"
ALLOWED_FOOD_COMPATIBILITY_SOURCES = {
    FOOD_COMPATIBILITY_SOURCE_EXPLICIT,
    FOOD_COMPATIBILITY_SOURCE_IMPORTED,
}

FOOD_LABEL_VEGAN = "vegan"
FOOD_LABEL_VEGETARIAN = "vegetarian"


def _normalize_term(value: str) -> str:
    """Normalize a compatibility term."""
    return value.strip().lower()


def _normalize_terms(values: Iterable[str] | None) -> tuple[str, ...]:
    """Normalize and deduplicate compatibility terms while preserving order."""
    if values is None:
        return ()

    normalized_values: list[str] = []
    seen: set[str] = set()

    for value in values:
        normalized_value = _normalize_term(str(value))
        if not normalized_value or normalized_value in seen:
            continue
        seen.add(normalized_value)
        normalized_values.append(normalized_value)

    return tuple(normalized_values)


def validate_food_compatibility_source(value: str | None) -> str | None:
    """Validate and normalize the optional compatibility metadata source."""
    if value is None:
        return None

    normalized_value = _normalize_term(value)
    if not normalized_value:
        return None

    if normalized_value not in ALLOWED_FOOD_COMPATIBILITY_SOURCES:
        raise BrizelFoodValidationError(
            "compatibility source must be one of "
            f"{sorted(ALLOWED_FOOD_COMPATIBILITY_SOURCES)}."
        )

    return normalized_value


@dataclass(slots=True)
class FoodCompatibilityMetadata:
    """Trusted food metadata relevant for dietary compatibility checks."""

    ingredients: tuple[str, ...]
    ingredients_known: bool
    allergens: tuple[str, ...]
    allergens_known: bool
    labels: tuple[str, ...]
    labels_known: bool
    source: str | None

    @classmethod
    def create(
        cls,
        ingredients: Iterable[str] | None = None,
        ingredients_known: bool = False,
        allergens: Iterable[str] | None = None,
        allergens_known: bool = False,
        labels: Iterable[str] | None = None,
        labels_known: bool = False,
        source: str | None = None,
    ) -> "FoodCompatibilityMetadata":
        """Create validated food compatibility metadata."""
        normalized_ingredients = _normalize_terms(ingredients)
        normalized_allergens = _normalize_terms(allergens)
        normalized_labels = _normalize_terms(labels)
        normalized_source = validate_food_compatibility_source(source)

        if normalized_ingredients and not ingredients_known:
            raise BrizelFoodValidationError(
                "ingredients_known must be true when ingredients are provided."
            )
        if normalized_allergens and not allergens_known:
            raise BrizelFoodValidationError(
                "allergens_known must be true when allergens are provided."
            )
        if normalized_labels and not labels_known:
            raise BrizelFoodValidationError(
                "labels_known must be true when labels are provided."
            )

        if normalized_source is not None and not (
            ingredients_known or allergens_known or labels_known
        ):
            raise BrizelFoodValidationError(
                "compatibility source requires known compatibility metadata."
            )

        return cls(
            ingredients=normalized_ingredients,
            ingredients_known=bool(ingredients_known),
            allergens=normalized_allergens,
            allergens_known=bool(allergens_known),
            labels=normalized_labels,
            labels_known=bool(labels_known),
            source=normalized_source,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FoodCompatibilityMetadata":
        """Create metadata from persisted food compatibility data."""
        return cls.create(
            ingredients=data.get("ingredients"),
            ingredients_known=bool(data.get("ingredients_known", False)),
            allergens=data.get("allergens"),
            allergens_known=bool(data.get("allergens_known", False)),
            labels=data.get("labels"),
            labels_known=bool(data.get("labels_known", False)),
            source=data.get("source"),
        )

    def has_known_metadata(self) -> bool:
        """Return whether any compatibility section is known."""
        return (
            self.ingredients_known
            or self.allergens_known
            or self.labels_known
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the metadata for storage on a food."""
        data: dict[str, Any] = {}

        if self.ingredients_known:
            data["ingredients_known"] = True
            data["ingredients"] = list(self.ingredients)
        if self.allergens_known:
            data["allergens_known"] = True
            data["allergens"] = list(self.allergens)
        if self.labels_known:
            data["labels_known"] = True
            data["labels"] = list(self.labels)
        if self.source is not None:
            data["source"] = self.source

        return data
