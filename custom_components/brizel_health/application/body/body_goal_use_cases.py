"""Use cases for body goals."""

from __future__ import annotations

from ...core.interfaces.user_repository import UserRepository
from ...domains.body.interfaces.body_goal_repository import BodyGoalRepository
from ...domains.body.models.body_goal import BodyGoal
from ..users.user_use_cases import get_user


def get_body_goal(
    repository: BodyGoalRepository,
    user_repository: UserRepository,
    profile_id: str,
) -> BodyGoal | None:
    """Return the current body goal for one profile."""
    user = get_user(user_repository, profile_id)
    return repository.get_by_profile_id(user.user_id)


async def set_body_goal(
    repository: BodyGoalRepository,
    user_repository: UserRepository,
    profile_id: str,
    target_weight_kg: float | int,
) -> BodyGoal:
    """Create or update the current body goal for one profile."""
    user = get_user(user_repository, profile_id)
    existing_goal = repository.get_by_profile_id(user.user_id)
    if existing_goal is None:
        goal = BodyGoal.create(
            profile_id=user.user_id,
            target_weight_kg=target_weight_kg,
        )
    else:
        goal = existing_goal
        goal.update(target_weight_kg=target_weight_kg)

    return await repository.upsert(goal)
