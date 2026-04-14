"""Food entry model for Brizel Health."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from ..common import normalize_optional_text
from ..errors import BrizelFoodEntryValidationError
from .food import Food

def generate_food_entry_id() -> str:
    """Generate a stable unique food entry ID."""
    return uuid4().hex


def validate_grams(grams: float | int) -> float:
    """Validate grams value."""
    normalized = float(grams)
    if normalized <= 0:
        raise BrizelFoodEntryValidationError("grams must be greater than 0.")
    return normalized


def normalize_optional_timestamp(consumed_at: str | None) -> str:
    """Normalize or generate an optional consumed timestamp."""
    if consumed_at is None or not consumed_at.strip():
        return datetime.now(UTC).isoformat()

    return normalize_required_timestamp(consumed_at, "consumed_at")


def validate_meal_type(meal_type: str | None) -> str | None:
    """Validate and normalize meal type."""
    allowed = {"breakfast", "lunch", "dinner", "snack"}

    if meal_type is None:
        return None

    normalized = meal_type.strip().lower()
    if not normalized:
        return None
    if normalized not in allowed:
        raise BrizelFoodEntryValidationError(
            f"meal_type must be one of {sorted(allowed)}."
        )
    return normalized


def validate_source(source: str | None) -> str:
    """Validate and normalize source."""
    allowed = {"manual", "barcode", "photo_ai"}

    if source is None:
        return "manual"

    normalized = source.strip().lower()
    if normalized not in allowed:
        raise BrizelFoodEntryValidationError(
            f"source must be one of {sorted(allowed)}."
        )
    return normalized


def normalize_required_timestamp(value: str, field_name: str) -> str:
    """Validate and normalize a required ISO timestamp."""
    normalized = value.strip()
    if not normalized:
        raise BrizelFoodEntryValidationError(f"{field_name} is required.")

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as err:
        raise BrizelFoodEntryValidationError(
            f"{field_name} must be a valid ISO datetime string."
        ) from err

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC).isoformat()


def calculate_food_entry_macros(food: Food, grams: float) -> dict[str, float]:
    """Calculate food entry nutrition values for the given grams."""
    factor = grams / 100.0

    return {
        "kcal": round(food.kcal_per_100g * factor, 2),
        "protein": round(food.protein_per_100g * factor, 2),
        "carbs": round(food.carbs_per_100g * factor, 2),
        "fat": round(food.fat_per_100g * factor, 2),
    }


@dataclass(slots=True)
class FoodEntry:
    """Persisted food consumption entry."""

    food_entry_id: str
    profile_id: str
    food_id: str
    food_name: str
    food_brand: str | None
    grams: float
    meal_type: str | None
    note: str | None
    source: str
    consumed_at: str
    kcal: float
    protein: float
    carbs: float
    fat: float
    created_at: str

    @classmethod
    def create(
        cls,
        profile_id: str,
        food: Food,
        grams: float | int,
        consumed_at: str | None = None,
        meal_type: str | None = None,
        note: str | None = None,
        source: str | None = None,
    ) -> "FoodEntry":
        """Create a validated food entry from a catalog food."""
        normalized_profile_id = profile_id.strip()
        if not normalized_profile_id:
            raise BrizelFoodEntryValidationError("A profile ID is required.")

        grams_value = validate_grams(grams)
        consumed_at_value = normalize_optional_timestamp(consumed_at)
        meal_type_value = validate_meal_type(meal_type)
        note_value = normalize_optional_text(note)
        source_value = validate_source(source)
        macros = calculate_food_entry_macros(food, grams_value)

        return cls(
            food_entry_id=generate_food_entry_id(),
            profile_id=normalized_profile_id,
            food_id=food.food_id,
            food_name=food.name,
            food_brand=food.brand,
            grams=grams_value,
            meal_type=meal_type_value,
            note=note_value,
            source=source_value,
            consumed_at=consumed_at_value,
            kcal=macros["kcal"],
            protein=macros["protein"],
            carbs=macros["carbs"],
            fat=macros["fat"],
            created_at=datetime.now(UTC).isoformat(),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FoodEntry":
        """Create a food entry from persisted legacy data."""
        food_entry_id = str(data.get("food_entry_id", "")).strip()
        profile_id = str(data.get("profile_id", "")).strip()
        food_id = str(data.get("food_id", "")).strip()
        food_name = str(data.get("food_name", "")).strip()

        if not food_entry_id:
            raise BrizelFoodEntryValidationError("A food entry ID is required.")
        if not profile_id:
            raise BrizelFoodEntryValidationError("A profile ID is required.")
        if not food_id:
            raise BrizelFoodEntryValidationError("A food ID is required.")
        if not food_name:
            raise BrizelFoodEntryValidationError("food_name is required.")

        return cls(
            food_entry_id=food_entry_id,
            profile_id=profile_id,
            food_id=food_id,
            food_name=food_name,
            food_brand=normalize_optional_text(data.get("food_brand")),
            grams=validate_grams(data.get("grams", 0)),
            meal_type=validate_meal_type(data.get("meal_type")),
            note=normalize_optional_text(data.get("note")),
            source=validate_source(data.get("source")),
            consumed_at=normalize_required_timestamp(
                str(data.get("consumed_at", "")),
                "consumed_at",
            ),
            kcal=round(float(data.get("kcal", 0)), 2),
            protein=round(float(data.get("protein", 0)), 2),
            carbs=round(float(data.get("carbs", 0)), 2),
            fat=round(float(data.get("fat", 0)), 2),
            created_at=normalize_required_timestamp(
                str(data.get("created_at", "")),
                "created_at",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the entry using the legacy storage shape."""
        data = {
            "food_entry_id": self.food_entry_id,
            "profile_id": self.profile_id,
            "food_id": self.food_id,
            "food_name": self.food_name,
            "food_brand": self.food_brand,
            "grams": self.grams,
            "note": self.note,
            "source": self.source,
            "consumed_at": self.consumed_at,
            "kcal": self.kcal,
            "protein": self.protein,
            "carbs": self.carbs,
            "fat": self.fat,
            "created_at": self.created_at,
        }
        if self.meal_type is not None:
            data["meal_type"] = self.meal_type
        return data
