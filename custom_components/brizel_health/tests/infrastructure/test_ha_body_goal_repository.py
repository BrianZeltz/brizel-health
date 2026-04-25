"""Tests for the Home Assistant body goal repository."""

from __future__ import annotations

import pytest

from custom_components.brizel_health.domains.body.models.body_goal import BodyGoal
from custom_components.brizel_health.infrastructure.repositories.ha_body_goal_repository import (
    HomeAssistantBodyGoalRepository,
)


class FakeStoreManager:
    """Minimal store manager stub for body-goal repository tests."""

    def __init__(self, data: dict) -> None:
        self.data = data
        self.save_calls = 0

    async def async_save(self) -> None:
        self.save_calls += 1


@pytest.mark.asyncio
async def test_repository_upsert_persists_goal_under_profile_scope() -> None:
    """Goals should be persisted under their stable CoreRecord ID."""
    store_manager = FakeStoreManager({})
    repository = HomeAssistantBodyGoalRepository(store_manager)
    goal = BodyGoal.create(profile_id="profile-1", target_weight_kg=75)

    stored = await repository.upsert(goal)

    assert stored.profile_id == "profile-1"
    stored_data = store_manager.data["body"]["goals"][
        "body_goal:profile-1:target_weight"
    ]
    assert stored_data["record_id"] == "body_goal:profile-1:target_weight"
    assert stored_data["record_type"] == "body_goal"
    assert stored_data["payload_version"] == 1
    assert stored_data["deleted_at"] is None
    assert isinstance(stored_data["encrypted_payload"], dict)
    assert "goal_type" not in stored_data
    assert "target_value" not in stored_data
    assert store_manager.save_calls >= 1


def test_repository_get_by_profile_id_parses_persisted_goal() -> None:
    """Stored goal data should round-trip through the repository."""
    repository = HomeAssistantBodyGoalRepository(
        FakeStoreManager(
            {
                "body": {
                    "goals": {
                        "profile-1": {
                            "profile_id": "profile-1",
                            "target_weight_kg": 74.5,
                            "created_at": "2026-04-15T08:00:00+00:00",
                            "updated_at": "2026-04-15T08:00:00+00:00",
                        }
                    }
                }
            }
        )
    )

    goal = repository.get_by_profile_id("profile-1")

    assert goal is not None
    assert goal.profile_id == "profile-1"
    assert goal.record_id == "body_goal:profile-1:target_weight"
    assert goal.goal_type == "target_weight"
    assert goal.target_weight_kg == 74.5


def test_repository_get_by_profile_id_hides_tombstoned_goal() -> None:
    """Standard goal queries should hide deleted CoreRecords."""
    repository = HomeAssistantBodyGoalRepository(
        FakeStoreManager(
            {
                "body": {
                    "goals": {
                        "body_goal:profile-1:target_weight": {
                            "record_id": "body_goal:profile-1:target_weight",
                            "record_type": "body_goal",
                            "profile_id": "profile-1",
                            "source_type": "manual",
                            "source_detail": "home_assistant",
                            "origin_node_id": "home_assistant",
                            "created_at": "2026-04-15T08:00:00+00:00",
                            "updated_at": "2026-04-16T08:00:00+00:00",
                            "updated_by_node_id": "home_assistant",
                            "revision": 2,
                            "payload_version": 1,
                            "deleted_at": "2026-04-16T08:00:00+00:00",
                            "goal_type": "target_weight",
                            "target_value": 74.5,
                            "note": None,
                        }
                    }
                }
            }
        )
    )

    assert repository.get_by_profile_id("profile-1") is None
