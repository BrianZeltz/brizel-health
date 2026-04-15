"""Tests for body progress queries."""

from __future__ import annotations

from custom_components.brizel_health.application.body.body_progress_queries import (
    get_body_progress_summary,
    get_body_trends,
)
from custom_components.brizel_health.core.users.brizel_user import BrizelUser
from custom_components.brizel_health.core.users.errors import BrizelUserNotFoundError
from custom_components.brizel_health.domains.body.models.body_goal import BodyGoal
from custom_components.brizel_health.domains.body.models.body_measurement_entry import (
    BodyMeasurementEntry,
)
from custom_components.brizel_health.domains.body.models.body_profile import BodyProfile


class InMemoryUserRepository:
    """Simple user repository for body-progress tests."""

    def __init__(self, users: list[BrizelUser]) -> None:
        self._users = {user.user_id: user for user in users}

    async def add(self, user: BrizelUser) -> BrizelUser:
        self._users[user.user_id] = user
        return user

    async def update(self, user: BrizelUser) -> BrizelUser:
        self._users[user.user_id] = user
        return user

    async def delete(self, user_id: str) -> BrizelUser:
        return self._users.pop(user_id)

    def get_by_id(self, user_id: str) -> BrizelUser:
        user = self._users.get(user_id)
        if user is None:
            raise BrizelUserNotFoundError(
                f"No profile found for profile_id '{user_id}'."
            )
        return user

    def get_all(self) -> list[BrizelUser]:
        return list(self._users.values())

    def display_name_exists(
        self,
        display_name: str,
        exclude_user_id: str | None = None,
    ) -> bool:
        return False


class InMemoryBodyGoalRepository:
    """Simple goal repository for progress tests."""

    def __init__(self, goal: BodyGoal | None = None) -> None:
        self._goal = goal

    async def upsert(self, goal: BodyGoal) -> BodyGoal:
        self._goal = goal
        return goal

    def get_by_profile_id(self, profile_id: str) -> BodyGoal | None:
        if self._goal is None or self._goal.profile_id != profile_id:
            return None
        return self._goal


class InMemoryBodyMeasurementRepository:
    """Simple measurement repository for progress tests."""

    def __init__(self, measurements: list[BodyMeasurementEntry] | None = None) -> None:
        self._measurements = list(measurements or [])

    async def add(self, measurement: BodyMeasurementEntry) -> BodyMeasurementEntry:
        self._measurements.append(measurement)
        return measurement

    async def update(self, measurement: BodyMeasurementEntry) -> BodyMeasurementEntry:
        self._measurements = [
            measurement if existing.measurement_id == measurement.measurement_id else existing
            for existing in self._measurements
        ]
        return measurement

    async def delete(self, measurement_id: str) -> BodyMeasurementEntry:
        raise NotImplementedError

    def get_by_id(self, measurement_id: str) -> BodyMeasurementEntry:
        for measurement in self._measurements:
            if measurement.measurement_id == measurement_id:
                return measurement
        raise AssertionError("Expected measurement to exist in tests")

    def get_by_profile_id(self, profile_id: str) -> list[BodyMeasurementEntry]:
        return [
            measurement
            for measurement in self._measurements
            if measurement.profile_id == profile_id
        ]


class InMemoryBodyProfileRepository:
    """Simple body profile repository for fallback tests."""

    def __init__(self, body_profile: BodyProfile | None = None) -> None:
        self._body_profile = body_profile

    async def upsert(self, body_profile: BodyProfile) -> BodyProfile:
        self._body_profile = body_profile
        return body_profile

    def get_by_profile_id(self, profile_id: str) -> BodyProfile | None:
        if self._body_profile is None or self._body_profile.profile_id != profile_id:
            return None
        return self._body_profile


def _user_repository() -> InMemoryUserRepository:
    return InMemoryUserRepository(
        [
            BrizelUser(
                user_id="profile-1",
                display_name="Alice",
                linked_ha_user_id=None,
                created_at="2026-04-08T08:00:00+00:00",
            )
        ]
    )


def _weight_entry(value: float, measured_at: str) -> BodyMeasurementEntry:
    return BodyMeasurementEntry.create(
        profile_id="profile-1",
        measurement_type="weight",
        canonical_value=value,
        measured_at=measured_at,
        source="manual",
    )


def test_get_body_progress_summary_returns_weight_deltas_goal_distance_and_trends() -> None:
    """Weight progress should expose the latest value, trend windows and goal distance."""
    repository = InMemoryBodyMeasurementRepository(
        [
            _weight_entry(80.0, "2026-04-01T07:30:00+00:00"),
            _weight_entry(79.0, "2026-04-08T07:30:00+00:00"),
            _weight_entry(78.5, "2026-04-15T07:30:00+00:00"),
        ]
    )
    goal_repository = InMemoryBodyGoalRepository(
        BodyGoal.create(profile_id="profile-1", target_weight_kg=75)
    )

    summary = get_body_progress_summary(
        measurement_repository=repository,
        goal_repository=goal_repository,
        user_repository=_user_repository(),
        profile_id="profile-1",
    )

    assert summary.latest_canonical_value == 78.5
    assert summary.previous_canonical_value == 79.0
    assert summary.first_canonical_value == 80.0
    assert summary.change_since_previous == -0.5
    assert summary.change_since_start == -1.5
    assert summary.trend_7d == -0.5
    assert summary.trend_30d == -1.5
    assert summary.goal_canonical_value == 75.0
    assert summary.distance_to_goal == 3.5
    assert summary.history_count == 3


def test_get_body_progress_summary_falls_back_to_profile_weight_without_fake_trends() -> None:
    """A static body-profile weight should seed the summary until real measurements exist."""
    summary = get_body_progress_summary(
        measurement_repository=InMemoryBodyMeasurementRepository(),
        goal_repository=InMemoryBodyGoalRepository(),
        user_repository=_user_repository(),
        profile_id="profile-1",
        body_profile_repository=InMemoryBodyProfileRepository(
            BodyProfile.create(profile_id="profile-1", weight_kg=82)
        ),
    )

    assert summary.latest_canonical_value == 82.0
    assert summary.latest_measured_at is None
    assert summary.change_since_previous is None
    assert summary.change_since_start is None
    assert summary.trend_7d is None
    assert summary.trend_30d is None
    assert summary.history_count == 0


def test_get_body_trends_returns_points_oldest_first_for_charting() -> None:
    """Trend points should stay chart-friendly while summary deltas remain available."""
    trends = get_body_trends(
        measurement_repository=InMemoryBodyMeasurementRepository(
            [
                _weight_entry(80.0, "2026-04-01T07:30:00+00:00"),
                _weight_entry(79.0, "2026-04-08T07:30:00+00:00"),
                _weight_entry(78.5, "2026-04-15T07:30:00+00:00"),
            ]
        ),
        user_repository=_user_repository(),
        profile_id="profile-1",
        measurement_type="weight",
    )

    assert [point["canonical_value"] for point in trends["points"]] == [80.0, 79.0, 78.5]
    assert trends["trend_7d"] == -0.5
    assert trends["trend_30d"] == -1.5
