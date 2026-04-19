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
    get_body_measurement_records_for_peer,
    update_body_measurement,
    upsert_body_measurement_peer_record,
)
from custom_components.brizel_health.core.users.brizel_user import BrizelUser
from custom_components.brizel_health.core.users.errors import BrizelUserNotFoundError
from custom_components.brizel_health.domains.body.errors import (
    BrizelBodyMeasurementNotFoundError,
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
        measurement = self._measurements[measurement_id]
        measurement.mark_deleted()
        self._measurements[measurement.record_id] = measurement
        return measurement

    def get_by_id(self, measurement_id: str) -> BodyMeasurementEntry:
        measurement = self._measurements.get(str(measurement_id).strip())
        if measurement is None:
            raise BrizelBodyMeasurementNotFoundError(
                f"No body measurement found for measurement_id '{measurement_id}'."
            )
        return measurement

    def get_by_profile_id(
        self,
        profile_id: str,
        *,
        include_deleted: bool = False,
    ) -> list[BodyMeasurementEntry]:
        normalized_profile_id = str(profile_id).strip()
        return [
            measurement
            for measurement in self._measurements.values()
            if measurement.profile_id == normalized_profile_id
            and (include_deleted or measurement.deleted_at is None)
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
    assert weight.record_id == weight.measurement_id
    assert weight.record_type == "body_measurement"
    assert weight.source_type == "manual"
    assert weight.source_detail == "home_assistant"
    assert weight.origin_node_id == "home_assistant"
    assert weight.updated_by_node_id == "home_assistant"
    assert weight.revision == 1
    assert weight.payload_version == 1
    assert weight.deleted_at is None


def test_body_measurement_legacy_sources_map_to_spec_source_types() -> None:
    """Legacy source values should normalize to the Brizel source taxonomy."""
    base_data = {
        "measurement_id": "m1",
        "profile_id": "profile-1",
        "measurement_type": "weight",
        "canonical_value": 82.5,
        "measured_at": "2026-04-15T07:30:00+00:00",
        "note": None,
        "created_at": "2026-04-15T07:30:00+00:00",
        "updated_at": "2026-04-15T07:30:00+00:00",
    }

    manual = BodyMeasurementEntry.from_dict({**base_data, "source": "manual"})
    imported = BodyMeasurementEntry.from_dict({**base_data, "source": "imported"})
    synced = BodyMeasurementEntry.from_dict({**base_data, "source": "synced"})
    previous_manual_entry = BodyMeasurementEntry.from_dict(
        {**base_data, "source_type": "manual_entry", "source_detail": "home_assistant"}
    )
    previous_peer_sync = BodyMeasurementEntry.from_dict(
        {**base_data, "source_type": "peer_sync", "source_detail": "unknown"}
    )

    assert (manual.source_type, manual.source_detail) == ("manual", "home_assistant")
    assert (imported.source_type, imported.source_detail) == (
        "device_import",
        "unknown",
    )
    assert (synced.source_type, synced.source_detail) == (
        "external_import",
        "peer_sync",
    )
    assert (previous_manual_entry.source_type, previous_manual_entry.source_detail) == (
        "manual",
        "home_assistant",
    )
    assert (previous_peer_sync.source_type, previous_peer_sync.source_detail) == (
        "external_import",
        "peer_sync",
    )


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
    updated_revision = updated.revision
    deleted = await delete_body_measurement(
        repository=repository,
        measurement_id=measurement.measurement_id,
    )

    assert updated.measurement_id == measurement.measurement_id
    assert updated.canonical_value == pytest.approx(81.6466, abs=0.0001)
    assert updated.note == "Morning weigh-in"
    assert updated_revision == 2
    assert deleted.measurement_id == measurement.measurement_id
    assert deleted.record_id == measurement.record_id
    assert deleted.revision == updated_revision + 1
    assert deleted.deleted_at is not None
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


@pytest.mark.asyncio
async def test_weight_peer_upsert_uses_revision_and_tombstone_records() -> None:
    """Peer upsert should keep record identity and apply v1 conflict rules."""
    repository = InMemoryBodyMeasurementRepository()
    older = BodyMeasurementEntry.from_dict(
        {
            "record_id": "body_measurement:profile-1:node-app:manual:1",
            "record_type": "body_measurement",
            "profile_id": "profile-1",
            "source_type": "manual",
            "source_detail": "app_manual",
            "origin_node_id": "node-app",
            "created_at": "2026-04-18T07:00:00+00:00",
            "updated_at": "2026-04-18T07:00:00+00:00",
            "updated_by_node_id": "node-app",
            "revision": 1,
            "payload_version": 1,
            "deleted_at": None,
            "measurement_type": "weight",
            "canonical_value": 82.5,
            "measured_at": "2026-04-18T06:30:00+00:00",
            "note": None,
        }
    )
    newer = BodyMeasurementEntry.from_dict(
        {
            **older.to_dict(),
            "canonical_value": 82.1,
            "updated_at": "2026-04-18T08:00:00+00:00",
            "revision": 2,
            "deleted_at": "2026-04-18T08:00:00+00:00",
        }
    )

    imported = await upsert_body_measurement_peer_record(
        repository,
        incoming=older,
    )
    updated = await upsert_body_measurement_peer_record(
        repository,
        incoming=newer,
    )
    ignored = await upsert_body_measurement_peer_record(
        repository,
        incoming=older,
    )

    assert imported.to_result_dict() == {"imported": 1, "updated": 0, "ignored": 0}
    assert updated.to_result_dict() == {"imported": 0, "updated": 1, "ignored": 0}
    assert ignored.to_result_dict() == {"imported": 0, "updated": 0, "ignored": 1}
    assert repository.get_by_profile_id("profile-1") == []
    peer_records = get_body_measurement_records_for_peer(
        repository,
        profile_id="profile-1",
    )
    assert len(peer_records) == 1
    assert peer_records[0].record_id == older.record_id
    assert peer_records[0].revision == 2
    assert peer_records[0].deleted_at is not None


@pytest.mark.asyncio
async def test_body_measurement_peer_sync_supports_expansion_types() -> None:
    """The Body peer path should accept the v2 manual measurement types."""
    repository = InMemoryBodyMeasurementRepository()
    supported_types = (
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
    )

    for index, measurement_type in enumerate(supported_types, start=1):
        incoming = BodyMeasurementEntry.from_dict(
            {
                "record_id": (
                    f"body_measurement:profile-1:node-app:manual:{measurement_type}"
                ),
                "record_type": "body_measurement",
                "profile_id": "profile-1",
                "source_type": "manual",
                "source_detail": "app_manual",
                "origin_node_id": "node-app",
                "created_at": "2026-04-18T07:00:00+00:00",
                "updated_at": "2026-04-18T07:00:00+00:00",
                "updated_by_node_id": "node-app",
                "revision": 1,
                "payload_version": 1,
                "deleted_at": None,
                "measurement_type": measurement_type,
                "canonical_value": 80.0 + index,
                "measured_at": "2026-04-18T06:30:00+00:00",
                "note": None,
            }
        )

        result = await upsert_body_measurement_peer_record(
            repository,
            incoming=incoming,
        )

        assert result.to_result_dict() == {
            "imported": 1,
            "updated": 0,
            "ignored": 0,
        }

    peer_records = get_body_measurement_records_for_peer(
        repository,
        profile_id="profile-1",
    )
    assert {entry.measurement_type for entry in peer_records} == set(supported_types)
