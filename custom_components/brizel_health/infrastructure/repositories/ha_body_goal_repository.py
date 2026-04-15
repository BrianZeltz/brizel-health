"""Home Assistant backed body goal repository."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...domains.body.models.body_goal import BodyGoal

if TYPE_CHECKING:
    from ..storage.store_manager import BrizelHealthStoreManager


class HomeAssistantBodyGoalRepository:
    """Persist body goals inside the integration store."""

    def __init__(self, store_manager: "BrizelHealthStoreManager") -> None:
        self._store_manager = store_manager

    def _goals(self) -> dict[str, dict]:
        body = self._store_manager.data.setdefault("body", {})
        return body.setdefault("goals", {})

    async def upsert(self, goal: BodyGoal) -> BodyGoal:
        self._goals()[goal.profile_id] = goal.to_dict()
        await self._store_manager.async_save()
        return goal

    def get_by_profile_id(self, profile_id: str) -> BodyGoal | None:
        goal_data = self._goals().get(str(profile_id).strip())
        if goal_data is None:
            return None
        return BodyGoal.from_dict(goal_data)
