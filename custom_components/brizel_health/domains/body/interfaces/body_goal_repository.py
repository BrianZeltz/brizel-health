"""Repository interface for body goals."""

from __future__ import annotations

from typing import Protocol

from ..models.body_goal import BodyGoal


class BodyGoalRepository(Protocol):
    """Persistence interface for profile-scoped body goals."""

    async def upsert(self, goal: BodyGoal) -> BodyGoal:
        """Store one goal."""

    def get_by_profile_id(self, profile_id: str) -> BodyGoal | None:
        """Load the current goal for one profile."""
