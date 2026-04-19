"""Profile-scoped body goal CoreRecords."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ..errors import BrizelBodyGoalValidationError, BrizelBodyProfileValidationError
from .body_profile import validate_profile_id, validate_weight_kg

BODY_GOAL_RECORD_TYPE = "body_goal"
BODY_GOAL_TARGET_WEIGHT = "target_weight"
BODY_GOAL_PAYLOAD_VERSION = 1
BODY_GOAL_DEFAULT_NODE_ID = "home_assistant"
BODY_GOAL_SOURCE_TYPE_MANUAL = "manual"
BODY_GOAL_SOURCE_DETAIL_HOME_ASSISTANT = "home_assistant"


def _normalize_required_timestamp(value: str, field_name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise BrizelBodyGoalValidationError(f"{field_name} is required.")

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as err:
        raise BrizelBodyGoalValidationError(
            f"{field_name} must be a valid ISO datetime string."
        ) from err

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC).isoformat()


def _normalize_optional_timestamp(value: object | None, field_name: str) -> str | None:
    if value is None or not str(value).strip():
        return None
    return _normalize_required_timestamp(str(value), field_name)


def _normalize_required_text(value: object, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise BrizelBodyGoalValidationError(f"{field_name} is required.")
    return normalized


def _normalize_optional_text(value: object | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _normalize_positive_int(value: object, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as err:
        raise BrizelBodyGoalValidationError(
            f"{field_name} must be an integer."
        ) from err
    if parsed < 1:
        raise BrizelBodyGoalValidationError(f"{field_name} must be positive.")
    return parsed


def _normalize_goal_type(value: object | None) -> str:
    normalized = _normalize_required_text(
        value or BODY_GOAL_TARGET_WEIGHT,
        "goal_type",
    ).lower()
    if normalized != BODY_GOAL_TARGET_WEIGHT:
        raise BrizelBodyGoalValidationError(
            f"goal_type must be '{BODY_GOAL_TARGET_WEIGHT}'."
        )
    return normalized


def _normalize_record_type(value: object | None) -> str:
    normalized = _normalize_required_text(
        value or BODY_GOAL_RECORD_TYPE,
        "record_type",
    )
    if normalized != BODY_GOAL_RECORD_TYPE:
        raise BrizelBodyGoalValidationError(
            f"record_type must be '{BODY_GOAL_RECORD_TYPE}'."
        )
    return normalized


def build_body_goal_record_id(*, profile_id: str, goal_type: str) -> str:
    """Build the stable CoreRecord ID for one profile-scoped goal state."""
    normalized_profile_id = validate_profile_id(profile_id)
    normalized_goal_type = _normalize_goal_type(goal_type)
    return f"{BODY_GOAL_RECORD_TYPE}:{normalized_profile_id}:{normalized_goal_type}"


def _validate_target_value(value: object) -> float:
    try:
        normalized = validate_weight_kg(value)  # v1 only supports target weight.
    except (TypeError, ValueError, BrizelBodyProfileValidationError) as err:
        raise BrizelBodyGoalValidationError(str(err)) from err
    if normalized is None:
        raise BrizelBodyGoalValidationError("target_value is required.")
    return float(normalized)


@dataclass(slots=True)
class BodyGoal:
    """Current body-goal CoreRecord for one profile and goal type."""

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
    goal_type: str
    target_value: float
    note: str | None

    @property
    def target_weight_kg(self) -> float:
        """Compatibility view for existing HA services and progress queries."""
        return self.target_value

    @classmethod
    def create(
        cls,
        *,
        profile_id: str,
        target_weight_kg: float | int | None = None,
        target_value: float | int | None = None,
        note: str | None = None,
        source_type: str = BODY_GOAL_SOURCE_TYPE_MANUAL,
        source_detail: str = BODY_GOAL_SOURCE_DETAIL_HOME_ASSISTANT,
        origin_node_id: str = BODY_GOAL_DEFAULT_NODE_ID,
        updated_by_node_id: str | None = None,
    ) -> "BodyGoal":
        """Create one active target-weight goal CoreRecord."""
        now = datetime.now(UTC).isoformat()
        normalized_profile_id = validate_profile_id(profile_id)
        goal_type = BODY_GOAL_TARGET_WEIGHT
        normalized_target = _validate_target_value(
            target_value if target_value is not None else target_weight_kg
        )
        normalized_origin_node_id = _normalize_required_text(
            origin_node_id,
            "origin_node_id",
        )
        return cls(
            record_id=build_body_goal_record_id(
                profile_id=normalized_profile_id,
                goal_type=goal_type,
            ),
            record_type=BODY_GOAL_RECORD_TYPE,
            profile_id=normalized_profile_id,
            source_type=_normalize_required_text(source_type, "source_type").lower(),
            source_detail=_normalize_required_text(
                source_detail,
                "source_detail",
            ).lower(),
            origin_node_id=normalized_origin_node_id,
            created_at=now,
            updated_at=now,
            updated_by_node_id=_normalize_required_text(
                updated_by_node_id or normalized_origin_node_id,
                "updated_by_node_id",
            ),
            revision=1,
            payload_version=BODY_GOAL_PAYLOAD_VERSION,
            deleted_at=None,
            goal_type=goal_type,
            target_value=normalized_target,
            note=_normalize_optional_text(note),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BodyGoal":
        """Load a body-goal CoreRecord, including legacy profile-keyed data."""
        profile_id = validate_profile_id(data.get("profile_id", ""))
        goal_type = _normalize_goal_type(data.get("goal_type"))
        record_id = str(
            data.get("record_id")
            or build_body_goal_record_id(profile_id=profile_id, goal_type=goal_type)
        ).strip()
        if not record_id:
            raise BrizelBodyGoalValidationError("record_id is required.")

        target_value = data.get("target_value")
        if target_value is None:
            target_value = data.get("target_weight_kg")
        created_at = _normalize_required_timestamp(
            str(data.get("created_at", "")),
            "created_at",
        )
        updated_at = _normalize_required_timestamp(
            str(data.get("updated_at", created_at)),
            "updated_at",
        )
        origin_node_id = _normalize_required_text(
            data.get("origin_node_id") or BODY_GOAL_DEFAULT_NODE_ID,
            "origin_node_id",
        )
        return cls(
            record_id=record_id,
            record_type=_normalize_record_type(data.get("record_type")),
            profile_id=profile_id,
            source_type=_normalize_required_text(
                data.get("source_type") or BODY_GOAL_SOURCE_TYPE_MANUAL,
                "source_type",
            ).lower(),
            source_detail=_normalize_required_text(
                data.get("source_detail") or BODY_GOAL_SOURCE_DETAIL_HOME_ASSISTANT,
                "source_detail",
            ).lower(),
            origin_node_id=origin_node_id,
            created_at=created_at,
            updated_at=updated_at,
            updated_by_node_id=_normalize_required_text(
                data.get("updated_by_node_id") or origin_node_id,
                "updated_by_node_id",
            ),
            revision=_normalize_positive_int(data.get("revision", 1), "revision"),
            payload_version=_normalize_positive_int(
                data.get("payload_version", BODY_GOAL_PAYLOAD_VERSION),
                "payload_version",
            ),
            deleted_at=_normalize_optional_timestamp(
                data.get("deleted_at"),
                "deleted_at",
            ),
            goal_type=goal_type,
            target_value=_validate_target_value(target_value),
            note=_normalize_optional_text(data.get("note")),
        )

    def update(
        self,
        *,
        target_weight_kg: float | int | None = None,
        target_value: float | int | None = None,
        note: str | None = None,
        updated_by_node_id: str | None = None,
    ) -> None:
        """Update the current goal state in place."""
        self.target_value = _validate_target_value(
            target_value if target_value is not None else target_weight_kg
        )
        self.note = _normalize_optional_text(note) if note is not None else self.note
        self.deleted_at = None
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
        """Tombstone the current goal state without physically deleting it."""
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
            "goal_type": self.goal_type,
            "target_value": self.target_value,
            "target_weight_kg": self.target_weight_kg,
            "note": self.note,
        }
