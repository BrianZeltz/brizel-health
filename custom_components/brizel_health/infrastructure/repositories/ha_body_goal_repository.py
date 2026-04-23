"""Home Assistant backed body goal repository."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...adapters.homeassistant.bridge_schemas import serialize_body_goal_peer_record
from ...domains.body.errors import BrizelBodyGoalValidationError
from ...domains.body.models.body_goal import (
    BODY_GOAL_TARGET_WEIGHT,
    BodyGoal,
    build_body_goal_record_id,
)
from .ha_history_sync_journal_repository import (
    HomeAssistantHistorySyncJournalRepository,
)

if TYPE_CHECKING:
    from ..storage.store_manager import BrizelHealthStoreManager


class HomeAssistantBodyGoalRepository:
    """Persist body goals inside the integration store."""

    def __init__(self, store_manager: "BrizelHealthStoreManager") -> None:
        self._store_manager = store_manager
        self._history_journal = HomeAssistantHistorySyncJournalRepository(
            store_manager
        )

    def _goals(self) -> dict[str, dict]:
        body = self._store_manager.data.setdefault("body", {})
        return body.setdefault("goals", {})

    async def upsert(self, goal: BodyGoal) -> BodyGoal:
        goals = self._goals()
        for key, data in list(goals.items()):
            if key == goal.record_id or not isinstance(data, dict):
                continue
            try:
                existing_goal = BodyGoal.from_dict(data)
            except BrizelBodyGoalValidationError:
                continue
            if (
                existing_goal.profile_id == goal.profile_id
                and existing_goal.goal_type == goal.goal_type
            ):
                del goals[key]
        goals[goal.record_id] = goal.to_dict()
        await self._store_manager.async_save()
        await self._history_journal.record_snapshot(
            domain="body_goals",
            profile_id=goal.profile_id,
            records=(goal,),
            serialize_record=serialize_body_goal_peer_record,
        )
        return goal

    async def delete_by_profile_id_and_goal_type(
        self,
        profile_id: str,
        goal_type: str = BODY_GOAL_TARGET_WEIGHT,
    ) -> BodyGoal:
        goal = self.get_by_profile_id(
            profile_id,
            goal_type=goal_type,
            include_deleted=True,
        )
        if goal is None:
            raise BrizelBodyGoalValidationError(
                f"No body goal found for profile_id '{profile_id}'."
            )
        goal.mark_deleted()
        self._goals()[goal.record_id] = goal.to_dict()
        await self._store_manager.async_save()
        await self._history_journal.record_snapshot(
            domain="body_goals",
            profile_id=goal.profile_id,
            records=(goal,),
            serialize_record=serialize_body_goal_peer_record,
        )
        return goal

    def get_by_profile_id(
        self,
        profile_id: str,
        *,
        goal_type: str = BODY_GOAL_TARGET_WEIGHT,
        include_deleted: bool = False,
    ) -> BodyGoal | None:
        normalized_profile_id = str(profile_id).strip()
        record_id = build_body_goal_record_id(
            profile_id=normalized_profile_id,
            goal_type=goal_type,
        )
        goal_data = self._goals().get(record_id) or self._goals().get(
            normalized_profile_id
        )
        if goal_data is not None:
            goal = BodyGoal.from_dict(goal_data)
            if include_deleted or goal.deleted_at is None:
                return goal
            return None

        for data in self._goals().values():
            if not isinstance(data, dict):
                continue
            goal = BodyGoal.from_dict(data)
            if (
                goal.profile_id == normalized_profile_id
                and goal.goal_type == goal_type
                and (include_deleted or goal.deleted_at is None)
            ):
                return goal
        return None
