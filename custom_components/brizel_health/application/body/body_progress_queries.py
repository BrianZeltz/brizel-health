"""Progress and trend queries for the Body module."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ...core.interfaces.user_repository import UserRepository
from ...domains.body.interfaces.body_goal_repository import BodyGoalRepository
from ...domains.body.interfaces.body_measurement_repository import (
    BodyMeasurementRepository,
)
from ...domains.body.interfaces.body_profile_repository import BodyProfileRepository
from ...domains.body.models.body_measurement_entry import BodyMeasurementEntry
from ...domains.body.models.body_progress_summary import BodyProgressSummary
from ..users.user_use_cases import get_user
from .body_measurement_queries import get_measurement_history


def _parse_iso_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _round_delta(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def _window_change(
    entries_desc: list[BodyMeasurementEntry],
    *,
    latest_entry: BodyMeasurementEntry,
    days: int,
) -> float | None:
    latest_time = _parse_iso_timestamp(latest_entry.measured_at)
    window_start = latest_time - timedelta(days=days)

    candidates = [
        entry
        for entry in entries_desc
        if _parse_iso_timestamp(entry.measured_at) >= window_start
    ]
    if len(candidates) < 2:
        return None

    earliest_in_window = min(
        candidates,
        key=lambda entry: _parse_iso_timestamp(entry.measured_at),
    )
    return _round_delta(
        latest_entry.canonical_value - earliest_in_window.canonical_value
    )


def get_body_progress_summary(
    measurement_repository: BodyMeasurementRepository,
    goal_repository: BodyGoalRepository,
    user_repository: UserRepository,
    *,
    profile_id: str,
    measurement_type: str = "weight",
    body_profile_repository: BodyProfileRepository | None = None,
) -> BodyProgressSummary:
    """Return a closed-beta-ready progress summary for one measurement type."""
    user = get_user(user_repository, profile_id)
    entries = get_measurement_history(
        measurement_repository,
        user_repository,
        profile_id=user.user_id,
        measurement_type=measurement_type,
    )
    goal = goal_repository.get_by_profile_id(user.user_id)
    latest_entry = entries[0] if entries else None
    previous_entry = entries[1] if len(entries) > 1 else None
    first_entry = entries[-1] if entries else None

    latest_value = latest_entry.canonical_value if latest_entry is not None else None
    previous_value = (
        previous_entry.canonical_value if previous_entry is not None else None
    )
    first_value = first_entry.canonical_value if first_entry is not None else None
    goal_value = (
        goal.target_weight_kg
        if goal is not None and measurement_type == "weight"
        else None
    )
    return BodyProgressSummary(
        profile_id=user.user_id,
        measurement_type=measurement_type,
        latest_canonical_value=latest_value,
        latest_measured_at=latest_entry.measured_at if latest_entry is not None else None,
        previous_canonical_value=previous_value,
        first_canonical_value=first_value,
        change_since_previous=_round_delta(
            latest_value - previous_value
            if latest_value is not None and previous_value is not None
            else None
        ),
        change_since_start=_round_delta(
            latest_value - first_value
            if latest_value is not None and first_value is not None
            else None
        ),
        trend_7d=(
            _window_change(entries, latest_entry=latest_entry, days=7)
            if latest_entry is not None
            else None
        ),
        trend_30d=(
            _window_change(entries, latest_entry=latest_entry, days=30)
            if latest_entry is not None
            else None
        ),
        goal_canonical_value=goal_value,
        distance_to_goal=_round_delta(
            latest_value - goal_value
            if latest_value is not None and goal_value is not None
            else None
        ),
        history_count=len(entries),
    )


def get_body_trends(
    measurement_repository: BodyMeasurementRepository,
    user_repository: UserRepository,
    *,
    profile_id: str,
    measurement_type: str = "weight",
    limit: int = 30,
) -> dict[str, object]:
    """Return trend points plus lightweight summary deltas for one measurement type."""
    entries = get_measurement_history(
        measurement_repository,
        user_repository,
        profile_id=profile_id,
        measurement_type=measurement_type,
        limit=limit,
    )
    if not entries:
        return {
            "profile_id": str(profile_id).strip(),
            "measurement_type": measurement_type,
            "points": [],
            "trend_7d": None,
            "trend_30d": None,
        }

    latest_entry = entries[0]
    return {
        "profile_id": str(profile_id).strip(),
        "measurement_type": measurement_type,
        "points": [
            {
                "measurement_id": entry.measurement_id,
                "measurement_type": entry.measurement_type,
                "canonical_value": entry.canonical_value,
                "measured_at": entry.measured_at,
                "source": entry.source,
                "note": entry.note,
            }
            for entry in reversed(entries)
        ],
        "trend_7d": _window_change(entries, latest_entry=latest_entry, days=7),
        "trend_30d": _window_change(entries, latest_entry=latest_entry, days=30),
    }
