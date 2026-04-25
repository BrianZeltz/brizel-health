"""Schemas and constants for the Brizel Health app bridge."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from ...domains.security.models.key_hierarchy import (
    JoinEnrollmentRequest,
    NodeEnrollmentDescriptor,
    WrappedProfileKeyEnvelope,
)

BRIDGE_SERVICE_NAME = "brizel_health_app_bridge"
BRIDGE_VERSION = "1.0"
BRIDGE_SCHEMA_VERSION = "1.0"
BRIDGE_AUTH_MODE = "bearer_token"
BRIDGE_SUPPORTED_MODULES = (
    "profiles",
    "steps",
    "body_measurement",
    "body_goal",
    "food_log",
)
BRIDGE_AVAILABLE_ENDPOINTS = (
    "ping",
    "capabilities",
    "profiles",
    "profile_context",
    "join_requests",
    "join_authorize",
    "join_complete",
    "join_invalidate",
    "sync_status",
    "sync_pull",
    "steps",
    "body_measurements",
    "body_goals",
    "food_logs",
)
BODY_MEASUREMENT_PEER_TYPES = frozenset(
    {
        "weight",
        "height",
        "waist",
        "abdomen",
        "hip",
        "chest",
        "upper_arm",
        "forearm",
        "thigh",
        "calf",
        "neck",
    }
)
BODY_MEASUREMENT_PEER_TYPE_ALIASES = {
    "weight_kg": "weight",
    "body_weight": "weight",
    "height_cm": "height",
}

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
ERROR_JOIN_REQUEST_NOT_FOUND = "JOIN_REQUEST_NOT_FOUND"
ERROR_JOIN_REQUEST_STATE = "JOIN_REQUEST_STATE"
ERROR_JOIN_REQUEST_EXPIRED = "JOIN_REQUEST_EXPIRED"


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
    """Validated body-measurement peer request for one supported record."""

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


@dataclass(frozen=True)
class FoodLogPeerRequest:
    """Validated v1 food-log peer request for one consumed-food record."""

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
    consumed_at: datetime
    food_id: str
    food_name: str
    food_brand: str | None
    amount_grams: float
    meal_type: str | None
    note: str | None
    kcal: float
    protein: float
    carbs: float
    fat: float


@dataclass(frozen=True)
class ProfileContextSyncRequest:
    """Validated profile-context sync request for one linked profile."""

    schema_version: str
    message_id: str
    sent_at: datetime
    profile_id: str | None
    updated_at: datetime
    updated_by_node_id: str
    display_name: str
    birth_date: str | None
    date_of_birth: str | None
    sex: str | None
    activity_level: str | None


@dataclass(frozen=True)
class SyncPullRequest:
    """Validated pull request carrying per-domain cursors."""

    schema_version: str
    message_id: str
    sent_at: datetime
    profile_id: str | None
    requesting_node_id: str | None
    cursors: dict[str, datetime | None]
    journal_cursors: dict[str, str | None]


@dataclass(frozen=True)
class JoinRequestCreateRequest:
    """Validated join request carrying recipient enrollment material."""

    schema_version: str
    message_id: str
    sent_at: datetime
    request_id: str
    profile_id: str | None
    requested_at: datetime
    expires_at: datetime
    requesting_node_id: str
    recipient: NodeEnrollmentDescriptor


@dataclass(frozen=True)
class JoinRequestAuthorizeRequest:
    """Validated approval request for one pending join request."""

    schema_version: str
    message_id: str
    sent_at: datetime
    request_id: str


@dataclass(frozen=True)
class JoinRequestCompleteRequest:
    """Validated completion request after a node consumed its join approval."""

    schema_version: str
    message_id: str
    sent_at: datetime
    request_id: str
    approval_id: str


@dataclass(frozen=True)
class JoinRequestInvalidateRequest:
    """Validated invalidation request for one join request."""

    schema_version: str
    message_id: str
    sent_at: datetime
    request_id: str
    reason: str | None


def get_capabilities_payload(
    *,
    fit_module_available: bool,
    body_measurement_available: bool = False,
    body_goal_available: bool = False,
    food_log_available: bool = False,
) -> dict[str, object]:
    """Return the public v1 capabilities payload."""
    return {
        "bridge_version": BRIDGE_VERSION,
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "supported_modules": list(BRIDGE_SUPPORTED_MODULES),
        "fit_module_available": fit_module_available,
        "body_measurement_available": body_measurement_available,
        "food_log_available": food_log_available,
        "auth_mode": BRIDGE_AUTH_MODE,
        "profiles_available": True,
        "steps_import_available": fit_module_available,
        "body_measurements_available": body_measurement_available,
        "body_goals_available": body_goal_available,
        "food_logs_available": food_log_available,
        "available_endpoints": list(BRIDGE_AVAILABLE_ENDPOINTS),
    }


def serialize_bridge_profile(
    profile: object,
    *,
    body_profile: object | None = None,
    activity_level: object | None = None,
    height_cm: float | None = None,
    weight_kg: float | None = None,
) -> dict[str, object]:
    """Serialize one aggregated profile context for app bridge clients."""
    birth_date = _optional_profile_text_any(
        body_profile,
        ("birth_date", "date_of_birth"),
    ) if body_profile is not None else None
    age_years = _age_years_from_birth_date(birth_date)
    if age_years is None:
        age_years = (
            _optional_profile_int(body_profile, "age_years")
            if body_profile is not None
            else None
        )

    sex = (
        _optional_profile_text(body_profile, "sex")
        if body_profile is not None
        else None
    )
    fit_activity_level = _optional_text(activity_level)

    return {
        "profile_id": str(getattr(profile, "user_id")),
        "display_name": str(getattr(profile, "display_name")),
        "is_default": False,
        "sex": sex,
        "activity_level": fit_activity_level,
        "height_cm": height_cm,
        "weight_kg": weight_kg,
        "birth_date": birth_date,
        "date_of_birth": birth_date,
        "age_years": age_years,
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


def serialize_join_request(
    request: JoinEnrollmentRequest,
    *,
    approval_envelope: WrappedProfileKeyEnvelope | None = None,
    wrapped_key_material: str | None = None,
    profile_key_algorithm: str | None = None,
) -> dict[str, object]:
    """Serialize one request-bound join state for app bridge clients."""
    approval_payload: dict[str, object] | None = None
    if approval_envelope is not None:
        approval_payload = {
            "approval_id": request.approval_id,
            "approved_at": _serialize_timestamp_value(request.approved_at, nullable=True),
            "approved_by_node_id": request.approved_by_node_id,
            "approved_by_node_key_id": request.approved_by_node_key_id,
            "profile_key_algorithm": profile_key_algorithm,
            "envelope": approval_envelope.to_dict(),
            "wrapped_key_material": wrapped_key_material,
        }

    return {
        "request_id": request.request_id,
        "profile_id": request.profile_id,
        "requesting_node_id": request.requesting_node_id,
        "recipient": request.recipient.to_dict(),
        "requested_at": _serialize_timestamp_value(request.requested_at),
        "expires_at": _serialize_timestamp_value(request.expires_at),
        "status": request.status,
        "approval": approval_payload,
        "completed_at": _serialize_timestamp_value(request.completed_at, nullable=True),
        "invalidated_at": _serialize_timestamp_value(
            request.invalidated_at,
            nullable=True,
        ),
        "invalidation_reason": request.invalidation_reason,
    }


def serialize_step_peer_record(record: object) -> dict[str, object]:
    """Serialize one raw step CoreRecord for app bridge peers."""
    return {
        "record_id": str(getattr(record, "record_id")),
        "record_type": str(getattr(record, "record_type")),
        "profile_id": str(getattr(record, "profile_id")),
        "origin_node_id": str(getattr(record, "origin_node_id")),
        "created_at": serialize_datetime_for_bridge(getattr(record, "created_at")),
        "updated_at": serialize_datetime_for_bridge(getattr(record, "updated_at")),
        "updated_by_node_id": str(getattr(record, "updated_by_node_id")),
        "revision": int(getattr(record, "revision")),
        "payload_version": int(getattr(record, "payload_version")),
        "deleted_at": serialize_datetime_for_bridge(getattr(record, "deleted_at")),
        "source_type": str(getattr(record, "source_type")),
        "source_detail": str(getattr(record, "source_detail")),
        "measurement_start": serialize_datetime_for_bridge(getattr(record, "start")),
        "measurement_end": serialize_datetime_for_bridge(getattr(record, "end")),
        "step_count": int(getattr(record, "steps")),
        "timezone": getattr(record, "timezone"),
        "read_mode": str(getattr(record, "read_mode")),
        "data_origin": str(getattr(record, "data_origin") or "unknown"),
    }


def serialize_body_measurement_peer_record(record: object) -> dict[str, object]:
    """Serialize one body-measurement CoreRecord for app bridge peers."""
    measurement_type = _normalize_body_measurement_peer_type(
        getattr(record, "measurement_type")
    )
    return {
        "record_id": str(getattr(record, "record_id")),
        "record_type": str(getattr(record, "record_type")),
        "profile_id": str(getattr(record, "profile_id")),
        "source_type": str(getattr(record, "source_type")),
        "source_detail": str(getattr(record, "source_detail")),
        "origin_node_id": str(getattr(record, "origin_node_id")),
        "created_at": _serialize_timestamp_value(getattr(record, "created_at")),
        "updated_at": _serialize_timestamp_value(getattr(record, "updated_at")),
        "updated_by_node_id": str(getattr(record, "updated_by_node_id")),
        "revision": int(getattr(record, "revision")),
        "payload_version": int(getattr(record, "payload_version")),
        "deleted_at": _serialize_timestamp_value(
            getattr(record, "deleted_at"),
            nullable=True,
        ),
        "measurement_type": measurement_type,
        "canonical_value": float(getattr(record, "canonical_value")),
        "measured_at": _serialize_timestamp_value(getattr(record, "measured_at")),
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


def serialize_food_log_peer_record(record: object) -> dict[str, object]:
    """Serialize one food_log CoreRecord for app bridge peers."""
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
        "consumed_at": str(getattr(record, "consumed_at")),
        "food_id": str(getattr(record, "food_id")),
        "food_name": str(getattr(record, "food_name")),
        "food_brand": getattr(record, "food_brand"),
        "amount_grams": float(getattr(record, "amount_grams")),
        "grams": float(getattr(record, "grams")),
        "meal_type": getattr(record, "meal_type"),
        "note": getattr(record, "note"),
        "kcal": float(getattr(record, "kcal")),
        "protein": float(getattr(record, "protein")),
        "carbs": float(getattr(record, "carbs")),
        "fat": float(getattr(record, "fat")),
    }


def _required_text(
    data: dict[str, Any],
    key: str,
    field_errors: dict[str, str],
    *,
    field_path: str | None = None,
) -> str:
    value = data.get(key)
    normalized = str(value or "").strip()
    if not normalized:
        field_errors[field_path or key] = "required"
    return normalized


def _optional_text(value: object) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _optional_profile_text(profile: object, key: str) -> str | None:
    return _optional_text(getattr(profile, key, None))


def _optional_profile_text_any(profile: object, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = _optional_profile_text(profile, key)
        if value is not None:
            return value
    return None


def _optional_profile_float(profile: object, key: str) -> float | None:
    if profile is None:
        return None
    value = getattr(profile, key, None)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_profile_int(profile: object, key: str) -> int | None:
    if profile is None:
        return None
    value = getattr(profile, key, None)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_body_measurement_peer_type(value: object) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return normalized
    return BODY_MEASUREMENT_PEER_TYPE_ALIASES.get(normalized, normalized)


def _age_years_from_birth_date(birth_date: str | None) -> int | None:
    if birth_date is None:
        return None
    try:
        normalized = birth_date.strip()
        if "T" in normalized or " " in normalized:
            parsed_date = datetime.fromisoformat(
                normalized.replace("Z", "+00:00")
            ).date()
        else:
            parsed_date = date.fromisoformat(normalized)
    except ValueError:
        return None
    today = datetime.now().date()
    years = today.year - parsed_date.year - (
        (today.month, today.day) < (parsed_date.month, parsed_date.day)
    )
    return years if years >= 0 else None


def _serialize_timestamp_value(value: object, *, nullable: bool = False) -> str | None:
    if value is None:
        return None if nullable else ""
    if isinstance(value, datetime):
        return serialize_datetime_for_bridge(value)
    parsed = _parse_nullable_datetime_value(value, "_timestamp", {})
    if parsed is not None:
        return serialize_datetime_for_bridge(parsed)
    normalized = str(value).strip()
    if not normalized and nullable:
        return None
    return normalized


def _parse_datetime_field(
    data: dict[str, Any],
    key: str,
    field_errors: dict[str, str],
    *,
    field_path: str | None = None,
) -> datetime | None:
    value = data.get(key)
    if not str(value or "").strip():
        field_errors[field_path or key] = "required"
        return None
    try:
        return datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        field_errors[field_path or key] = "invalid_datetime"
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


def _parse_non_negative_float_field(
    data: dict[str, Any],
    key: str,
    field_errors: dict[str, str],
    *,
    field_path: str,
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
    if parsed < 0:
        field_errors[field_path] = "must_be_greater_than_or_equal_to_0"
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
    if measurement_type and measurement_type not in BODY_MEASUREMENT_PEER_TYPES:
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


def parse_food_log_peer_request(data: Any) -> FoodLogPeerRequest:
    """Validate and normalize one v1 food_log peer request."""
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

    consumed_at = _parse_datetime_field(payload, "consumed_at", field_errors)
    if "consumed_at" in field_errors:
        field_errors["payload.consumed_at"] = field_errors.pop("consumed_at")
    food_id = _required_text(payload, "food_id", field_errors)
    if "food_id" in field_errors:
        field_errors["payload.food_id"] = field_errors.pop("food_id")
    food_name = _required_text(payload, "food_name", field_errors)
    if "food_name" in field_errors:
        field_errors["payload.food_name"] = field_errors.pop("food_name")
    food_brand = _optional_text(payload.get("food_brand"))
    amount_grams = _parse_float_field(
        payload,
        "amount_grams",
        field_errors,
        field_path="payload.amount_grams",
        minimum_exclusive=0,
    )
    meal_type = _optional_text(payload.get("meal_type"))
    note = _optional_text(payload.get("note"))
    kcal = _parse_non_negative_float_field(
        payload,
        "kcal",
        field_errors,
        field_path="payload.kcal",
    )
    protein = _parse_non_negative_float_field(
        payload,
        "protein",
        field_errors,
        field_path="payload.protein",
    )
    carbs = _parse_non_negative_float_field(
        payload,
        "carbs",
        field_errors,
        field_path="payload.carbs",
    )
    fat = _parse_non_negative_float_field(
        payload,
        "fat",
        field_errors,
        field_path="payload.fat",
    )

    if schema_version and schema_version != BRIDGE_SCHEMA_VERSION:
        raise BridgeValidationError(
            error_code=ERROR_UNSUPPORTED_SCHEMA_VERSION,
            message=f"Unsupported schema_version '{schema_version}'.",
            field_errors={"schema_version": "unsupported"},
        )

    if record_type and record_type != "food_log":
        field_errors["record_type"] = "unsupported"

    if field_errors:
        raise BridgeValidationError(
            error_code=ERROR_INVALID_PAYLOAD,
            message="The food_log peer payload is invalid.",
            field_errors=field_errors,
        )

    return FoodLogPeerRequest(
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
        consumed_at=consumed_at,
        food_id=food_id,
        food_name=food_name,
        food_brand=food_brand,
        amount_grams=amount_grams,
        meal_type=meal_type,
        note=note,
        kcal=kcal,
        protein=protein,
        carbs=carbs,
        fat=fat,
    )


def parse_profile_context_sync_request(data: Any) -> ProfileContextSyncRequest:
    """Validate and normalize one v1 profile-context sync request."""
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
    profile_id = _optional_text(data.get("profile_id"))
    updated_at = _parse_datetime_field(data, "updated_at", field_errors)
    updated_by_node_id = _required_text(data, "updated_by_node_id", field_errors)

    payload = data.get("payload")
    if not isinstance(payload, dict):
        field_errors["payload"] = "required"
        payload = {}

    display_name = _required_text(payload, "display_name", field_errors)
    if "display_name" in field_errors:
        field_errors["payload.display_name"] = field_errors.pop("display_name")

    birth_date = _optional_text(payload.get("birth_date"))
    date_of_birth = _optional_text(payload.get("date_of_birth"))
    sex = _optional_text(payload.get("sex"))
    activity_level = _optional_text(payload.get("activity_level"))

    if schema_version and schema_version != BRIDGE_SCHEMA_VERSION:
        raise BridgeValidationError(
            error_code=ERROR_UNSUPPORTED_SCHEMA_VERSION,
            message=f"Unsupported schema_version '{schema_version}'.",
            field_errors={"schema_version": "unsupported"},
        )

    if field_errors:
        raise BridgeValidationError(
            error_code=ERROR_INVALID_PAYLOAD,
            message="The profile context payload is invalid.",
            field_errors=field_errors,
        )

    return ProfileContextSyncRequest(
        schema_version=schema_version,
        message_id=message_id,
        sent_at=sent_at,
        profile_id=profile_id,
        updated_at=updated_at,
        updated_by_node_id=updated_by_node_id,
        display_name=display_name,
        birth_date=birth_date,
        date_of_birth=date_of_birth,
        sex=sex,
        activity_level=activity_level,
    )


def parse_sync_pull_request(data: Any) -> SyncPullRequest:
    """Validate and normalize one v1 sync pull request."""
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
    profile_id = _optional_text(data.get("profile_id"))
    requesting_node_id = _optional_text(
        data.get("requesting_node_id") or data.get("node_id")
    )

    raw_cursors = data.get("cursors")
    cursors: dict[str, datetime | None] = {}
    journal_cursors: dict[str, str | None] = {}
    if raw_cursors is not None and not isinstance(raw_cursors, dict):
        field_errors["cursors"] = "invalid_object"
        raw_cursors = None

    for domain in ("steps", "body_measurements", "body_goals", "food_logs"):
        domain_cursor: datetime | None = None
        if isinstance(raw_cursors, dict):
            cursor_payload = raw_cursors.get(domain)
            if cursor_payload is not None and not isinstance(cursor_payload, dict):
                field_errors[f"cursors.{domain}"] = "invalid_object"
            elif isinstance(cursor_payload, dict):
                domain_cursor = _parse_nullable_datetime_value(
                    cursor_payload.get("updated_after"),
                    f"cursors.{domain}.updated_after",
                    field_errors,
                )
                journal_cursors[domain] = _optional_text(
                    cursor_payload.get("cursor")
                    or cursor_payload.get("journal_cursor")
                    or cursor_payload.get("sequence")
                )
        cursors[domain] = domain_cursor
        journal_cursors.setdefault(domain, None)

    if schema_version and schema_version != BRIDGE_SCHEMA_VERSION:
        raise BridgeValidationError(
            error_code=ERROR_UNSUPPORTED_SCHEMA_VERSION,
            message=f"Unsupported schema_version '{schema_version}'.",
            field_errors={"schema_version": "unsupported"},
        )

    if field_errors:
        raise BridgeValidationError(
            error_code=ERROR_INVALID_PAYLOAD,
            message="The sync pull payload is invalid.",
            field_errors=field_errors,
        )

    return SyncPullRequest(
        schema_version=schema_version,
        message_id=message_id,
        sent_at=sent_at,
        profile_id=profile_id,
        requesting_node_id=requesting_node_id,
        cursors=cursors,
        journal_cursors=journal_cursors,
    )


def parse_join_request_create_request(data: Any) -> JoinRequestCreateRequest:
    """Validate and normalize one join/enrollment request."""
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
    request_id = _required_text(data, "request_id", field_errors)
    profile_id = _optional_text(data.get("profile_id"))
    requested_at = _parse_datetime_field(data, "requested_at", field_errors)
    expires_at = _parse_datetime_field(data, "expires_at", field_errors)
    requesting_node_id = _required_text(data, "requesting_node_id", field_errors)

    raw_recipient = (
        data.get("recipient")
        or data.get("recipient_descriptor")
        or data.get("node_enrollment_descriptor")
    )
    if not isinstance(raw_recipient, dict):
        field_errors["recipient"] = "required"
        raw_recipient = {}

    recipient = _parse_node_enrollment_descriptor(
        raw_recipient,
        field_prefix="recipient",
        field_errors=field_errors,
    )
    if requesting_node_id and requesting_node_id != recipient.node_id:
        field_errors["requesting_node_id"] = "must_match_recipient_node_id"

    if requested_at is not None and expires_at is not None and expires_at <= requested_at:
        field_errors["expires_at"] = "must_be_after_requested_at"

    if schema_version and schema_version != BRIDGE_SCHEMA_VERSION:
        raise BridgeValidationError(
            error_code=ERROR_UNSUPPORTED_SCHEMA_VERSION,
            message=f"Unsupported schema_version '{schema_version}'.",
            field_errors={"schema_version": "unsupported"},
        )

    if field_errors:
        raise BridgeValidationError(
            error_code=ERROR_INVALID_PAYLOAD,
            message="The join request payload is invalid.",
            field_errors=field_errors,
        )

    return JoinRequestCreateRequest(
        schema_version=schema_version,
        message_id=message_id,
        sent_at=sent_at,
        request_id=request_id,
        profile_id=profile_id,
        requested_at=requested_at,
        expires_at=expires_at,
        requesting_node_id=requesting_node_id,
        recipient=recipient,
    )


def parse_join_request_authorize_request(data: Any) -> JoinRequestAuthorizeRequest:
    """Validate and normalize one join approval request."""
    return JoinRequestAuthorizeRequest(
        schema_version=_parse_simple_bridge_action(data, "schema_version"),
        message_id=_parse_simple_bridge_action(data, "message_id"),
        sent_at=_parse_simple_bridge_action_datetime(data, "sent_at"),
        request_id=_parse_simple_bridge_action(data, "request_id"),
    )


def parse_join_request_complete_request(data: Any) -> JoinRequestCompleteRequest:
    """Validate and normalize one join completion request."""
    return JoinRequestCompleteRequest(
        schema_version=_parse_simple_bridge_action(data, "schema_version"),
        message_id=_parse_simple_bridge_action(data, "message_id"),
        sent_at=_parse_simple_bridge_action_datetime(data, "sent_at"),
        request_id=_parse_simple_bridge_action(data, "request_id"),
        approval_id=_parse_simple_bridge_action(data, "approval_id"),
    )


def parse_join_request_invalidate_request(data: Any) -> JoinRequestInvalidateRequest:
    """Validate and normalize one join invalidation request."""
    if not isinstance(data, dict):
        raise BridgeValidationError(
            error_code=ERROR_INVALID_PAYLOAD,
            message="Request body must be a JSON object.",
            field_errors={"body": "invalid_object"},
        )
    schema_version = _parse_simple_bridge_action(data, "schema_version")
    message_id = _parse_simple_bridge_action(data, "message_id")
    sent_at = _parse_simple_bridge_action_datetime(data, "sent_at")
    request_id = _parse_simple_bridge_action(data, "request_id")
    reason = _optional_text(data.get("reason"))
    return JoinRequestInvalidateRequest(
        schema_version=schema_version,
        message_id=message_id,
        sent_at=sent_at,
        request_id=request_id,
        reason=reason,
    )


def _parse_node_enrollment_descriptor(
    data: dict[str, Any],
    *,
    field_prefix: str,
    field_errors: dict[str, str],
) -> NodeEnrollmentDescriptor:
    created_at = _parse_datetime_field(
        data,
        "created_at",
        field_errors,
        field_path=f"{field_prefix}.created_at",
    )
    updated_at = _parse_datetime_field(
        data,
        "updated_at",
        field_errors,
        field_path=f"{field_prefix}.updated_at",
    )
    return NodeEnrollmentDescriptor(
        node_id=_required_text(
            data,
            "node_id",
            field_errors,
            field_path=f"{field_prefix}.node_id",
        ),
        recipient_key_id=_required_text(
            data,
            "recipient_key_id",
            field_errors,
            field_path=f"{field_prefix}.recipient_key_id",
        ),
        key_version=_parse_int_field(
            data,
            "key_version",
            field_errors,
            minimum=1,
            field_path=f"{field_prefix}.key_version",
        ),
        algorithm=_required_text(
            data,
            "algorithm",
            field_errors,
            field_path=f"{field_prefix}.algorithm",
        ),
        public_key_b64=_required_text(
            data,
            "public_key_b64",
            field_errors,
            field_path=f"{field_prefix}.public_key_b64",
        ),
        created_at=created_at,
        updated_at=updated_at,
    )


def _parse_simple_bridge_action(data: Any, field_name: str) -> str:
    if not isinstance(data, dict):
        raise BridgeValidationError(
            error_code=ERROR_INVALID_PAYLOAD,
            message="Request body must be a JSON object.",
            field_errors={"body": "invalid_object"},
        )
    field_errors: dict[str, str] = {}
    schema_version = _required_text(data, "schema_version", field_errors)
    if schema_version and schema_version != BRIDGE_SCHEMA_VERSION:
        raise BridgeValidationError(
            error_code=ERROR_UNSUPPORTED_SCHEMA_VERSION,
            message=f"Unsupported schema_version '{schema_version}'.",
            field_errors={"schema_version": "unsupported"},
        )
    value = _required_text(data, field_name, field_errors)
    if field_errors:
        raise BridgeValidationError(
            error_code=ERROR_INVALID_PAYLOAD,
            message="The join action payload is invalid.",
            field_errors=field_errors,
        )
    return value


def _parse_simple_bridge_action_datetime(data: Any, field_name: str) -> datetime:
    if not isinstance(data, dict):
        raise BridgeValidationError(
            error_code=ERROR_INVALID_PAYLOAD,
            message="Request body must be a JSON object.",
            field_errors={"body": "invalid_object"},
        )
    field_errors: dict[str, str] = {}
    schema_version = _required_text(data, "schema_version", field_errors)
    if schema_version and schema_version != BRIDGE_SCHEMA_VERSION:
        raise BridgeValidationError(
            error_code=ERROR_UNSUPPORTED_SCHEMA_VERSION,
            message=f"Unsupported schema_version '{schema_version}'.",
            field_errors={"schema_version": "unsupported"},
        )
    value = _parse_datetime_field(data, field_name, field_errors)
    if field_errors:
        raise BridgeValidationError(
            error_code=ERROR_INVALID_PAYLOAD,
            message="The join action payload is invalid.",
            field_errors=field_errors,
        )
    return value
