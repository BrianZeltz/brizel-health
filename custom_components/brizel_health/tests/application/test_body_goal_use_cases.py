"""Tests for body goal use cases."""

from __future__ import annotations

import pytest

from custom_components.brizel_health.application.body.body_goal_use_cases import (
    get_body_goal,
    set_body_goal,
)
from custom_components.brizel_health.core.users.brizel_user import BrizelUser
from custom_components.brizel_health.core.users.errors import BrizelUserNotFoundError
from custom_components.brizel_health.domains.body.models.body_goal import BodyGoal


class InMemoryUserRepository:
    """Simple user repository for body-goal tests."""

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
    """Simple goal repository for body-goal tests."""

    def __init__(self, goals: list[BodyGoal] | None = None) -> None:
        self._goals = {
            goal.profile_id: goal for goal in goals or []
        }

    async def upsert(self, goal: BodyGoal) -> BodyGoal:
        self._goals[goal.profile_id] = goal
        return goal

    def get_by_profile_id(self, profile_id: str) -> BodyGoal | None:
        return self._goals.get(profile_id)


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
async def test_set_body_goal_creates_and_reads_profile_scoped_target_weight() -> None:
    """Setting a body goal should persist and expose one explicit target weight."""
    repository = InMemoryBodyGoalRepository()

    goal = await set_body_goal(
        repository=repository,
        user_repository=_user_repository(),
        profile_id=" profile-1 ",
        target_weight_kg=75,
    )

    stored_goal = get_body_goal(
        repository=repository,
        user_repository=_user_repository(),
        profile_id="profile-1",
    )

    assert goal.profile_id == "profile-1"
    assert goal.target_weight_kg == 75.0
    assert stored_goal is goal


@pytest.mark.asyncio
async def test_set_body_goal_updates_existing_goal_without_replacing_profile_scope() -> None:
    """Updating a goal should keep the profile binding and refresh the target."""
    existing_goal = BodyGoal.create(
        profile_id="profile-1",
        target_weight_kg=80,
    )
    repository = InMemoryBodyGoalRepository([existing_goal])

    updated_goal = await set_body_goal(
        repository=repository,
        user_repository=_user_repository(),
        profile_id="profile-1",
        target_weight_kg=76.5,
    )

    assert updated_goal is existing_goal
    assert updated_goal.target_weight_kg == 76.5
    assert repository.get_by_profile_id("profile-1") is updated_goal
