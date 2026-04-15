"""Persisted body measurement entries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from ..errors import BrizelBodyMeasurementValidationError
from .body_measurement_type import (
    BodyMeasurementTypeDefinition,
    get_body_measurement_type,
)
from .body_profile import validate_profile_id

BODY_MEASUREMENT_SOURCE_MANUAL = "manual"
BODY_MEASUREMENT_SOURCE_IMPORTED = "imported"
BODY_MEASUREMENT_SOURCE_SYNCED = "synced"
ALLOWED_BODY_MEASUREMENT_SOURCES = {
    BODY_MEASUREMENT_SOURCE_MANUAL,
    BODY_MEASUREMENT_SOURCE_IMPORTED,
    BODY_MEASUREMENT_SOURCE_SYNCED,
}


def _generate_measurement_id() -> str:
    return uuid4().hex


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _normalize_required_timestamp(value: str, field_name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise BrizelBodyMeasurementValidationError(f"{field_name} is required.")

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as err:
        raise BrizelBodyMeasurementValidationError(
            f"{field_name} must be a valid ISO datetime string."
        ) from err

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    parsed = parsed.astimezone(UTC)
    if parsed > datetime.now(UTC) + timedelta(days=1):
        raise BrizelBodyMeasurementValidationError(
            f"{field_name} cannot be more than 24 hours in the future."
        )
    return parsed.isoformat()


def _normalize_optional_measured_at(value: str | None) -> str:
    if value is None or not str(value).strip():
        return datetime.now(UTC).isoformat()
    return _normalize_required_timestamp(str(value), "measured_at")


def _validate_measurement_source(source: str | None) -> str:
    if source is None:
        return BODY_MEASUREMENT_SOURCE_MANUAL

    normalized = str(source).strip().lower()
    if not normalized:
        return BODY_MEASUREMENT_SOURCE_MANUAL
    if normalized not in ALLOWED_BODY_MEASUREMENT_SOURCES:
        raise BrizelBodyMeasurementValidationError(
            f"source must be one of {sorted(ALLOWED_BODY_MEASUREMENT_SOURCES)}."
        )
    return normalized


def _validate_canonical_value(
    measurement_type: str,
    canonical_value: float | int,
) -> tuple[str, float, BodyMeasurementTypeDefinition]:
    definition = get_body_measurement_type(measurement_type)
    normalized_value = float(canonical_value)
    if normalized_value <= 0:
        raise BrizelBodyMeasurementValidationError(
            "canonical_value must be greater than 0."
        )

    minimum_value = definition.minimum_canonical_value
    maximum_value = definition.maximum_canonical_value
    if minimum_value is not None and normalized_value < minimum_value:
        raise BrizelBodyMeasurementValidationError(
            f"{definition.key} must be at least {minimum_value} {definition.canonical_unit}."
        )
    if maximum_value is not None and normalized_value > maximum_value:
        raise BrizelBodyMeasurementValidationError(
            f"{definition.key} must be at most {maximum_value} {definition.canonical_unit}."
        )

    return definition.key, round(normalized_value, 4), definition


@dataclass(slots=True)
class BodyMeasurementEntry:
    """One sync-friendly body measurement entry."""

    measurement_id: str
    profile_id: str
    measurement_type: str
    canonical_value: float
    measured_at: str
    source: str
    note: str | None
    created_at: str
    updated_at: str

    @classmethod
    def create(
        cls,
        *,
        profile_id: str,
        measurement_type: str,
        canonical_value: float | int,
        measured_at: str | None = None,
        source: str | None = None,
        note: str | None = None,
    ) -> "BodyMeasurementEntry":
        normalized_type, normalized_value, _definition = _validate_canonical_value(
            measurement_type,
            canonical_value,
        )
        now = datetime.now(UTC).isoformat()
        return cls(
            measurement_id=_generate_measurement_id(),
            profile_id=validate_profile_id(profile_id),
            measurement_type=normalized_type,
            canonical_value=normalized_value,
            measured_at=_normalize_optional_measured_at(measured_at),
            source=_validate_measurement_source(source),
            note=_normalize_optional_text(note),
            created_at=now,
            updated_at=now,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BodyMeasurementEntry":
        measurement_id = str(data.get("measurement_id", "")).strip()
        if not measurement_id:
            raise BrizelBodyMeasurementValidationError(
                "measurement_id is required."
            )

        normalized_type, normalized_value, _definition = _validate_canonical_value(
            str(data.get("measurement_type", "")),
            data.get("canonical_value"),
        )

        return cls(
            measurement_id=measurement_id,
            profile_id=validate_profile_id(data.get("profile_id", "")),
            measurement_type=normalized_type,
            canonical_value=normalized_value,
            measured_at=_normalize_required_timestamp(
                str(data.get("measured_at", "")),
                "measured_at",
            ),
            source=_validate_measurement_source(data.get("source")),
            note=_normalize_optional_text(data.get("note")),
            created_at=_normalize_required_timestamp(
                str(data.get("created_at", "")),
                "created_at",
            ),
            updated_at=_normalize_required_timestamp(
                str(data.get("updated_at", "")),
                "updated_at",
            ),
        )

    def update(
        self,
        *,
        measurement_type: str | None = None,
        canonical_value: float | int | None = None,
        measured_at: str | None = None,
        source: str | None = None,
        note: str | None = None,
    ) -> None:
        next_type = measurement_type if measurement_type is not None else self.measurement_type
        next_value = canonical_value if canonical_value is not None else self.canonical_value
        normalized_type, normalized_value, _definition = _validate_canonical_value(
            next_type,
            next_value,
        )

        self.measurement_type = normalized_type
        self.canonical_value = normalized_value
        self.measured_at = (
            _normalize_required_timestamp(measured_at, "measured_at")
            if measured_at is not None
            else self.measured_at
        )
        self.source = (
            _validate_measurement_source(source) if source is not None else self.source
        )
        self.note = _normalize_optional_text(note) if note is not None else self.note
        self.updated_at = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "measurement_id": self.measurement_id,
            "profile_id": self.profile_id,
            "measurement_type": self.measurement_type,
            "canonical_value": self.canonical_value,
            "measured_at": self.measured_at,
            "source": self.source,
            "note": self.note,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
