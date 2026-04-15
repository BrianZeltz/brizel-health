"""Profile-scoped body goals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ..errors import BrizelBodyGoalValidationError
from .body_profile import validate_profile_id, validate_weight_kg


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


@dataclass(slots=True)
class BodyGoal:
    """Profile-scoped body goal for weight progress."""

    profile_id: str
    target_weight_kg: float
    created_at: str
    updated_at: str

    @classmethod
    def create(
        cls,
        *,
        profile_id: str,
        target_weight_kg: float | int,
    ) -> "BodyGoal":
        now = datetime.now(UTC).isoformat()
        return cls(
            profile_id=validate_profile_id(profile_id),
            target_weight_kg=validate_weight_kg(target_weight_kg),
            created_at=now,
            updated_at=now,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BodyGoal":
        return cls(
            profile_id=validate_profile_id(data.get("profile_id", "")),
            target_weight_kg=validate_weight_kg(data.get("target_weight_kg")),
            created_at=_normalize_required_timestamp(
                str(data.get("created_at", "")),
                "created_at",
            ),
            updated_at=_normalize_required_timestamp(
                str(data.get("updated_at", "")),
                "updated_at",
            ),
        )

    def update(self, *, target_weight_kg: float | int) -> None:
        self.target_weight_kg = validate_weight_kg(target_weight_kg)
        self.updated_at = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "target_weight_kg": self.target_weight_kg,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
