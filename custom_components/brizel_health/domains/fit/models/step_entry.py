"""Step entry model for the Fit module."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


def _normalize_required_text(value: object, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} is required.")
    return normalized


def _normalize_optional_text(value: object) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _normalize_datetime(value: datetime | str | None, field_name: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    else:
        raise ValueError(f"{field_name} is required.")

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _normalize_optional_datetime(
    value: datetime | str | None,
    field_name: str,
) -> datetime | None:
    if value is None:
        return None
    normalized = str(value or "").strip()
    if not normalized:
        return None
    return _normalize_datetime(value, field_name)


def _normalize_positive_int(value: object, field_name: str) -> int:
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError(f"{field_name} must be an integer.")
        parsed = int(value)
    else:
        text = str(value or "").strip()
        if "." in text:
            try:
                parsed_float = float(text)
            except ValueError as err:
                raise ValueError(f"{field_name} must be an integer.") from err
            if not parsed_float.is_integer():
                raise ValueError(f"{field_name} must be an integer.")
            parsed = int(parsed_float)
        else:
            try:
                parsed = int(text)
            except ValueError as err:
                raise ValueError(f"{field_name} must be an integer.") from err
    if parsed < 1:
        raise ValueError(f"{field_name} must be positive.")
    return parsed


@dataclass(frozen=True)
class StepEntry:
    """One idempotent step record received through a Fit bridge path."""

    external_record_id: str
    profile_id: str
    message_id: str
    device_id: str
    source: str
    start: datetime
    end: datetime
    steps: int
    received_at: datetime
    timezone: str | None = None
    origin: str | None = None
    record_id: str | None = None
    record_type: str = "steps"
    origin_node_id: str | None = None
    source_type: str | None = None
    source_detail: str | None = None
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None
    updated_by_node_id: str | None = None
    revision: int = 1
    payload_version: int = 1
    deleted_at: datetime | str | None = None
    read_mode: str = "raw"
    data_origin: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "external_record_id",
            _normalize_required_text(self.external_record_id, "external_record_id"),
        )
        object.__setattr__(
            self,
            "profile_id",
            _normalize_required_text(self.profile_id, "profile_id"),
        )
        object.__setattr__(
            self,
            "message_id",
            _normalize_required_text(self.message_id, "message_id"),
        )
        object.__setattr__(
            self,
            "device_id",
            _normalize_required_text(self.device_id, "device_id"),
        )
        object.__setattr__(
            self,
            "source",
            _normalize_required_text(self.source, "source"),
        )

        start = _normalize_datetime(self.start, "start")
        end = _normalize_datetime(self.end, "end")
        received_at = _normalize_datetime(self.received_at, "received_at")
        created_at = (
            _normalize_datetime(self.created_at, "created_at")
            if self.created_at is not None
            else received_at
        )
        updated_at = (
            _normalize_datetime(self.updated_at, "updated_at")
            if self.updated_at is not None
            else created_at
        )
        deleted_at = _normalize_optional_datetime(self.deleted_at, "deleted_at")
        if end <= start:
            raise ValueError("end must be after start.")
        if int(self.steps) < 0:
            raise ValueError("steps must not be negative.")
        revision = _normalize_positive_int(self.revision, "revision")
        payload_version = _normalize_positive_int(
            self.payload_version,
            "payload_version",
        )

        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)
        object.__setattr__(self, "steps", int(self.steps))
        object.__setattr__(self, "received_at", received_at)
        object.__setattr__(self, "timezone", _normalize_optional_text(self.timezone))
        object.__setattr__(self, "origin", _normalize_optional_text(self.origin))
        object.__setattr__(
            self,
            "record_id",
            _normalize_optional_text(self.record_id)
            or f"{self.profile_id}:{self.external_record_id}",
        )
        object.__setattr__(
            self,
            "record_type",
            _normalize_required_text(self.record_type, "record_type"),
        )
        object.__setattr__(
            self,
            "origin_node_id",
            _normalize_optional_text(self.origin_node_id) or self.device_id,
        )
        object.__setattr__(
            self,
            "source_type",
            _normalize_optional_text(self.source_type) or "app_bridge",
        )
        object.__setattr__(
            self,
            "source_detail",
            _normalize_optional_text(self.source_detail) or self.source,
        )
        object.__setattr__(self, "created_at", created_at)
        object.__setattr__(self, "updated_at", updated_at)
        object.__setattr__(self, "deleted_at", deleted_at)
        object.__setattr__(
            self,
            "updated_by_node_id",
            _normalize_optional_text(self.updated_by_node_id) or self.origin_node_id,
        )
        object.__setattr__(self, "revision", revision)
        object.__setattr__(self, "payload_version", payload_version)
        object.__setattr__(
            self,
            "read_mode",
            _normalize_required_text(self.read_mode, "read_mode"),
        )
        object.__setattr__(
            self,
            "data_origin",
            _normalize_optional_text(self.data_origin),
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize the step entry for storage and bridge responses."""
        return {
            "external_record_id": self.external_record_id,
            "profile_id": self.profile_id,
            "message_id": self.message_id,
            "device_id": self.device_id,
            "source": self.source,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "steps": self.steps,
            "received_at": self.received_at.isoformat(),
            "timezone": self.timezone,
            "origin": self.origin,
            "record_id": self.record_id,
            "record_type": self.record_type,
            "origin_node_id": self.origin_node_id,
            "source_type": self.source_type,
            "source_detail": self.source_detail,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "updated_by_node_id": self.updated_by_node_id,
            "revision": self.revision,
            "payload_version": self.payload_version,
            "deleted_at": (
                None if self.deleted_at is None else self.deleted_at.isoformat()
            ),
            "read_mode": self.read_mode,
            "data_origin": self.data_origin,
        }

    def has_same_import_content(self, other: "StepEntry") -> bool:
        """Return whether another import describes the same external step record."""
        return (
            self.external_record_id == other.external_record_id
            and self.profile_id == other.profile_id
            and self.device_id == other.device_id
            and self.source == other.source
            and self.start == other.start
            and self.end == other.end
            and self.steps == other.steps
            and self.timezone == other.timezone
            and self.record_id == other.record_id
            and self.record_type == other.record_type
            and self.origin_node_id == other.origin_node_id
            and self.source_type == other.source_type
            and self.source_detail == other.source_detail
            and self.payload_version == other.payload_version
            and self.deleted_at == other.deleted_at
            and self.read_mode == other.read_mode
            and self.data_origin == other.data_origin
        )

    def updated_from_import(self, other: "StepEntry") -> "StepEntry":
        """Return a revised record that preserves identity and creation metadata."""
        if self.record_id != other.record_id or self.profile_id != other.profile_id:
            raise ValueError("Only the same profile record can be updated.")

        return StepEntry(
            external_record_id=self.external_record_id,
            profile_id=self.profile_id,
            message_id=other.message_id,
            device_id=other.device_id,
            source=other.source,
            start=other.start,
            end=other.end,
            steps=other.steps,
            received_at=other.received_at,
            timezone=other.timezone,
            origin=other.origin,
            record_id=self.record_id,
            record_type=other.record_type,
            origin_node_id=other.origin_node_id,
            source_type=other.source_type,
            source_detail=other.source_detail,
            created_at=self.created_at,
            updated_at=other.updated_at,
            updated_by_node_id=other.updated_by_node_id,
            revision=self.revision + 1,
            payload_version=other.payload_version,
            deleted_at=other.deleted_at,
            read_mode=other.read_mode,
            data_origin=other.data_origin,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StepEntry":
        """Restore a step entry from storage."""
        return cls(
            external_record_id=data.get("external_record_id"),
            profile_id=data.get("profile_id"),
            message_id=data.get("message_id"),
            device_id=data.get("device_id"),
            source=data.get("source"),
            start=data.get("start"),
            end=data.get("end"),
            steps=int(data.get("steps", 0)),
            received_at=data.get("received_at"),
            timezone=data.get("timezone"),
            origin=data.get("origin"),
            record_id=data.get("record_id"),
            record_type=data.get("record_type", "steps"),
            origin_node_id=data.get("origin_node_id"),
            source_type=data.get("source_type"),
            source_detail=data.get("source_detail"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            updated_by_node_id=data.get("updated_by_node_id"),
            revision=data.get("revision", 1),
            payload_version=data.get("payload_version", 1),
            deleted_at=data.get("deleted_at"),
            read_mode=data.get("read_mode", "raw"),
            data_origin=data.get("data_origin"),
        )
