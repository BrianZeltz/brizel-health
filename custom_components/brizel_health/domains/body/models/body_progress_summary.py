"""Structured body progress summary results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class BodyProgressSummary:
    """Progress summary for one measurement type."""

    profile_id: str
    measurement_type: str
    latest_canonical_value: float | None
    latest_measured_at: str | None
    previous_canonical_value: float | None
    first_canonical_value: float | None
    change_since_previous: float | None
    change_since_start: float | None
    trend_7d: float | None
    trend_30d: float | None
    goal_canonical_value: float | None
    distance_to_goal: float | None
    history_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "measurement_type": self.measurement_type,
            "latest_canonical_value": self.latest_canonical_value,
            "latest_measured_at": self.latest_measured_at,
            "previous_canonical_value": self.previous_canonical_value,
            "first_canonical_value": self.first_canonical_value,
            "change_since_previous": self.change_since_previous,
            "change_since_start": self.change_since_start,
            "trend_7d": self.trend_7d,
            "trend_30d": self.trend_30d,
            "goal_canonical_value": self.goal_canonical_value,
            "distance_to_goal": self.distance_to_goal,
            "history_count": self.history_count,
        }
