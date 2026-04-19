"""Use cases for body goals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from ...core.interfaces.user_repository import UserRepository
from ...domains.body.interfaces.body_goal_repository import BodyGoalRepository
from ...domains.body.models.body_goal import (
    BODY_GOAL_TARGET_WEIGHT,
    BodyGoal,
    build_body_goal_record_id,
)
from ..users.user_use_cases import get_user


@dataclass(frozen=True)
class BodyGoalPeerSyncResult:
    """Outcome of one body-goal peer upsert."""

    goal: BodyGoal
    imported: int
    updated: int
    ignored: int

    def to_result_dict(self) -> dict[str, int]:
        """Serialize counters for bridge responses."""
        return {
            "imported": self.imported,
            "updated": self.updated,
            "ignored": self.ignored,
        }


def get_body_goal(
    repository: BodyGoalRepository,
    user_repository: UserRepository,
    profile_id: str,
) -> BodyGoal | None:
    """Return the current body goal for one profile."""
    user = get_user(user_repository, profile_id)
    return repository.get_by_profile_id(
        user.user_id,
        goal_type=BODY_GOAL_TARGET_WEIGHT,
    )


async def set_body_goal(
    repository: BodyGoalRepository,
    user_repository: UserRepository,
    profile_id: str,
    target_weight_kg: float | int,
) -> BodyGoal:
    """Create or update the current body goal for one profile."""
    user = get_user(user_repository, profile_id)
    existing_goal = repository.get_by_profile_id(
        user.user_id,
        goal_type=BODY_GOAL_TARGET_WEIGHT,
        include_deleted=True,
    )
    if existing_goal is None:
        goal = BodyGoal.create(
            profile_id=user.user_id,
            target_weight_kg=target_weight_kg,
        )
    else:
        goal = existing_goal
        goal.update(target_weight_kg=target_weight_kg)

    return await repository.upsert(goal)


async def delete_body_goal(
    repository: BodyGoalRepository,
    user_repository: UserRepository,
    profile_id: str,
) -> BodyGoal:
    """Tombstone the current target-weight goal for one profile."""
    user = get_user(user_repository, profile_id)
    return await repository.delete_by_profile_id_and_goal_type(
        user.user_id,
        BODY_GOAL_TARGET_WEIGHT,
    )


def get_body_goal_target_weight_records_for_peer(
    repository: BodyGoalRepository,
    *,
    profile_id: str,
    include_deleted: bool = True,
) -> list[BodyGoal]:
    """Return the target-weight goal CoreRecord for the body-goal peer pilot."""
    goal = repository.get_by_profile_id(
        str(profile_id).strip(),
        goal_type=BODY_GOAL_TARGET_WEIGHT,
        include_deleted=include_deleted,
    )
    return [] if goal is None else [goal]


async def upsert_body_goal_target_weight_peer_record(
    repository: BodyGoalRepository,
    *,
    incoming: BodyGoal,
) -> BodyGoalPeerSyncResult:
    """Upsert one peer-synced target-weight goal using v1 peer conflict rules."""
    if incoming.goal_type != BODY_GOAL_TARGET_WEIGHT:
        raise ValueError("Only target_weight body goals are supported by this pilot.")

    expected_record_id = build_body_goal_record_id(
        profile_id=incoming.profile_id,
        goal_type=incoming.goal_type,
    )
    if incoming.record_id != expected_record_id:
        raise ValueError("Body goal record_id must match profile_id and goal_type.")

    existing = repository.get_by_profile_id(
        incoming.profile_id,
        goal_type=incoming.goal_type,
        include_deleted=True,
    )
    if existing is None:
        saved = await repository.upsert(incoming)
        return BodyGoalPeerSyncResult(
            goal=saved,
            imported=1,
            updated=0,
            ignored=0,
        )

    if existing.record_id != incoming.record_id:
        raise ValueError("Body goal record_id belongs to another profile or goal type.")

    if not _incoming_body_goal_wins(existing=existing, incoming=incoming):
        return BodyGoalPeerSyncResult(
            goal=existing,
            imported=0,
            updated=0,
            ignored=1,
        )

    saved = await repository.upsert(incoming)
    return BodyGoalPeerSyncResult(
        goal=saved,
        imported=0,
        updated=1,
        ignored=0,
    )


def _incoming_body_goal_wins(
    *,
    existing: BodyGoal,
    incoming: BodyGoal,
) -> bool:
    if incoming.revision != existing.revision:
        return incoming.revision > existing.revision

    existing_updated_at = _parse_timestamp(existing.updated_at)
    incoming_updated_at = _parse_timestamp(incoming.updated_at)
    if incoming_updated_at != existing_updated_at:
        return incoming_updated_at > existing_updated_at

    return incoming.updated_by_node_id > existing.updated_by_node_id


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
