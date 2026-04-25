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
from ...domains.security.models.key_hierarchy import (
    EncryptedPayloadEnvelope,
    PROTECTED_DATA_CLASS_HISTORY_PAYLOADS,
)
from .ha_history_sync_journal_repository import (
    HomeAssistantHistorySyncJournalRepository,
)
from .ha_key_hierarchy_repository import HomeAssistantKeyHierarchyRepository
from ..security.ha_local_crypto_service import HomeAssistantLocalCryptoService

if TYPE_CHECKING:
    from ..storage.store_manager import BrizelHealthStoreManager


class HomeAssistantBodyGoalRepository:
    """Persist body goals inside the integration store."""

    def __init__(self, store_manager: "BrizelHealthStoreManager") -> None:
        self._store_manager = store_manager
        self._history_journal = HomeAssistantHistorySyncJournalRepository(
            store_manager
        )
        self._key_hierarchy_repository = HomeAssistantKeyHierarchyRepository(
            store_manager
        )
        self._crypto_service = HomeAssistantLocalCryptoService(
            self._key_hierarchy_repository
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
                existing_goal = self._deserialize_goal(data)
            except BrizelBodyGoalValidationError:
                continue
            if (
                existing_goal.profile_id == goal.profile_id
                and existing_goal.goal_type == goal.goal_type
            ):
                del goals[key]
        goals[goal.record_id] = await self._serialize_goal(goal)
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
        self._goals()[goal.record_id] = await self._serialize_goal(goal)
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
            goal = self._deserialize_goal(goal_data)
            if include_deleted or goal.deleted_at is None:
                return goal
            return None

        for data in self._goals().values():
            if not isinstance(data, dict):
                continue
            goal = self._deserialize_goal(data)
            if (
                goal.profile_id == normalized_profile_id
                and goal.goal_type == goal_type
                and (include_deleted or goal.deleted_at is None)
            ):
                return goal
        return None

    async def migrate_legacy_plaintext_goals(self) -> int:
        """Re-write legacy plaintext goals into encrypted payload form."""
        goals = self._goals()
        migrated = 0
        updated_goals = dict(goals)

        for key, data in goals.items():
            if not isinstance(data, dict):
                continue
            if isinstance(data.get("encrypted_payload"), dict):
                continue
            goal = self._deserialize_goal(data)
            serialized = await self._serialize_goal(goal)
            updated_goals[goal.record_id] = serialized
            if key != goal.record_id:
                updated_goals.pop(key, None)
            migrated += 1

        if migrated:
            self._store_manager.data.setdefault("body", {})["goals"] = updated_goals
            await self._store_manager.async_save()
        return migrated

    async def _serialize_goal(self, goal: BodyGoal) -> dict[str, object]:
        envelope = await self._crypto_service.encrypt_profile_payload(
            profile_id=goal.profile_id,
            data_class_id=PROTECTED_DATA_CLASS_HISTORY_PAYLOADS,
            payload={
                "goal_type": goal.goal_type,
                "target_value": goal.target_value,
                "note": goal.note,
            },
            aad_context=_body_goal_payload_aad_context(
                record_id=goal.record_id,
                profile_id=goal.profile_id,
                revision=goal.revision,
                updated_at=goal.updated_at,
            ),
        )
        return {
            "record_id": goal.record_id,
            "record_type": goal.record_type,
            "profile_id": goal.profile_id,
            "source_type": goal.source_type,
            "source_detail": goal.source_detail,
            "origin_node_id": goal.origin_node_id,
            "created_at": goal.created_at,
            "updated_at": goal.updated_at,
            "updated_by_node_id": goal.updated_by_node_id,
            "revision": goal.revision,
            "payload_version": goal.payload_version,
            "deleted_at": goal.deleted_at,
            "encrypted_payload": envelope.to_dict(),
        }

    def _deserialize_goal(self, data: dict[str, object]) -> BodyGoal:
        encrypted_payload = data.get("encrypted_payload")
        if not isinstance(encrypted_payload, dict):
            return BodyGoal.from_dict(data)
        payload = self._crypto_service.decrypt_profile_payload_sync(
            profile_id=str(data.get("profile_id") or "").strip(),
            envelope=EncryptedPayloadEnvelope.from_dict(encrypted_payload),
            expected_aad_context=_body_goal_payload_aad_context(
                record_id=str(data.get("record_id") or "").strip(),
                profile_id=str(data.get("profile_id") or "").strip(),
                revision=int(data.get("revision") or 0),
                updated_at=str(data.get("updated_at") or ""),
            ),
        )
        merged = dict(data)
        merged.update(payload)
        return BodyGoal.from_dict(merged)


def _body_goal_payload_aad_context(
    *,
    record_id: str,
    profile_id: str,
    revision: int,
    updated_at: str,
) -> dict[str, object]:
    return {
        "data_class_id": PROTECTED_DATA_CLASS_HISTORY_PAYLOADS,
        "storage": "body.goals",
        "record_type": "body_goal",
        "record_id": record_id,
        "profile_id": profile_id,
        "revision": revision,
        "updated_at": updated_at,
    }
