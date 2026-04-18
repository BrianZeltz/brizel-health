"""Schemas and constants for the Brizel Health app bridge."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

BRIDGE_SERVICE_NAME = "brizel_health_app_bridge"
BRIDGE_VERSION = "1.0"
BRIDGE_SCHEMA_VERSION = "1.0"
BRIDGE_AUTH_MODE = "bearer_token"
BRIDGE_SUPPORTED_MODULES = ("profiles", "steps")
BRIDGE_AVAILABLE_ENDPOINTS = (
    "ping",
    "capabilities",
    "profiles",
    "sync_status",
    "steps",
)

ERROR_AUTH_REQUIRED = "AUTH_REQUIRED"
ERROR_AUTH_FAILED = "AUTH_FAILED"
ERROR_UNSUPPORTED_SCHEMA_VERSION = "UNSUPPORTED_SCHEMA_VERSION"
ERROR_INVALID_PAYLOAD = "INVALID_PAYLOAD"
ERROR_INVALID_TIME_RANGE = "INVALID_TIME_RANGE"
ERROR_DUPLICATE_RECORD = "DUPLICATE_RECORD"
ERROR_CONFLICTING_RECORD = "CONFLICTING_RECORD"
ERROR_INTERNAL_ERROR = "INTERNAL_ERROR"
ERROR_PROFILE_NOT_LINKED = "PROFILE_NOT_LINKED"
ERROR_PROFILE_LINK_AMBIGUOUS = "PROFILE_LINK_AMBIGUOUS"
ERROR_PROFILE_ACCESS_DENIED = "PROFILE_ACCESS_DENIED"


class BridgeValidationError(ValueError):
    """Raised when one app bridge request cannot be accepted."""

    def __init__(
        self,
        *,
        error_code: str,
        message: str,
        field_errors: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.field_errors = field_errors or {}


@dataclass(frozen=True)
class StepImportRequest:
    """Validated v1 app bridge request for one step entry import."""

    schema_version: str
    message_id: str
    device_id: str
    source: str
    sent_at: datetime
    external_record_id: str
    start: datetime
    end: datetime
    steps: int
    timezone: str | None = None
    origin: str | None = None
    profile_id: str | None = None


def get_capabilities_payload(*, fit_module_available: bool) -> dict[str, object]:
    """Return the public v1 capabilities payload."""
    return {
        "bridge_version": BRIDGE_VERSION,
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "supported_modules": list(BRIDGE_SUPPORTED_MODULES),
        "fit_module_available": fit_module_available,
        "auth_mode": BRIDGE_AUTH_MODE,
        "profiles_available": True,
        "steps_import_available": fit_module_available,
        "available_endpoints": list(BRIDGE_AVAILABLE_ENDPOINTS),
    }


def serialize_bridge_profile(profile: object) -> dict[str, object]:
    """Serialize one Brizel profile for app bridge clients."""
    return {
        "profile_id": str(getattr(profile, "user_id")),
        "display_name": str(getattr(profile, "display_name")),
        "is_default": False,
    }


def serialize_datetime_for_bridge(value: datetime | None) -> str | None:
    """Serialize optional datetimes for bridge responses."""
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def serialize_bridge_profile_sync_status(
    *,
    profile: object,
    last_steps_sync: datetime | None,
    last_steps_import_status: str | None,
) -> dict[str, object]:
    """Serialize one profile's minimal sync status for app bridge clients."""
    return {
        "profile_id": str(getattr(profile, "user_id")),
        "last_steps_sync": serialize_datetime_for_bridge(last_steps_sync),
        "last_steps_import_status": last_steps_import_status,
    }


def _required_text(
    data: dict[str, Any],
    key: str,
    field_errors: dict[str, str],
) -> str:
    value = data.get(key)
    normalized = str(value or "").strip()
    if not normalized:
        field_errors[key] = "required"
    return normalized


def _optional_text(value: object) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _parse_datetime_field(
    data: dict[str, Any],
    key: str,
    field_errors: dict[str, str],
) -> datetime | None:
    value = data.get(key)
    if not str(value or "").strip():
        field_errors[key] = "required"
        return None
    try:
        return datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        field_errors[key] = "invalid_datetime"
        return None


def _parse_steps(payload: dict[str, Any], field_errors: dict[str, str]) -> int | None:
    value = payload.get("steps")
    if value is None or value == "":
        field_errors["payload.steps"] = "required"
        return None
    if isinstance(value, bool):
        field_errors["payload.steps"] = "invalid_integer"
        return None
    try:
        steps = int(value)
    except (TypeError, ValueError):
        field_errors["payload.steps"] = "invalid_integer"
        return None
    if isinstance(value, float) and not value.is_integer():
        field_errors["payload.steps"] = "invalid_integer"
        return None
    if steps < 0:
        field_errors["payload.steps"] = "must_be_greater_than_or_equal_to_zero"
        return None
    return steps


def parse_step_import_request(data: Any) -> StepImportRequest:
    """Validate and normalize one v1 step import request."""
    if not isinstance(data, dict):
        raise BridgeValidationError(
            error_code=ERROR_INVALID_PAYLOAD,
            message="Request body must be a JSON object.",
            field_errors={"body": "invalid_object"},
        )

    field_errors: dict[str, str] = {}
    schema_version = _required_text(data, "schema_version", field_errors)
    message_id = _required_text(data, "message_id", field_errors)
    device_id = _required_text(data, "device_id", field_errors)
    source = _required_text(data, "source", field_errors)
    sent_at = _parse_datetime_field(data, "sent_at", field_errors)

    payload = data.get("payload")
    if not isinstance(payload, dict):
        field_errors["payload"] = "required"
        payload = {}

    external_record_id = _required_text(
        payload,
        "external_record_id",
        field_errors,
    )
    if "external_record_id" in field_errors:
        field_errors["payload.external_record_id"] = field_errors.pop(
            "external_record_id"
        )
    start = _parse_datetime_field(payload, "start", field_errors)
    if "start" in field_errors:
        field_errors["payload.start"] = field_errors.pop("start")
    end = _parse_datetime_field(payload, "end", field_errors)
    if "end" in field_errors:
        field_errors["payload.end"] = field_errors.pop("end")
    steps = _parse_steps(payload, field_errors)

    if schema_version and schema_version != BRIDGE_SCHEMA_VERSION:
        raise BridgeValidationError(
            error_code=ERROR_UNSUPPORTED_SCHEMA_VERSION,
            message=f"Unsupported schema_version '{schema_version}'.",
            field_errors={"schema_version": "unsupported"},
        )

    if start is not None and end is not None and end <= start:
        raise BridgeValidationError(
            error_code=ERROR_INVALID_TIME_RANGE,
            message="The step entry end time must be after start time.",
            field_errors={"payload.end": "must_be_after_start"},
        )

    if field_errors:
        raise BridgeValidationError(
            error_code=ERROR_INVALID_PAYLOAD,
            message="The step import payload is invalid.",
            field_errors=field_errors,
        )

    return StepImportRequest(
        schema_version=schema_version,
        message_id=message_id,
        device_id=device_id,
        source=source,
        sent_at=sent_at,
        external_record_id=external_record_id,
        start=start,
        end=end,
        steps=steps,
        timezone=_optional_text(payload.get("timezone")),
        origin=_optional_text(payload.get("origin")),
        profile_id=_optional_text(payload.get("profile_id")),
    )
