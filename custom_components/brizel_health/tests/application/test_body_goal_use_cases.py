"""Tests for body goal use cases."""

from __future__ import annotations

import pytest

from custom_components.brizel_health.application.body.body_goal_use_cases import (
    delete_body_goal,
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
            goal.record_id: goal for goal in goals or []
        }

    async def upsert(self, goal: BodyGoal) -> BodyGoal:
        self._goals[goal.record_id] = goal
        return goal

    async def delete_by_profile_id_and_goal_type(
        self,
        profile_id: str,
        goal_type: str = "target_weight",
    ) -> BodyGoal:
        goal = self.get_by_profile_id(profile_id)
        assert goal is not None
        goal.mark_deleted()
        self._goals[goal.record_id] = goal
        return goal

    def get_by_profile_id(
        self,
        profile_id: str,
        *,
        goal_type: str = "target_weight",
        include_deleted: bool = False,
    ) -> BodyGoal | None:
        return next(
            (
                goal
                for goal in self._goals.values()
                if goal.profile_id == profile_id
                and goal.goal_type == goal_type
                and (include_deleted or goal.deleted_at is None)
            ),
            None,
        )


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
    assert goal.record_id == "body_goal:profile-1:target_weight"
    assert goal.record_type == "body_goal"
    assert goal.goal_type == "target_weight"
    assert goal.target_value == 75.0
    assert goal.target_weight_kg == 75.0
    assert goal.source_type == "manual"
    assert goal.source_detail == "home_assistant"
    assert goal.origin_node_id == "home_assistant"
    assert goal.updated_by_node_id == "home_assistant"
    assert goal.revision == 1
    assert goal.payload_version == 1
    assert goal.deleted_at is None
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
    assert updated_goal.record_id == "body_goal:profile-1:target_weight"
    assert updated_goal.revision == 2
    assert repository.get_by_profile_id("profile-1") is updated_goal


@pytest.mark.asyncio
async def test_delete_body_goal_marks_target_weight_as_tombstone() -> None:
    """Deleting a body goal should tombstone the current target-weight record."""
    existing_goal = BodyGoal.create(
        profile_id="profile-1",
        target_weight_kg=80,
    )
    repository = InMemoryBodyGoalRepository([existing_goal])

    deleted_goal = await delete_body_goal(
        repository=repository,
        user_repository=_user_repository(),
        profile_id="profile-1",
    )

    assert deleted_goal is existing_goal
    assert deleted_goal.deleted_at is not None
    assert deleted_goal.revision == 2
    assert repository.get_by_profile_id("profile-1") is None


@pytest.mark.asyncio
async def test_set_body_goal_reactivates_existing_tombstone_with_next_revision() -> None:
    """Setting a deleted goal should reuse the same CoreRecord and advance revision."""
    existing_goal = BodyGoal.create(
        profile_id="profile-1",
        target_weight_kg=80,
    )
    existing_goal.mark_deleted()
    repository = InMemoryBodyGoalRepository([existing_goal])

    updated_goal = await set_body_goal(
        repository=repository,
        user_repository=_user_repository(),
        profile_id="profile-1",
        target_weight_kg=76,
    )

    assert updated_goal is existing_goal
    assert updated_goal.record_id == "body_goal:profile-1:target_weight"
    assert updated_goal.target_value == 76.0
    assert updated_goal.revision == 3
    assert updated_goal.deleted_at is None
