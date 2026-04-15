"""Tests for body measurement use cases and queries."""

from __future__ import annotations

import pytest

from custom_components.brizel_health.application.body.body_measurement_queries import (
    get_latest_measurement,
    get_measurement_history,
)
from custom_components.brizel_health.application.body.body_measurement_use_cases import (
    add_body_measurement,
    delete_body_measurement,
    update_body_measurement,
)
from custom_components.brizel_health.core.users.brizel_user import BrizelUser
from custom_components.brizel_health.core.users.errors import BrizelUserNotFoundError
from custom_components.brizel_health.domains.body.errors import (
    BrizelBodyMeasurementValidationError,
)
from custom_components.brizel_health.domains.body.models.body_measurement_entry import (
    BodyMeasurementEntry,
)


class InMemoryUserRepository:
    """Simple user repository for body-measurement tests."""

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


class InMemoryBodyMeasurementRepository:
    """Simple measurement repository for application tests."""

    def __init__(self, measurements: list[BodyMeasurementEntry] | None = None) -> None:
        self._measurements = {
            measurement.measurement_id: measurement for measurement in measurements or []
        }

    async def add(self, measurement: BodyMeasurementEntry) -> BodyMeasurementEntry:
        self._measurements[measurement.measurement_id] = measurement
        return measurement

    async def update(self, measurement: BodyMeasurementEntry) -> BodyMeasurementEntry:
        self._measurements[measurement.measurement_id] = measurement
        return measurement

    async def delete(self, measurement_id: str) -> BodyMeasurementEntry:
        return self._measurements.pop(measurement_id)

    def get_by_id(self, measurement_id: str) -> BodyMeasurementEntry:
        return self._measurements[str(measurement_id).strip()]

    def get_by_profile_id(self, profile_id: str) -> list[BodyMeasurementEntry]:
        normalized_profile_id = str(profile_id).strip()
        return [
            measurement
            for measurement in self._measurements.values()
            if measurement.profile_id == normalized_profile_id
        ]


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


@pytest.mark.asyncio
async def test_add_body_measurement_converts_imperial_inputs_to_canonical_metric() -> None:
    """Imperial user input should be stored canonically in kg and cm."""
    repository = InMemoryBodyMeasurementRepository()

    weight = await add_body_measurement(
        repository=repository,
        user_repository=_user_repository(),
        profile_id="profile-1",
        measurement_type="weight",
        value=185,
        unit="lb",
        measured_at="2026-04-15T07:30:00+00:00",
    )
    waist = await add_body_measurement(
        repository=repository,
        user_repository=_user_repository(),
        profile_id="profile-1",
        measurement_type="waist",
        value=34,
        unit="in",
        measured_at="2026-04-15T07:35:00+00:00",
    )

    assert weight.canonical_value == pytest.approx(83.9146, abs=0.0001)
    assert waist.canonical_value == pytest.approx(86.36, abs=0.0001)


@pytest.mark.asyncio
async def test_measurement_history_and_latest_stay_sorted_newest_first() -> None:
    """Measurement queries should return the newest entries first."""
    repository = InMemoryBodyMeasurementRepository()

    await add_body_measurement(
        repository=repository,
        user_repository=_user_repository(),
        profile_id="profile-1",
        measurement_type="weight",
        value=82.4,
        unit="kg",
        measured_at="2026-04-01T07:30:00+00:00",
    )
    latest = await add_body_measurement(
        repository=repository,
        user_repository=_user_repository(),
        profile_id="profile-1",
        measurement_type="weight",
        value=81.8,
        unit="kg",
        measured_at="2026-04-15T07:30:00+00:00",
    )

    history = get_measurement_history(
        repository,
        _user_repository(),
        profile_id="profile-1",
        measurement_type="weight",
    )
    latest_measurement = get_latest_measurement(
        repository,
        _user_repository(),
        profile_id="profile-1",
        measurement_type="weight",
    )

    assert [entry.canonical_value for entry in history] == [81.8, 82.4]
    assert latest_measurement is latest


@pytest.mark.asyncio
async def test_update_and_delete_body_measurement_keep_existing_flow_stable() -> None:
    """Measurements should be updatable and deletable without changing their scope."""
    repository = InMemoryBodyMeasurementRepository()
    measurement = await add_body_measurement(
        repository=repository,
        user_repository=_user_repository(),
        profile_id="profile-1",
        measurement_type="weight",
        value=80,
        unit="kg",
        measured_at="2026-04-15T07:30:00+00:00",
    )

    updated = await update_body_measurement(
        repository=repository,
        user_repository=_user_repository(),
        measurement_id=measurement.measurement_id,
        value=180,
        unit="lb",
        note="Morning weigh-in",
    )
    deleted = await delete_body_measurement(
        repository=repository,
        measurement_id=measurement.measurement_id,
    )

    assert updated.measurement_id == measurement.measurement_id
    assert updated.canonical_value == pytest.approx(81.6466, abs=0.0001)
    assert updated.note == "Morning weigh-in"
    assert deleted.measurement_id == measurement.measurement_id
    assert repository.get_by_profile_id("profile-1") == []


@pytest.mark.asyncio
async def test_add_body_measurement_rejects_invalid_values_and_types() -> None:
    """The write path should keep basic validation guardrails in place."""
    repository = InMemoryBodyMeasurementRepository()

    with pytest.raises(BrizelBodyMeasurementValidationError):
        await add_body_measurement(
            repository=repository,
            user_repository=_user_repository(),
            profile_id="profile-1",
            measurement_type="weight",
            value=0,
            unit="kg",
        )

    with pytest.raises(BrizelBodyMeasurementValidationError):
        await add_body_measurement(
            repository=repository,
            user_repository=_user_repository(),
            profile_id="profile-1",
            measurement_type="steps",
            value=10000,
            unit=None,
        )
