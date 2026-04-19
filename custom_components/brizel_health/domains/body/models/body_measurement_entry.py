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
BODY_MEASUREMENT_RECORD_TYPE = "body_measurement"
BODY_MEASUREMENT_PAYLOAD_VERSION = 1
BODY_MEASUREMENT_DEFAULT_NODE_ID = "home_assistant"
BODY_MEASUREMENT_SOURCE_TYPE_MANUAL = "manual"
BODY_MEASUREMENT_SOURCE_TYPE_DEVICE_IMPORT = "device_import"
BODY_MEASUREMENT_SOURCE_TYPE_EXTERNAL_IMPORT = "external_import"
BODY_MEASUREMENT_SOURCE_DETAIL_HOME_ASSISTANT = "home_assistant"
BODY_MEASUREMENT_SOURCE_DETAIL_PEER_SYNC = "peer_sync"
BODY_MEASUREMENT_SOURCE_DETAIL_UNKNOWN = "unknown"
ALLOWED_BODY_MEASUREMENT_SOURCES = {
    BODY_MEASUREMENT_SOURCE_MANUAL,
    BODY_MEASUREMENT_SOURCE_IMPORTED,
    BODY_MEASUREMENT_SOURCE_SYNCED,
}
LEGACY_SOURCE_TO_CORE_SOURCE = {
    BODY_MEASUREMENT_SOURCE_MANUAL: (
        BODY_MEASUREMENT_SOURCE_TYPE_MANUAL,
        BODY_MEASUREMENT_SOURCE_DETAIL_HOME_ASSISTANT,
    ),
    BODY_MEASUREMENT_SOURCE_IMPORTED: (
        BODY_MEASUREMENT_SOURCE_TYPE_DEVICE_IMPORT,
        BODY_MEASUREMENT_SOURCE_DETAIL_UNKNOWN,
    ),
    BODY_MEASUREMENT_SOURCE_SYNCED: (
        BODY_MEASUREMENT_SOURCE_TYPE_EXTERNAL_IMPORT,
        BODY_MEASUREMENT_SOURCE_DETAIL_PEER_SYNC,
    ),
}


def _generate_measurement_id() -> str:
    return uuid4().hex


def _normalize_required_text(value: object, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise BrizelBodyMeasurementValidationError(f"{field_name} is required.")
    return normalized


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


def _normalize_optional_timestamp(value: str | None, field_name: str) -> str | None:
    if value is None or not str(value).strip():
        return None
    return _normalize_required_timestamp(str(value), field_name)


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


def _normalize_positive_int(value: object, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as err:
        raise BrizelBodyMeasurementValidationError(
            f"{field_name} must be an integer."
        ) from err
    if parsed < 1:
        raise BrizelBodyMeasurementValidationError(f"{field_name} must be positive.")
    return parsed


def _normalize_record_type(value: object | None) -> str:
    normalized = _normalize_required_text(
        value or BODY_MEASUREMENT_RECORD_TYPE,
        "record_type",
    )
    if normalized != BODY_MEASUREMENT_RECORD_TYPE:
        raise BrizelBodyMeasurementValidationError(
            f"record_type must be '{BODY_MEASUREMENT_RECORD_TYPE}'."
        )
    return normalized


def _normalize_core_source(
    *,
    source_type: object | None = None,
    source_detail: object | None = None,
    legacy_source: object | None = None,
) -> tuple[str, str]:
    if source_type is None or not str(source_type).strip():
        legacy = _validate_measurement_source(
            str(legacy_source) if legacy_source is not None else None
        )
        return LEGACY_SOURCE_TO_CORE_SOURCE[legacy]

    normalized_type = _normalize_required_text(source_type, "source_type").lower()
    detail = _normalize_optional_text(
        str(source_detail) if source_detail is not None else None
    )
    if normalized_type == "manual_entry":
        normalized_type = BODY_MEASUREMENT_SOURCE_TYPE_MANUAL
        if detail is None or detail == BODY_MEASUREMENT_SOURCE_DETAIL_UNKNOWN:
            detail = BODY_MEASUREMENT_SOURCE_DETAIL_HOME_ASSISTANT
    elif normalized_type == "peer_sync":
        normalized_type = BODY_MEASUREMENT_SOURCE_TYPE_EXTERNAL_IMPORT
        if detail is None or detail == BODY_MEASUREMENT_SOURCE_DETAIL_UNKNOWN:
            detail = BODY_MEASUREMENT_SOURCE_DETAIL_PEER_SYNC
    if detail is None:
        if legacy_source is not None and str(legacy_source).strip():
            legacy = _validate_measurement_source(str(legacy_source))
            _default_type, detail = LEGACY_SOURCE_TO_CORE_SOURCE[legacy]
        else:
            detail = BODY_MEASUREMENT_SOURCE_DETAIL_UNKNOWN
    return normalized_type, detail


def _legacy_source_from_core_source(source_type: str) -> str:
    if source_type == BODY_MEASUREMENT_SOURCE_TYPE_MANUAL:
        return BODY_MEASUREMENT_SOURCE_MANUAL
    if source_type == BODY_MEASUREMENT_SOURCE_TYPE_EXTERNAL_IMPORT:
        return BODY_MEASUREMENT_SOURCE_SYNCED
    return BODY_MEASUREMENT_SOURCE_IMPORTED


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
    measurement_type: str
    canonical_value: float
    measured_at: str
    note: str | None

    @property
    def measurement_id(self) -> str:
        """Legacy alias for the canonical CoreRecord identity."""
        return self.record_id

    @property
    def source(self) -> str:
        """Legacy source view for existing HA services and responses."""
        return _legacy_source_from_core_source(self.source_type)

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
        source_type, source_detail = _normalize_core_source(legacy_source=source)
        record_id = _generate_measurement_id()
        return cls(
            record_id=record_id,
            record_type=BODY_MEASUREMENT_RECORD_TYPE,
            profile_id=validate_profile_id(profile_id),
            source_type=source_type,
            source_detail=source_detail,
            origin_node_id=BODY_MEASUREMENT_DEFAULT_NODE_ID,
            created_at=now,
            updated_at=now,
            updated_by_node_id=BODY_MEASUREMENT_DEFAULT_NODE_ID,
            revision=1,
            payload_version=BODY_MEASUREMENT_PAYLOAD_VERSION,
            deleted_at=None,
            measurement_type=normalized_type,
            canonical_value=normalized_value,
            measured_at=_normalize_optional_measured_at(measured_at),
            note=_normalize_optional_text(note),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BodyMeasurementEntry":
        record_id = str(
            data.get("record_id") or data.get("measurement_id") or ""
        ).strip()
        if not record_id:
            raise BrizelBodyMeasurementValidationError(
                "record_id is required."
            )

        normalized_type, normalized_value, _definition = _validate_canonical_value(
            str(data.get("measurement_type", "")),
            data.get("canonical_value"),
        )
        source_type, source_detail = _normalize_core_source(
            source_type=data.get("source_type"),
            source_detail=data.get("source_detail"),
            legacy_source=data.get("source"),
        )
        created_at = _normalize_required_timestamp(
            str(data.get("created_at", "")),
            "created_at",
        )
        updated_at = _normalize_required_timestamp(
            str(data.get("updated_at", created_at)),
            "updated_at",
        )
        origin_node_id = _normalize_required_text(
            data.get("origin_node_id") or BODY_MEASUREMENT_DEFAULT_NODE_ID,
            "origin_node_id",
        )

        return cls(
            record_id=record_id,
            record_type=_normalize_record_type(data.get("record_type")),
            profile_id=validate_profile_id(data.get("profile_id", "")),
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
                data.get("payload_version", BODY_MEASUREMENT_PAYLOAD_VERSION),
                "payload_version",
            ),
            deleted_at=_normalize_optional_timestamp(
                data.get("deleted_at"),
                "deleted_at",
            ),
            measurement_type=normalized_type,
            canonical_value=normalized_value,
            measured_at=_normalize_required_timestamp(
                str(data.get("measured_at", "")),
                "measured_at",
            ),
            note=_normalize_optional_text(data.get("note")),
        )

    def update(
        self,
        *,
        measurement_type: str | None = None,
        canonical_value: float | int | None = None,
        measured_at: str | None = None,
        source: str | None = None,
        note: str | None = None,
        updated_by_node_id: str | None = None,
    ) -> None:
        next_type = (
            measurement_type if measurement_type is not None else self.measurement_type
        )
        next_value = (
            canonical_value if canonical_value is not None else self.canonical_value
        )
        normalized_type, normalized_value, _definition = _validate_canonical_value(
            next_type,
            next_value,
        )
        source_type = self.source_type
        source_detail = self.source_detail
        if source is not None:
            source_type, source_detail = _normalize_core_source(legacy_source=source)

        self.measurement_type = normalized_type
        self.canonical_value = normalized_value
        self.measured_at = (
            _normalize_required_timestamp(measured_at, "measured_at")
            if measured_at is not None
            else self.measured_at
        )
        self.source_type = source_type
        self.source_detail = source_detail
        self.note = _normalize_optional_text(note) if note is not None else self.note
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
        """Mark the measurement as deleted without removing the record."""
        timestamp = (
            _normalize_required_timestamp(deleted_at, "deleted_at")
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "record_type": self.record_type,
            "measurement_id": self.measurement_id,
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
            "measurement_type": self.measurement_type,
            "canonical_value": self.canonical_value,
            "measured_at": self.measured_at,
            "source": self.source,
            "note": self.note,
        }
