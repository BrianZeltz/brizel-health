"""Local cache entry for imported foods."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ..errors import BrizelImportedFoodValidationError
from .imported_food_data import ImportedFoodData


def _normalize_required_text(value: str, field_name: str) -> str:
    """Normalize a required text field."""
    normalized = value.strip()
    if not normalized:
        raise BrizelImportedFoodValidationError(f"{field_name} is required.")
    return normalized


def _normalize_required_timestamp(value: str) -> str:
    """Validate and normalize a required ISO timestamp."""
    normalized = value.strip()
    if not normalized:
        raise BrizelImportedFoodValidationError("last_synced_at is required.")

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as err:
        raise BrizelImportedFoodValidationError(
            "last_synced_at must be a valid ISO datetime string."
        ) from err

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC).isoformat()


@dataclass(slots=True)
class ImportedFoodCacheEntry:
    """Cached imported food snapshot linked to an internal food ID."""

    source_name: str
    source_id: str
    food_id: str
    imported_food: ImportedFoodData
    last_synced_at: str

    @classmethod
    def create(
        cls,
        source_name: str,
        source_id: str,
        food_id: str,
        imported_food: ImportedFoodData,
        last_synced_at: str | None = None,
    ) -> "ImportedFoodCacheEntry":
        """Create a validated imported food cache entry."""
        resolved_last_synced_at = (
            imported_food.fetched_at
            if last_synced_at is None
            else last_synced_at
        )
        normalized_source_name = _normalize_required_text(
            source_name,
            "source_name",
        ).lower()
        normalized_source_id = _normalize_required_text(source_id, "source_id")

        if imported_food.source_name != normalized_source_name:
            raise BrizelImportedFoodValidationError(
                "cache entry source_name must match imported_food.source_name."
            )
        if imported_food.source_id != normalized_source_id:
            raise BrizelImportedFoodValidationError(
                "cache entry source_id must match imported_food.source_id."
            )

        return cls(
            source_name=normalized_source_name,
            source_id=normalized_source_id,
            food_id=_normalize_required_text(food_id, "food_id"),
            imported_food=imported_food,
            last_synced_at=_normalize_required_timestamp(resolved_last_synced_at),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImportedFoodCacheEntry":
        """Create a cache entry from persisted data."""
        imported_food_data = data.get("imported_food")
        if not isinstance(imported_food_data, dict):
            raise BrizelImportedFoodValidationError(
                "imported_food cache data is required."
            )

        return cls.create(
            source_name=str(data.get("source_name", "")),
            source_id=str(data.get("source_id", "")),
            food_id=str(data.get("food_id", "")),
            imported_food=ImportedFoodData.from_dict(imported_food_data),
            last_synced_at=str(data.get("last_synced_at", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the cache entry."""
        return {
            "source_name": self.source_name,
            "source_id": self.source_id,
            "food_id": self.food_id,
            "last_synced_at": self.last_synced_at,
            "imported_food": self.imported_food.to_dict(),
        }
