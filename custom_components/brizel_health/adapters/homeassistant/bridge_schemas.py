"""Schemas and constants for the Brizel Health app bridge."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

BRIDGE_SERVICE_NAME = "brizel_health_app_bridge"
BRIDGE_VERSION = "1.0"
BRIDGE_SCHEMA_VERSION = "1.0"
BRIDGE_AUTH_MODE = "bearer_token"
BRIDGE_SUPPORTED_MODULES = ("profiles", "steps", "body_measurement", "body_goal")
BRIDGE_AVAILABLE_ENDPOINTS = (
    "ping",
    "capabilities",
    "profiles",
    "sync_status",
    "steps",
    "body_measurements",
    "body_goals",
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
    sent_at: datetime
    record_id: str
    record_type: str
    origin_node_id: str
    source_type: str
    source_detail: str
    created_at: datetime
    updated_at: datetime
    updated_by_node_id: str
    revision: int
    payload_version: int
    deleted_at: datetime | None
    measurement_start: datetime
    measurement_end: datetime
    step_count: int
    timezone: str | None = None
    read_mode: str = "raw"
    data_origin: str | None = None
    profile_id: str | None = None

    @property
    def external_record_id(self) -> str:
        """Return the storage identity for compatibility with existing callers."""
        return self.record_id

    @property
    def device_id(self) -> str:
        """Return the node ID under the legacy device_id name."""
        return self.origin_node_id

    @property
    def source(self) -> str:
        """Return the source detail under the legacy source name."""
        return self.source_detail

    @property
    def start(self) -> datetime:
        """Return measurement_start under the legacy start name."""
        return self.measurement_start

    @property
    def end(self) -> datetime:
        """Return measurement_end under the legacy end name."""
        return self.measurement_end

    @property
    def steps(self) -> int:
        """Return step_count under the legacy steps name."""
        return self.step_count

    @property
    def steps_total(self) -> int:
        """Return step_count under the former aggregate payload name."""
        return self.step_count


@dataclass(frozen=True)
class BodyMeasurementPeerRequest:
    """Validated v1 body-measurement peer request for one weight record."""

    schema_version: str
    message_id: str
    sent_at: datetime
    record_id: str
    record_type: str
    profile_id: str | None
    origin_node_id: str
    source_type: str
    source_detail: str
    created_at: datetime
    updated_at: datetime
    updated_by_node_id: str
    revision: int
    payload_version: int
    deleted_at: datetime | None
    measurement_type: str
    canonical_value: float
    measured_at: datetime
    note: str | None = None


@dataclass(frozen=True)
class BodyGoalPeerRequest:
    """Validated v1 body-goal peer request for one target-weight record."""

    schema_version: str
    message_id: str
    sent_at: datetime
    record_id: str
    record_type: str
    profile_id: str | None
    origin_node_id: str
    source_type: str
    source_detail: str
    created_at: datetime
    updated_at: datetime
    updated_by_node_id: str
    revision: int
    payload_version: int
    deleted_at: datetime | None
    goal_type: str
    target_value: float
    note: str | None = None


def get_capabilities_payload(
    *,
    fit_module_available: bool,
    body_measurement_available: bool = False,
    body_goal_available: bool = False,
) -> dict[str, object]:
    """Return the public v1 capabilities payload."""
    return {
        "bridge_version": BRIDGE_VERSION,
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "supported_modules": list(BRIDGE_SUPPORTED_MODULES),
        "fit_module_available": fit_module_available,
        "body_measurement_available": body_measurement_available,
        "auth_mode": BRIDGE_AUTH_MODE,
        "profiles_available": True,
        "steps_import_available": fit_module_available,
        "body_measurements_available": body_measurement_available,
        "body_goals_available": body_goal_available,
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


def serialize_body_measurement_peer_record(record: object) -> dict[str, object]:
    """Serialize one body-measurement CoreRecord for app bridge peers."""
    return {
        "record_id": str(getattr(record, "record_id")),
        "record_type": str(getattr(record, "record_type")),
        "profile_id": str(getattr(record, "profile_id")),
        "source_type": str(getattr(record, "source_type")),
        "source_detail": str(getattr(record, "source_detail")),
        "origin_node_id": str(getattr(record, "origin_node_id")),
        "created_at": str(getattr(record, "created_at")),
        "updated_at": str(getattr(record, "updated_at")),
        "updated_by_node_id": str(getattr(record, "updated_by_node_id")),
        "revision": int(getattr(record, "revision")),
        "payload_version": int(getattr(record, "payload_version")),
        "deleted_at": getattr(record, "deleted_at"),
        "measurement_type": str(getattr(record, "measurement_type")),
        "canonical_value": float(getattr(record, "canonical_value")),
        "measured_at": str(getattr(record, "measured_at")),
        "note": getattr(record, "note"),
    }


def serialize_body_goal_peer_record(record: object) -> dict[str, object]:
    """Serialize one body-goal CoreRecord for app bridge peers."""
    return {
        "record_id": str(getattr(record, "record_id")),
        "record_type": str(getattr(record, "record_type")),
        "profile_id": str(getattr(record, "profile_id")),
        "source_type": str(getattr(record, "source_type")),
        "source_detail": str(getattr(record, "source_detail")),
        "origin_node_id": str(getattr(record, "origin_node_id")),
        "created_at": str(getattr(record, "created_at")),
        "updated_at": str(getattr(record, "updated_at")),
        "updated_by_node_id": str(getattr(record, "updated_by_node_id")),
        "revision": int(getattr(record, "revision")),
        "payload_version": int(getattr(record, "payload_version")),
        "deleted_at": getattr(record, "deleted_at"),
        "goal_type": str(getattr(record, "goal_type")),
        "target_value": float(getattr(record, "target_value")),
        "note": getattr(record, "note"),
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


def _parse_int_field(
    data: dict[str, Any],
    key: str,
    field_errors: dict[str, str],
    *,
    field_path: str,
    minimum: int | None = None,
) -> int | None:
    value = data.get(key)
    if value is None or value == "":
        field_errors[field_path] = "required"
        return None
    if isinstance(value, bool):
        field_errors[field_path] = "invalid_integer"
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        field_errors[field_path] = "invalid_integer"
        return None
    if isinstance(value, float) and not value.is_integer():
        field_errors[field_path] = "invalid_integer"
        return None
    if minimum is not None and parsed < minimum:
        field_errors[field_path] = f"must_be_greater_than_or_equal_to_{minimum}"
        return None
    return parsed


def _parse_float_field(
    data: dict[str, Any],
    key: str,
    field_errors: dict[str, str],
    *,
    field_path: str,
    minimum_exclusive: float | None = None,
) -> float | None:
    value = data.get(key)
    if value is None or value == "":
        field_errors[field_path] = "required"
        return None
    if isinstance(value, bool):
        field_errors[field_path] = "invalid_number"
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        field_errors[field_path] = "invalid_number"
        return None
    if minimum_exclusive is not None and parsed <= minimum_exclusive:
        field_errors[field_path] = f"must_be_greater_than_{minimum_exclusive:g}"
        return None
    return round(parsed, 4)


def _parse_nullable_datetime_value(
    value: object,
    field_path: str,
    field_errors: dict[str, str],
) -> datetime | None:
    if value is None:
        return None
    if not str(value or "").strip():
        field_errors[field_path] = "invalid_datetime"
        return None
    try:
        return datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        field_errors[field_path] = "invalid_datetime"
        return None


def _is_v1_step_record(data: dict[str, Any], payload: object) -> bool:
    if any(
        key in data
        for key in (
            "record_id",
            "record_type",
            "origin_node_id",
            "payload_version",
            "source_type",
        )
    ):
        return True
    return isinstance(payload, dict) and any(
        key in payload
        for key in ("measurement_start", "step_count", "steps_total", "read_mode")
    )


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
    sent_at = _parse_datetime_field(data, "sent_at", field_errors)

    payload = data.get("payload")
    if not isinstance(payload, dict):
        field_errors["payload"] = "required"
        payload = {}

    if _is_v1_step_record(data, payload):
        record_id = _required_text(data, "record_id", field_errors)
        record_type = _required_text(data, "record_type", field_errors)
        profile_id = _optional_text(data.get("profile_id"))
        origin_node_id = _required_text(data, "origin_node_id", field_errors)
        source_type = _required_text(data, "source_type", field_errors)
        source_detail = _required_text(data, "source_detail", field_errors)
        created_at = _parse_datetime_field(data, "created_at", field_errors)
        updated_at = _parse_datetime_field(data, "updated_at", field_errors)
        updated_by_node_id = _required_text(
            data,
            "updated_by_node_id",
            field_errors,
        )
        revision = _parse_int_field(
            data,
            "revision",
            field_errors,
            field_path="revision",
            minimum=1,
        )
        payload_version = _parse_int_field(
            data,
            "payload_version",
            field_errors,
            field_path="payload_version",
            minimum=1,
        )
        if "deleted_at" not in data:
            field_errors["deleted_at"] = "required"
            deleted_at = None
        else:
            deleted_at = _parse_nullable_datetime_value(
                data.get("deleted_at"),
                "deleted_at",
                field_errors,
            )

        measurement_start = _parse_datetime_field(
            payload,
            "measurement_start",
            field_errors,
        )
        if "measurement_start" in field_errors:
            field_errors["payload.measurement_start"] = field_errors.pop(
                "measurement_start"
            )
        measurement_end = _parse_datetime_field(
            payload,
            "measurement_end",
            field_errors,
        )
        if "measurement_end" in field_errors:
            field_errors["payload.measurement_end"] = field_errors.pop(
                "measurement_end"
            )
        step_count_key = "step_count" if "step_count" in payload else "steps_total"
        step_count = _parse_int_field(
            payload,
            step_count_key,
            field_errors,
            field_path=f"payload.{step_count_key}",
            minimum=0,
        )
        read_mode = _required_text(payload, "read_mode", field_errors)
        if "read_mode" in field_errors:
            field_errors["payload.read_mode"] = field_errors.pop("read_mode")
        data_origin = _optional_text(payload.get("data_origin"))
        if read_mode == "raw" and data_origin is None:
            field_errors["payload.data_origin"] = "required"
    else:
        device_id = _required_text(data, "device_id", field_errors)
        source = _required_text(data, "source", field_errors)
        external_record_id = _required_text(
            payload,
            "external_record_id",
            field_errors,
        )
        if "external_record_id" in field_errors:
            field_errors["payload.external_record_id"] = field_errors.pop(
                "external_record_id"
            )
        measurement_start = _parse_datetime_field(payload, "start", field_errors)
        if "start" in field_errors:
            field_errors["payload.start"] = field_errors.pop("start")
        measurement_end = _parse_datetime_field(payload, "end", field_errors)
        if "end" in field_errors:
            field_errors["payload.end"] = field_errors.pop("end")
        step_count = _parse_int_field(
            payload,
            "steps",
            field_errors,
            field_path="payload.steps",
            minimum=0,
        )
        record_id = external_record_id
        record_type = "steps"
        profile_id = _optional_text(payload.get("profile_id"))
        origin_node_id = device_id
        source_type = "app_bridge"
        source_detail = source
        created_at = sent_at
        updated_at = sent_at
        updated_by_node_id = origin_node_id
        revision = 1
        payload_version = 1
        deleted_at = None
        read_mode = _optional_text(payload.get("origin")) or "legacy"
        data_origin = _optional_text(payload.get("data_origin"))

    if schema_version and schema_version != BRIDGE_SCHEMA_VERSION:
        raise BridgeValidationError(
            error_code=ERROR_UNSUPPORTED_SCHEMA_VERSION,
            message=f"Unsupported schema_version '{schema_version}'.",
            field_errors={"schema_version": "unsupported"},
        )

    if record_type and record_type != "steps":
        field_errors["record_type"] = "unsupported"

    if (
        measurement_start is not None
        and measurement_end is not None
        and measurement_end <= measurement_start
    ):
        raise BridgeValidationError(
            error_code=ERROR_INVALID_TIME_RANGE,
            message="The step entry end time must be after start time.",
            field_errors={"payload.measurement_end": "must_be_after_start"},
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
        sent_at=sent_at,
        record_id=record_id,
        record_type=record_type,
        profile_id=profile_id,
        origin_node_id=origin_node_id,
        source_type=source_type,
        source_detail=source_detail,
        created_at=created_at,
        updated_at=updated_at,
        updated_by_node_id=updated_by_node_id,
        revision=revision,
        payload_version=payload_version,
        deleted_at=deleted_at,
        measurement_start=measurement_start,
        measurement_end=measurement_end,
        step_count=step_count,
        timezone=_optional_text(payload.get("timezone")),
        read_mode=read_mode,
        data_origin=data_origin,
    )


def parse_body_measurement_peer_request(data: Any) -> BodyMeasurementPeerRequest:
    """Validate and normalize one v1 body-measurement peer request."""
    if not isinstance(data, dict):
        raise BridgeValidationError(
            error_code=ERROR_INVALID_PAYLOAD,
            message="Request body must be a JSON object.",
            field_errors={"body": "invalid_object"},
        )

    field_errors: dict[str, str] = {}
    schema_version = _required_text(data, "schema_version", field_errors)
    message_id = _required_text(data, "message_id", field_errors)
    sent_at = _parse_datetime_field(data, "sent_at", field_errors)
    record_id = _required_text(data, "record_id", field_errors)
    record_type = _required_text(data, "record_type", field_errors)
    profile_id = _optional_text(data.get("profile_id"))
    origin_node_id = _required_text(data, "origin_node_id", field_errors)
    source_type = _required_text(data, "source_type", field_errors)
    source_detail = _required_text(data, "source_detail", field_errors)
    created_at = _parse_datetime_field(data, "created_at", field_errors)
    updated_at = _parse_datetime_field(data, "updated_at", field_errors)
    updated_by_node_id = _required_text(
        data,
        "updated_by_node_id",
        field_errors,
    )
    revision = _parse_int_field(
        data,
        "revision",
        field_errors,
        field_path="revision",
        minimum=1,
    )
    payload_version = _parse_int_field(
        data,
        "payload_version",
        field_errors,
        field_path="payload_version",
        minimum=1,
    )
    if "deleted_at" not in data:
        field_errors["deleted_at"] = "required"
        deleted_at = None
    else:
        deleted_at = _parse_nullable_datetime_value(
            data.get("deleted_at"),
            "deleted_at",
            field_errors,
        )

    payload = data.get("payload")
    if payload is None:
        payload = data
    if not isinstance(payload, dict):
        field_errors["payload"] = "invalid_object"
        payload = {}

    measurement_type = _required_text(payload, "measurement_type", field_errors)
    if "measurement_type" in field_errors:
        field_errors["payload.measurement_type"] = field_errors.pop(
            "measurement_type"
        )
    canonical_value = _parse_float_field(
        payload,
        "canonical_value",
        field_errors,
        field_path="payload.canonical_value",
        minimum_exclusive=0,
    )
    measured_at = _parse_datetime_field(payload, "measured_at", field_errors)
    if "measured_at" in field_errors:
        field_errors["payload.measured_at"] = field_errors.pop("measured_at")
    note = _optional_text(payload.get("note"))

    if schema_version and schema_version != BRIDGE_SCHEMA_VERSION:
        raise BridgeValidationError(
            error_code=ERROR_UNSUPPORTED_SCHEMA_VERSION,
            message=f"Unsupported schema_version '{schema_version}'.",
            field_errors={"schema_version": "unsupported"},
        )

    if record_type and record_type != "body_measurement":
        field_errors["record_type"] = "unsupported"
    if measurement_type and measurement_type != "weight":
        field_errors["payload.measurement_type"] = "unsupported"

    if field_errors:
        raise BridgeValidationError(
            error_code=ERROR_INVALID_PAYLOAD,
            message="The body measurement peer payload is invalid.",
            field_errors=field_errors,
        )

    return BodyMeasurementPeerRequest(
        schema_version=schema_version,
        message_id=message_id,
        sent_at=sent_at,
        record_id=record_id,
        record_type=record_type,
        profile_id=profile_id,
        origin_node_id=origin_node_id,
        source_type=source_type,
        source_detail=source_detail,
        created_at=created_at,
        updated_at=updated_at,
        updated_by_node_id=updated_by_node_id,
        revision=revision,
        payload_version=payload_version,
        deleted_at=deleted_at,
        measurement_type=measurement_type,
        canonical_value=canonical_value,
        measured_at=measured_at,
        note=note,
    )


def parse_body_goal_peer_request(data: Any) -> BodyGoalPeerRequest:
    """Validate and normalize one v1 body-goal peer request."""
    if not isinstance(data, dict):
        raise BridgeValidationError(
            error_code=ERROR_INVALID_PAYLOAD,
            message="Request body must be a JSON object.",
            field_errors={"body": "invalid_object"},
        )

    field_errors: dict[str, str] = {}
    schema_version = _required_text(data, "schema_version", field_errors)
    message_id = _required_text(data, "message_id", field_errors)
    sent_at = _parse_datetime_field(data, "sent_at", field_errors)
    record_id = _required_text(data, "record_id", field_errors)
    record_type = _required_text(data, "record_type", field_errors)
    profile_id = _optional_text(data.get("profile_id"))
    origin_node_id = _required_text(data, "origin_node_id", field_errors)
    source_type = _required_text(data, "source_type", field_errors)
    source_detail = _required_text(data, "source_detail", field_errors)
    created_at = _parse_datetime_field(data, "created_at", field_errors)
    updated_at = _parse_datetime_field(data, "updated_at", field_errors)
    updated_by_node_id = _required_text(
        data,
        "updated_by_node_id",
        field_errors,
    )
    revision = _parse_int_field(
        data,
        "revision",
        field_errors,
        field_path="revision",
        minimum=1,
    )
    payload_version = _parse_int_field(
        data,
        "payload_version",
        field_errors,
        field_path="payload_version",
        minimum=1,
    )
    if "deleted_at" not in data:
        field_errors["deleted_at"] = "required"
        deleted_at = None
    else:
        deleted_at = _parse_nullable_datetime_value(
            data.get("deleted_at"),
            "deleted_at",
            field_errors,
        )

    payload = data.get("payload")
    if payload is None:
        payload = data
    if not isinstance(payload, dict):
        field_errors["payload"] = "invalid_object"
        payload = {}

    goal_type = _required_text(payload, "goal_type", field_errors)
    if "goal_type" in field_errors:
        field_errors["payload.goal_type"] = field_errors.pop("goal_type")
    target_value = _parse_float_field(
        payload,
        "target_value",
        field_errors,
        field_path="payload.target_value",
        minimum_exclusive=0,
    )
    note = _optional_text(payload.get("note"))

    if schema_version and schema_version != BRIDGE_SCHEMA_VERSION:
        raise BridgeValidationError(
            error_code=ERROR_UNSUPPORTED_SCHEMA_VERSION,
            message=f"Unsupported schema_version '{schema_version}'.",
            field_errors={"schema_version": "unsupported"},
        )

    if record_type and record_type != "body_goal":
        field_errors["record_type"] = "unsupported"
    if goal_type and goal_type != "target_weight":
        field_errors["payload.goal_type"] = "unsupported"

    if field_errors:
        raise BridgeValidationError(
            error_code=ERROR_INVALID_PAYLOAD,
            message="The body goal peer payload is invalid.",
            field_errors=field_errors,
        )

    return BodyGoalPeerRequest(
        schema_version=schema_version,
        message_id=message_id,
        sent_at=sent_at,
        record_id=record_id,
        record_type=record_type,
        profile_id=profile_id,
        origin_node_id=origin_node_id,
        source_type=source_type,
        source_detail=source_detail,
        created_at=created_at,
        updated_at=updated_at,
        updated_by_node_id=updated_by_node_id,
        revision=revision,
        payload_version=payload_version,
        deleted_at=deleted_at,
        goal_type=goal_type,
        target_value=target_value,
        note=note,
    )
