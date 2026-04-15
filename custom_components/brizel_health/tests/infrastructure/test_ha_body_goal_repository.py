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
    """Goals should be persisted under the owning profile ID."""
    store_manager = FakeStoreManager({})
    repository = HomeAssistantBodyGoalRepository(store_manager)
    goal = BodyGoal.create(profile_id="profile-1", target_weight_kg=75)

    stored = await repository.upsert(goal)

    assert stored.profile_id == "profile-1"
    assert store_manager.data["body"]["goals"]["profile-1"]["target_weight_kg"] == 75.0
    assert store_manager.save_calls == 1


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
    assert goal.target_weight_kg == 74.5
