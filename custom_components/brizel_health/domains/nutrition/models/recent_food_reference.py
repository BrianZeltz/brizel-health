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


@dataclass(slots=True)
class RecentFoodReference:
    """Recent-food reference without duplicating food data."""

    food_id: str
    last_used_at: str

    @classmethod
    def create(
        cls,
        food_id: str,
        last_used_at: str | None = None,
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
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RecentFoodReference":
        """Create a recent-food reference from persisted data."""
        return cls.create(
            food_id=str(data.get("food_id", "")),
            last_used_at=str(data.get("last_used_at", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the recent-food reference."""
        return {
            "food_id": self.food_id,
            "last_used_at": self.last_used_at,
        }
