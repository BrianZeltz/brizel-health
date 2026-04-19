"""Tests for the Home Assistant body measurement repository."""

from __future__ import annotations

import pytest

from custom_components.brizel_health.domains.body.models.body_measurement_entry import (
    BodyMeasurementEntry,
)
from custom_components.brizel_health.infrastructure.repositories.ha_body_measurement_repository import (
    HomeAssistantBodyMeasurementRepository,
)


class FakeStoreManager:
    """Minimal store manager stub for body-measurement repository tests."""

    def __init__(self, data: dict) -> None:
        self.data = data
        self.save_calls = 0

    async def async_save(self) -> None:
        self.save_calls += 1


@pytest.mark.asyncio
async def test_repository_add_update_and_delete_persist_measurements() -> None:
    """Body measurements should round-trip through add, update and tombstone delete."""
    store_manager = FakeStoreManager({})
    repository = HomeAssistantBodyMeasurementRepository(store_manager)
    measurement = repository.get_by_profile_id("profile-1")

    assert measurement == []

    entry = await repository.add(
        BodyMeasurementEntry.create(
            profile_id="profile-1",
            measurement_type="weight",
            canonical_value=82.5,
            measured_at="2026-04-15T07:30:00+00:00",
        )
    )
    entry.update(note="Morning weigh-in")
    updated = await repository.update(entry)
    deleted = await repository.delete(entry.measurement_id)

    assert updated.note == "Morning weigh-in"
    assert deleted.measurement_id == entry.measurement_id
    assert deleted.record_id == entry.record_id
    assert deleted.deleted_at is not None
    stored_deleted_at = store_manager.data["body"]["measurements"][entry.record_id][
        "deleted_at"
    ]
    assert stored_deleted_at is not None
    assert repository.get_by_profile_id("profile-1") == []
    assert store_manager.save_calls == 3


def test_repository_get_by_profile_id_returns_only_matching_measurements() -> None:
    """Profile lookups should stay profile-scoped."""
    repository = HomeAssistantBodyMeasurementRepository(
        FakeStoreManager(
            {
                "body": {
                    "measurements": {
                        "m1": {
                            "measurement_id": "m1",
                            "profile_id": "profile-1",
                            "measurement_type": "weight",
                            "canonical_value": 82.5,
                            "measured_at": "2026-04-15T07:30:00+00:00",
                            "source": "manual",
                            "note": None,
                            "created_at": "2026-04-15T07:30:00+00:00",
                            "updated_at": "2026-04-15T07:30:00+00:00",
                        },
                        "m2": {
                            "measurement_id": "m2",
                            "profile_id": "profile-2",
                            "measurement_type": "waist",
                            "canonical_value": 90.0,
                            "measured_at": "2026-04-15T07:35:00+00:00",
                            "source": "manual",
                            "note": None,
                            "created_at": "2026-04-15T07:35:00+00:00",
                            "updated_at": "2026-04-15T07:35:00+00:00",
                        },
                    }
                }
            }
        )
    )

    measurements = repository.get_by_profile_id("profile-1")

    assert len(measurements) == 1
    assert measurements[0].measurement_id == "m1"
    assert measurements[0].record_id == "m1"
    assert measurements[0].record_type == "body_measurement"
    assert measurements[0].source_type == "manual"
    assert measurements[0].source_detail == "home_assistant"
    assert measurements[0].origin_node_id == "home_assistant"
    assert measurements[0].updated_by_node_id == "home_assistant"
    assert measurements[0].revision == 1
    assert measurements[0].payload_version == 1
    assert measurements[0].deleted_at is None
