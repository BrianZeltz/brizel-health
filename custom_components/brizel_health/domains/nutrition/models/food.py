"""Food catalog model for Brizel Health."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from ..common import normalize_optional_text
from ..errors import BrizelFoodValidationError
from .food_compatibility import FoodCompatibilityMetadata

HYDRATION_KIND_DRINK = "drink"
HYDRATION_KIND_FOOD = "food"
ALLOWED_HYDRATION_KINDS = {
    HYDRATION_KIND_DRINK,
    HYDRATION_KIND_FOOD,
}
HYDRATION_SOURCE_INTERNAL = "internal"
HYDRATION_SOURCE_EXPLICIT = "explicit"
HYDRATION_SOURCE_IMPORTED = "imported"
HYDRATION_SOURCE_UNKNOWN = "unknown"
ALLOWED_HYDRATION_SOURCES = {
    HYDRATION_SOURCE_INTERNAL,
    HYDRATION_SOURCE_EXPLICIT,
    HYDRATION_SOURCE_IMPORTED,
}
_UNSET = object()


def generate_food_id() -> str:
    """Generate a stable unique food ID."""
    return uuid4().hex


def normalize_food_name(name: str) -> str:
    """Normalize a food name."""
    return name.strip()


def validate_macro_value(field_name: str, value: float | int) -> float:
    """Validate a macro/calorie value."""
    normalized_value = float(value)

    if normalized_value < 0:
        raise BrizelFoodValidationError(
            f"{field_name} must be greater than or equal to 0."
        )

    return normalized_value


def validate_hydration_kind(value: str | None) -> str | None:
    """Validate and normalize hydration classification."""
    if value is None:
        return None

    normalized_value = value.strip().lower()
    if not normalized_value:
        return None

    if normalized_value not in ALLOWED_HYDRATION_KINDS:
        raise BrizelFoodValidationError(
            f"hydration_kind must be one of {sorted(ALLOWED_HYDRATION_KINDS)}."
        )

    return normalized_value


def validate_hydration_ml_per_100g(value: float | int | None) -> float | None:
    """Validate optional hydration amount metadata."""
    if value is None:
        return None

    normalized_value = float(value)
    if normalized_value < 0:
        raise BrizelFoodValidationError(
            "hydration_ml_per_100g must be greater than or equal to 0."
        )

    return normalized_value


def validate_hydration_source(value: str | None) -> str | None:
    """Validate and normalize hydration source metadata."""
    if value is None:
        return None

    normalized_value = value.strip().lower()
    if not normalized_value:
        return None

    if normalized_value not in ALLOWED_HYDRATION_SOURCES:
        raise BrizelFoodValidationError(
            f"hydration_source must be one of {sorted(ALLOWED_HYDRATION_SOURCES)}."
        )

    return normalized_value


def validate_hydration_metadata(
    hydration_kind: str | None,
    hydration_ml_per_100g: float | int | None,
    hydration_source: str | None = None,
) -> tuple[str | None, float | None, str | None]:
    """Validate hydration metadata as one coherent pair."""
    normalized_kind = validate_hydration_kind(hydration_kind)
    normalized_hydration = validate_hydration_ml_per_100g(hydration_ml_per_100g)
    normalized_source = validate_hydration_source(hydration_source)

    if (normalized_kind is None) != (normalized_hydration is None):
        raise BrizelFoodValidationError(
            "hydration_kind and hydration_ml_per_100g must either both be set or both be omitted."
        )
    if normalized_kind is None and normalized_source is not None:
        raise BrizelFoodValidationError(
            "hydration_source requires hydration metadata."
        )

    return normalized_kind, normalized_hydration, normalized_source


@dataclass(slots=True)
class Food:
    """Food catalog entry."""

    food_id: str
    name: str
    brand: str | None
    barcode: str | None
    kcal_per_100g: float
    protein_per_100g: float
    carbs_per_100g: float
    fat_per_100g: float
    created_at: str
    hydration_kind: str | None = None
    hydration_ml_per_100g: float | None = None
    hydration_source: str | None = None
    compatibility: FoodCompatibilityMetadata | None = None

    @classmethod
    def create(
        cls,
        name: str,
        kcal_per_100g: float | int,
        protein_per_100g: float | int,
        carbs_per_100g: float | int,
        fat_per_100g: float | int,
        brand: str | None = None,
        barcode: str | None = None,
        hydration_kind: str | None = None,
        hydration_ml_per_100g: float | int | None = None,
        hydration_source: str | None = None,
        compatibility: FoodCompatibilityMetadata | None = None,
    ) -> "Food":
        """Create a validated food catalog entry."""
        normalized_name = normalize_food_name(name)

        if not normalized_name:
            raise BrizelFoodValidationError("A food name is required.")

        normalized_hydration_kind, normalized_hydration_ml, normalized_hydration_source = (
            validate_hydration_metadata(
                hydration_kind=hydration_kind,
                hydration_ml_per_100g=hydration_ml_per_100g,
                hydration_source=hydration_source,
            )
        )

        return cls(
            food_id=generate_food_id(),
            name=normalized_name,
            brand=normalize_optional_text(brand),
            barcode=normalize_optional_text(barcode),
            kcal_per_100g=validate_macro_value("kcal_per_100g", kcal_per_100g),
            protein_per_100g=validate_macro_value(
                "protein_per_100g", protein_per_100g
            ),
            carbs_per_100g=validate_macro_value("carbs_per_100g", carbs_per_100g),
            fat_per_100g=validate_macro_value("fat_per_100g", fat_per_100g),
            created_at=datetime.now(UTC).isoformat(),
            hydration_kind=normalized_hydration_kind,
            hydration_ml_per_100g=normalized_hydration_ml,
            hydration_source=normalized_hydration_source,
            compatibility=compatibility,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Food":
        """Create a food model from persisted legacy data."""
        food_id = str(data.get("food_id", "")).strip()
        name = normalize_food_name(str(data.get("name", "")))
        created_at = str(data.get("created_at", "")).strip()

        if not food_id:
            raise BrizelFoodValidationError("A food ID is required.")
        if not name:
            raise BrizelFoodValidationError("A food name is required.")
        if not created_at:
            raise BrizelFoodValidationError("created_at is required.")

        normalized_hydration_kind, normalized_hydration_ml, normalized_hydration_source = (
            validate_hydration_metadata(
                hydration_kind=data.get("hydration_kind"),
                hydration_ml_per_100g=data.get("hydration_ml_per_100g"),
                hydration_source=data.get("hydration_source"),
            )
        )
        compatibility_data = data.get("compatibility")
        compatibility = None
        if isinstance(compatibility_data, dict):
            parsed_compatibility = FoodCompatibilityMetadata.from_dict(
                compatibility_data
            )
            if parsed_compatibility.has_known_metadata():
                compatibility = parsed_compatibility

        return cls(
            food_id=food_id,
            name=name,
            brand=normalize_optional_text(data.get("brand")),
            barcode=normalize_optional_text(data.get("barcode")),
            kcal_per_100g=validate_macro_value(
                "kcal_per_100g",
                data.get("kcal_per_100g", 0),
            ),
            protein_per_100g=validate_macro_value(
                "protein_per_100g",
                data.get("protein_per_100g", 0),
            ),
            carbs_per_100g=validate_macro_value(
                "carbs_per_100g",
                data.get("carbs_per_100g", 0),
            ),
            fat_per_100g=validate_macro_value(
                "fat_per_100g",
                data.get("fat_per_100g", 0),
            ),
            created_at=created_at,
            hydration_kind=normalized_hydration_kind,
            hydration_ml_per_100g=normalized_hydration_ml,
            hydration_source=normalized_hydration_source,
            compatibility=compatibility,
        )

    def update(
        self,
        name: str,
        kcal_per_100g: float | int,
        protein_per_100g: float | int,
        carbs_per_100g: float | int,
        fat_per_100g: float | int,
        brand: str | None = None,
        barcode: str | None = None,
        hydration_kind: str | None | object = _UNSET,
        hydration_ml_per_100g: float | int | None | object = _UNSET,
        hydration_source: str | None | object = _UNSET,
        compatibility: FoodCompatibilityMetadata | None | object = _UNSET,
    ) -> None:
        """Update mutable food catalog fields."""
        normalized_name = normalize_food_name(name)
        if not normalized_name:
            raise BrizelFoodValidationError("A food name is required.")

        if (
            hydration_kind is _UNSET
            and hydration_ml_per_100g is _UNSET
            and hydration_source is _UNSET
        ):
            normalized_hydration_kind = self.hydration_kind
            normalized_hydration_ml = self.hydration_ml_per_100g
            normalized_hydration_source = self.hydration_source
        elif (
            hydration_kind is _UNSET
            or hydration_ml_per_100g is _UNSET
            or hydration_source is _UNSET
        ):
            raise BrizelFoodValidationError(
                "hydration_kind, hydration_ml_per_100g and hydration_source must either be provided together or all be omitted."
            )
        else:
            (
                normalized_hydration_kind,
                normalized_hydration_ml,
                normalized_hydration_source,
            ) = (
                validate_hydration_metadata(
                    hydration_kind=hydration_kind,
                    hydration_ml_per_100g=hydration_ml_per_100g,
                    hydration_source=hydration_source,
                )
            )

        self.name = normalized_name
        self.brand = normalize_optional_text(brand)
        self.barcode = normalize_optional_text(barcode)
        self.kcal_per_100g = validate_macro_value("kcal_per_100g", kcal_per_100g)
        self.protein_per_100g = validate_macro_value(
            "protein_per_100g", protein_per_100g
        )
        self.carbs_per_100g = validate_macro_value(
            "carbs_per_100g", carbs_per_100g
        )
        self.fat_per_100g = validate_macro_value("fat_per_100g", fat_per_100g)
        self.hydration_kind = normalized_hydration_kind
        self.hydration_ml_per_100g = normalized_hydration_ml
        self.hydration_source = normalized_hydration_source
        if compatibility is not _UNSET:
            self.compatibility = compatibility

    def has_hydration_data(self) -> bool:
        """Return whether the food carries trusted hydration metadata."""
        return (
            self.hydration_kind is not None
            and self.hydration_ml_per_100g is not None
        )

    def set_hydration_metadata(
        self,
        hydration_kind: str | None,
        hydration_ml_per_100g: float | int | None,
        hydration_source: str | None,
    ) -> None:
        """Set or replace hydration metadata without changing catalog nutrition fields."""
        (
            self.hydration_kind,
            self.hydration_ml_per_100g,
            self.hydration_source,
        ) = validate_hydration_metadata(
            hydration_kind=hydration_kind,
            hydration_ml_per_100g=hydration_ml_per_100g,
            hydration_source=hydration_source,
        )

    def clear_hydration_metadata(self) -> None:
        """Remove hydration metadata from the food."""
        self.hydration_kind = None
        self.hydration_ml_per_100g = None
        self.hydration_source = None

    def has_compatibility_metadata(self) -> bool:
        """Return whether trusted food compatibility metadata is available."""
        return (
            self.compatibility is not None
            and self.compatibility.has_known_metadata()
        )

    def set_compatibility_metadata(
        self,
        compatibility: FoodCompatibilityMetadata,
    ) -> None:
        """Set trusted compatibility metadata on the food."""
        self.compatibility = compatibility

    def clear_compatibility_metadata(self) -> None:
        """Remove compatibility metadata from the food."""
        self.compatibility = None

    def is_hydration_drink(self) -> bool:
        """Return whether the food should count as a directly consumed drink."""
        return self.hydration_kind == HYDRATION_KIND_DRINK

    def is_hydration_food(self) -> bool:
        """Return whether the food contributes hydration as a food."""
        return self.hydration_kind == HYDRATION_KIND_FOOD

    def calculate_hydration_ml(self, grams: float | int) -> float:
        """Calculate hydration for a consumed amount using the catalog metadata."""
        if not self.has_hydration_data():
            return 0.0

        return round(float(self.hydration_ml_per_100g) * (float(grams) / 100.0), 2)

    def get_hydration_source(self) -> str:
        """Return the hydration metadata source or an honest unknown state."""
        if not self.has_hydration_data():
            return HYDRATION_SOURCE_UNKNOWN
        if self.hydration_source is None:
            return HYDRATION_SOURCE_UNKNOWN
        return self.hydration_source

    def to_dict(self) -> dict[str, Any]:
        """Serialize the food using the legacy storage shape."""
        data = {
            "food_id": self.food_id,
            "name": self.name,
            "brand": self.brand,
            "barcode": self.barcode,
            "kcal_per_100g": self.kcal_per_100g,
            "protein_per_100g": self.protein_per_100g,
            "carbs_per_100g": self.carbs_per_100g,
            "fat_per_100g": self.fat_per_100g,
            "created_at": self.created_at,
        }

        if self.hydration_kind is not None:
            data["hydration_kind"] = self.hydration_kind
        if self.hydration_ml_per_100g is not None:
            data["hydration_ml_per_100g"] = self.hydration_ml_per_100g
        if self.hydration_source is not None:
            data["hydration_source"] = self.hydration_source
        if self.has_compatibility_metadata():
            data["compatibility"] = self.compatibility.to_dict()

        return data
