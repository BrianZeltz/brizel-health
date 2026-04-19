"""Repository interface for body goals."""

from __future__ import annotations

from typing import Protocol

from ..models.body_goal import BodyGoal


class BodyGoalRepository(Protocol):
    """Persistence interface for profile-scoped body-goal CoreRecords."""

    async def upsert(self, goal: BodyGoal) -> BodyGoal:
        """Store one body-goal CoreRecord."""

    async def delete_by_profile_id_and_goal_type(
        self,
        profile_id: str,
        goal_type: str = "target_weight",
    ) -> BodyGoal:
        """Tombstone the current goal state for one profile and goal type."""

    def get_by_profile_id(
        self,
        profile_id: str,
        *,
        goal_type: str = "target_weight",
        include_deleted: bool = False,
    ) -> BodyGoal | None:
        """Load the current goal state for one profile and goal type."""
