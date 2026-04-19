"""Food entry model for Brizel Health."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from ..common import normalize_optional_text
from ..errors import BrizelFoodEntryValidationError
from .food import Food

FOOD_LOG_RECORD_TYPE = "food_log"
FOOD_LOG_PAYLOAD_VERSION = 1
FOOD_LOG_DEFAULT_NODE_ID = "home_assistant"
FOOD_ENTRY_SOURCE_MANUAL = "manual"
FOOD_ENTRY_SOURCE_BARCODE = "barcode"
FOOD_ENTRY_SOURCE_PHOTO_AI = "photo_ai"
FOOD_ENTRY_SOURCE_IMPORTED = "imported"
FOOD_LOG_SOURCE_TYPE_MANUAL = "manual"
FOOD_LOG_SOURCE_TYPE_EXTERNAL_IMPORT = "external_import"
FOOD_LOG_SOURCE_DETAIL_HOME_ASSISTANT = "home_assistant"
FOOD_LOG_SOURCE_DETAIL_BARCODE = "barcode"
FOOD_LOG_SOURCE_DETAIL_PHOTO_AI = "photo_ai"
FOOD_LOG_SOURCE_DETAIL_IMPORTED_FOOD = "imported_food"
FOOD_LOG_SOURCE_DETAIL_UNKNOWN = "unknown"
ALLOWED_FOOD_ENTRY_SOURCES = {
    FOOD_ENTRY_SOURCE_MANUAL,
    FOOD_ENTRY_SOURCE_BARCODE,
    FOOD_ENTRY_SOURCE_PHOTO_AI,
    FOOD_ENTRY_SOURCE_IMPORTED,
}
LEGACY_SOURCE_TO_CORE_SOURCE = {
    FOOD_ENTRY_SOURCE_MANUAL: (
        FOOD_LOG_SOURCE_TYPE_MANUAL,
        FOOD_LOG_SOURCE_DETAIL_HOME_ASSISTANT,
    ),
    FOOD_ENTRY_SOURCE_BARCODE: (
        FOOD_LOG_SOURCE_TYPE_EXTERNAL_IMPORT,
        FOOD_LOG_SOURCE_DETAIL_BARCODE,
    ),
    FOOD_ENTRY_SOURCE_PHOTO_AI: (
        FOOD_LOG_SOURCE_TYPE_EXTERNAL_IMPORT,
        FOOD_LOG_SOURCE_DETAIL_PHOTO_AI,
    ),
    FOOD_ENTRY_SOURCE_IMPORTED: (
        FOOD_LOG_SOURCE_TYPE_EXTERNAL_IMPORT,
        FOOD_LOG_SOURCE_DETAIL_IMPORTED_FOOD,
    ),
}
_UNSET = object()


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
    if source is None:
        return FOOD_ENTRY_SOURCE_MANUAL

    normalized = source.strip().lower()
    if not normalized:
        return FOOD_ENTRY_SOURCE_MANUAL
    if normalized not in ALLOWED_FOOD_ENTRY_SOURCES:
        raise BrizelFoodEntryValidationError(
            f"source must be one of {sorted(ALLOWED_FOOD_ENTRY_SOURCES)}."
        )
    return normalized


def _normalize_required_text(value: object, field_name: str) -> str:
    """Normalize a required text value."""
    normalized = str(value or "").strip()
    if not normalized:
        raise BrizelFoodEntryValidationError(f"{field_name} is required.")
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


def _normalize_optional_timestamp(value: object | None, field_name: str) -> str | None:
    """Validate and normalize an optional ISO timestamp."""
    if value is None or not str(value).strip():
        return None
    return normalize_required_timestamp(str(value), field_name)


def _normalize_positive_int(value: object, field_name: str) -> int:
    """Validate and normalize one positive integer."""
    try:
        parsed = int(value)
    except (TypeError, ValueError) as err:
        raise BrizelFoodEntryValidationError(
            f"{field_name} must be an integer."
        ) from err
    if parsed < 1:
        raise BrizelFoodEntryValidationError(f"{field_name} must be positive.")
    return parsed


def _normalize_record_type(value: object | None) -> str:
    """Validate and normalize the food-log record type."""
    normalized = _normalize_required_text(
        value or FOOD_LOG_RECORD_TYPE,
        "record_type",
    )
    if normalized != FOOD_LOG_RECORD_TYPE:
        raise BrizelFoodEntryValidationError(
            f"record_type must be '{FOOD_LOG_RECORD_TYPE}'."
        )
    return normalized


def _normalize_core_source(
    *,
    source_type: object | None = None,
    source_detail: object | None = None,
    legacy_source: object | None = None,
) -> tuple[str, str]:
    """Normalize legacy and Core source fields into source_type/source_detail."""
    if source_type is None or not str(source_type).strip():
        legacy = validate_source(str(legacy_source) if legacy_source is not None else None)
        return LEGACY_SOURCE_TO_CORE_SOURCE[legacy]

    normalized_type = _normalize_required_text(source_type, "source_type").lower()
    detail = normalize_optional_text(
        str(source_detail) if source_detail is not None else None
    )
    if normalized_type == "manual_entry":
        normalized_type = FOOD_LOG_SOURCE_TYPE_MANUAL
        if detail is None or detail == FOOD_LOG_SOURCE_DETAIL_UNKNOWN:
            detail = FOOD_LOG_SOURCE_DETAIL_HOME_ASSISTANT
    if detail is None:
        if legacy_source is not None and str(legacy_source).strip():
            legacy = validate_source(str(legacy_source))
            _default_type, detail = LEGACY_SOURCE_TO_CORE_SOURCE[legacy]
        elif normalized_type == FOOD_LOG_SOURCE_TYPE_MANUAL:
            detail = FOOD_LOG_SOURCE_DETAIL_HOME_ASSISTANT
        else:
            detail = FOOD_LOG_SOURCE_DETAIL_UNKNOWN
    return normalized_type, detail.lower()


def _legacy_source_from_core_source(source_type: str, source_detail: str) -> str:
    """Return the legacy source string for existing service responses."""
    if source_type == FOOD_LOG_SOURCE_TYPE_MANUAL:
        return FOOD_ENTRY_SOURCE_MANUAL
    if source_detail == FOOD_LOG_SOURCE_DETAIL_BARCODE:
        return FOOD_ENTRY_SOURCE_BARCODE
    if source_detail == FOOD_LOG_SOURCE_DETAIL_PHOTO_AI:
        return FOOD_ENTRY_SOURCE_PHOTO_AI
    return FOOD_ENTRY_SOURCE_IMPORTED


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
    """Persisted food-log CoreRecord for one consumed food."""

    record_id: str
    record_type: str
    profile_id: str
    source_type: str
    source_detail: str
    origin_node_id: str
    created_at: str
    updated_at: str
    updated_by_node_id: str
    revision: int
    payload_version: int
    deleted_at: str | None
    food_id: str
    food_name: str
    food_brand: str | None
    amount_grams: float
    meal_type: str | None
    note: str | None
    consumed_at: str
    kcal: float
    protein: float
    carbs: float
    fat: float

    @property
    def food_entry_id(self) -> str:
        """Legacy alias for the canonical CoreRecord identity."""
        return self.record_id

    @property
    def grams(self) -> float:
        """Legacy amount alias for existing nutrition queries and services."""
        return self.amount_grams

    @property
    def source(self) -> str:
        """Legacy source view for existing HA service responses."""
        return _legacy_source_from_core_source(self.source_type, self.source_detail)

    @property
    def is_deleted(self) -> bool:
        """Return whether the food-log record is tombstoned."""
        return self.deleted_at is not None

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
        source_type, source_detail = _normalize_core_source(
            legacy_source=source_value,
        )
        macros = calculate_food_entry_macros(food, grams_value)
        now = datetime.now(UTC).isoformat()
        record_id = generate_food_entry_id()

        return cls(
            record_id=record_id,
            record_type=FOOD_LOG_RECORD_TYPE,
            profile_id=normalized_profile_id,
            source_type=source_type,
            source_detail=source_detail,
            origin_node_id=FOOD_LOG_DEFAULT_NODE_ID,
            created_at=now,
            updated_at=now,
            updated_by_node_id=FOOD_LOG_DEFAULT_NODE_ID,
            revision=1,
            payload_version=FOOD_LOG_PAYLOAD_VERSION,
            deleted_at=None,
            food_id=food.food_id,
            food_name=food.name,
            food_brand=food.brand,
            amount_grams=grams_value,
            meal_type=meal_type_value,
            note=note_value,
            consumed_at=consumed_at_value,
            kcal=macros["kcal"],
            protein=macros["protein"],
            carbs=macros["carbs"],
            fat=macros["fat"],
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FoodEntry":
        """Create a food-log CoreRecord from persisted current or legacy data."""
        record_id = str(data.get("record_id") or data.get("food_entry_id") or "").strip()
        profile_id = str(data.get("profile_id", "")).strip()
        food_id = str(data.get("food_id", "")).strip()
        food_name = str(data.get("food_name", "")).strip()

        if not record_id:
            raise BrizelFoodEntryValidationError("record_id is required.")
        if not profile_id:
            raise BrizelFoodEntryValidationError("A profile ID is required.")
        if not food_id:
            raise BrizelFoodEntryValidationError("A food ID is required.")
        if not food_name:
            raise BrizelFoodEntryValidationError("food_name is required.")

        created_at = normalize_required_timestamp(
            str(data.get("created_at", "")),
            "created_at",
        )
        updated_at = normalize_required_timestamp(
            str(data.get("updated_at", created_at)),
            "updated_at",
        )
        origin_node_id = _normalize_required_text(
            data.get("origin_node_id") or FOOD_LOG_DEFAULT_NODE_ID,
            "origin_node_id",
        )
        source_type, source_detail = _normalize_core_source(
            source_type=data.get("source_type"),
            source_detail=data.get("source_detail"),
            legacy_source=data.get("source"),
        )

        return cls(
            record_id=record_id,
            record_type=_normalize_record_type(data.get("record_type")),
            profile_id=profile_id,
            source_type=source_type,
            source_detail=source_detail,
            origin_node_id=origin_node_id,
            created_at=created_at,
            updated_at=updated_at,
            updated_by_node_id=_normalize_required_text(
                data.get("updated_by_node_id") or origin_node_id,
                "updated_by_node_id",
            ),
            revision=_normalize_positive_int(data.get("revision", 1), "revision"),
            payload_version=_normalize_positive_int(
                data.get("payload_version", FOOD_LOG_PAYLOAD_VERSION),
                "payload_version",
            ),
            deleted_at=_normalize_optional_timestamp(
                data.get("deleted_at"),
                "deleted_at",
            ),
            food_id=food_id,
            food_name=food_name,
            food_brand=normalize_optional_text(data.get("food_brand")),
            amount_grams=validate_grams(
                data.get("amount_grams", data.get("grams", 0))
            ),
            meal_type=validate_meal_type(data.get("meal_type")),
            note=normalize_optional_text(data.get("note")),
            consumed_at=normalize_required_timestamp(
                str(data.get("consumed_at", "")),
                "consumed_at",
            ),
            kcal=round(float(data.get("kcal", 0)), 2),
            protein=round(float(data.get("protein", 0)), 2),
            carbs=round(float(data.get("carbs", 0)), 2),
            fat=round(float(data.get("fat", 0)), 2),
        )

    def update(
        self,
        *,
        amount_grams: float | int | None = None,
        consumed_at: str | None = None,
        meal_type: str | None | object = _UNSET,
        note: str | None | object = _UNSET,
        source: str | None = None,
        kcal: float | int | None = None,
        protein: float | int | None = None,
        carbs: float | int | None = None,
        fat: float | int | None = None,
        updated_by_node_id: str | None = None,
    ) -> None:
        """Update mutable food-log payload fields and advance revision."""
        if amount_grams is not None:
            self.amount_grams = validate_grams(amount_grams)
        if consumed_at is not None:
            self.consumed_at = normalize_required_timestamp(
                consumed_at,
                "consumed_at",
            )
        if meal_type is not _UNSET:
            self.meal_type = validate_meal_type(meal_type)
        if note is not _UNSET:
            self.note = normalize_optional_text(note)
        if source is not None:
            self.source_type, self.source_detail = _normalize_core_source(
                legacy_source=source,
            )
        if kcal is not None:
            self.kcal = round(float(kcal), 2)
        if protein is not None:
            self.protein = round(float(protein), 2)
        if carbs is not None:
            self.carbs = round(float(carbs), 2)
        if fat is not None:
            self.fat = round(float(fat), 2)

        self.updated_at = datetime.now(UTC).isoformat()
        self.updated_by_node_id = _normalize_required_text(
            updated_by_node_id or self.origin_node_id,
            "updated_by_node_id",
        )
        self.revision += 1

    def mark_deleted(
        self,
        *,
        deleted_at: str | None = None,
        updated_by_node_id: str | None = None,
    ) -> None:
        """Tombstone the food-log record without losing payload data."""
        timestamp = (
            normalize_required_timestamp(deleted_at, "deleted_at")
            if deleted_at is not None
            else datetime.now(UTC).isoformat()
        )
        self.deleted_at = timestamp
        self.updated_at = timestamp
        self.updated_by_node_id = _normalize_required_text(
            updated_by_node_id or self.origin_node_id,
            "updated_by_node_id",
        )
        self.revision += 1

    def restore(self, *, updated_by_node_id: str | None = None) -> None:
        """Restore a tombstoned food-log record."""
        self.deleted_at = None
        self.updated_at = datetime.now(UTC).isoformat()
        self.updated_by_node_id = _normalize_required_text(
            updated_by_node_id or self.origin_node_id,
            "updated_by_node_id",
        )
        self.revision += 1

    def to_dict(self) -> dict[str, Any]:
        """Serialize the food-log CoreRecord with legacy aliases."""
        data = {
            "record_id": self.record_id,
            "record_type": self.record_type,
            "food_entry_id": self.food_entry_id,
            "profile_id": self.profile_id,
            "source_type": self.source_type,
            "source_detail": self.source_detail,
            "origin_node_id": self.origin_node_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "updated_by_node_id": self.updated_by_node_id,
            "revision": self.revision,
            "payload_version": self.payload_version,
            "deleted_at": self.deleted_at,
            "food_id": self.food_id,
            "food_name": self.food_name,
            "food_brand": self.food_brand,
            "amount_grams": self.amount_grams,
            "grams": self.grams,
            "note": self.note,
            "source": self.source,
            "consumed_at": self.consumed_at,
            "kcal": self.kcal,
            "protein": self.protein,
            "carbs": self.carbs,
            "fat": self.fat,
        }
        if self.meal_type is not None:
            data["meal_type"] = self.meal_type
        return data
