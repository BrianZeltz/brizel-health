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
    origin_node_id: str | None = None
    source_type: str | None = None
    source_detail: str | None = None
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None
    updated_by_node_id: str | None = None
    revision: int = 1
    payload_version: str = "1.0"

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
        if end <= start:
            raise ValueError("end must be after start.")
        if int(self.steps) < 0:
            raise ValueError("steps must not be negative.")
        if int(self.revision) < 1:
            raise ValueError("revision must be positive.")

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
        object.__setattr__(
            self,
            "updated_by_node_id",
            _normalize_optional_text(self.updated_by_node_id) or self.origin_node_id,
        )
        object.__setattr__(self, "revision", int(self.revision))
        object.__setattr__(
            self,
            "payload_version",
            _normalize_required_text(self.payload_version, "payload_version"),
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
            "origin_node_id": self.origin_node_id,
            "source_type": self.source_type,
            "source_detail": self.source_detail,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "updated_by_node_id": self.updated_by_node_id,
            "revision": self.revision,
            "payload_version": self.payload_version,
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
            and self.origin == other.origin
            and self.profile_id == other.profile_id
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
            origin_node_id=data.get("origin_node_id"),
            source_type=data.get("source_type"),
            source_detail=data.get("source_detail"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            updated_by_node_id=data.get("updated_by_node_id"),
            revision=int(data.get("revision", 1)),
            payload_version=data.get("payload_version", "1.0"),
        )
