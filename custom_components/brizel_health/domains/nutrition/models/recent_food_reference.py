"""Recent food reference stored per profile."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ..errors import BrizelFoodValidationError


def _normalize_required_text(value: str, field_name: str) -> str:
    """Normalize a required text field."""
    normalized = value.strip()
    if not normalized:
        raise BrizelFoodValidationError(f"{field_name} is required.")
    return normalized


def _normalize_timestamp(value: str) -> str:
    """Validate and normalize a required ISO timestamp."""
    normalized = value.strip()
    if not normalized:
        raise BrizelFoodValidationError("last_used_at is required.")

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as err:
        raise BrizelFoodValidationError(
            "last_used_at must be a valid ISO datetime string."
        ) from err

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC).isoformat()


def _normalize_use_count(value: int | None) -> int:
    """Validate and normalize one recent-food use counter."""
    normalized = 1 if value is None else int(value)
    if normalized <= 0:
        raise BrizelFoodValidationError("use_count must be greater than 0.")
    return normalized


def _normalize_optional_logged_grams(value: float | int | None) -> float | None:
    """Validate an optional last-logged gram amount."""
    if value is None:
        return None

    normalized = float(value)
    if normalized <= 0:
        raise BrizelFoodValidationError(
            "last_logged_grams must be greater than 0 when provided."
        )
    return normalized


def _normalize_optional_meal_type(value: str | None) -> str | None:
    """Normalize the last meal type associated with one recent-food reference."""
    if value is None:
        return None

    normalized = value.strip().lower()
    if not normalized:
        return None

    allowed = {"breakfast", "lunch", "dinner", "snack"}
    if normalized not in allowed:
        raise BrizelFoodValidationError(
            f"last_meal_type must be one of {sorted(allowed)}."
        )
    return normalized


@dataclass(slots=True)
class RecentFoodReference:
    """Recent-food reference without duplicating food data."""

    food_id: str
    last_used_at: str
    use_count: int = 1
    last_logged_grams: float | None = None
    last_meal_type: str | None = None
    is_favorite: bool = False

    @classmethod
    def create(
        cls,
        food_id: str,
        last_used_at: str | None = None,
        use_count: int | None = None,
        last_logged_grams: float | int | None = None,
        last_meal_type: str | None = None,
        is_favorite: bool = False,
    ) -> "RecentFoodReference":
        """Create a validated recent-food reference."""
        resolved_last_used_at = (
            datetime.now(UTC).isoformat()
            if last_used_at is None
            else last_used_at
        )
        return cls(
            food_id=_normalize_required_text(food_id, "food_id"),
            last_used_at=_normalize_timestamp(resolved_last_used_at),
            use_count=_normalize_use_count(use_count),
            last_logged_grams=_normalize_optional_logged_grams(last_logged_grams),
            last_meal_type=_normalize_optional_meal_type(last_meal_type),
            is_favorite=bool(is_favorite),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RecentFoodReference":
        """Create a recent-food reference from persisted data."""
        return cls.create(
            food_id=str(data.get("food_id", "")),
            last_used_at=str(data.get("last_used_at", "")),
            use_count=data.get("use_count"),
            last_logged_grams=data.get("last_logged_grams"),
            last_meal_type=data.get("last_meal_type"),
            is_favorite=bool(data.get("is_favorite", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the recent-food reference."""
        return {
            "food_id": self.food_id,
            "last_used_at": self.last_used_at,
            "use_count": self.use_count,
            "last_logged_grams": self.last_logged_grams,
            "last_meal_type": self.last_meal_type,
            "is_favorite": self.is_favorite,
        }
