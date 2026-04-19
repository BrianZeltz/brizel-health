"""Write use cases for nutrition food entries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from ...core.interfaces.user_repository import UserRepository
from ...domains.nutrition.errors import BrizelFoodEntryNotFoundError
from ...domains.nutrition.errors import BrizelFoodEntryValidationError
from ...domains.nutrition.interfaces.food_entry_repository import FoodEntryRepository
from ...domains.nutrition.interfaces.food_repository import FoodRepository
from ...domains.nutrition.interfaces.recent_food_repository import (
    RecentFoodRepository,
)
from ...domains.nutrition.models.food_entry import FoodEntry
from .recent_food_use_cases import remember_recent_food
from ..users.user_use_cases import get_user


@dataclass(frozen=True)
class FoodLogPeerSyncResult:
    """Outcome of one food-log peer upsert."""

    food_log: FoodEntry
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


async def create_food_entry(
    repository: FoodEntryRepository,
    user_repository: UserRepository,
    food_repository: FoodRepository,
    recent_food_repository: RecentFoodRepository | None,
    profile_id: str,
    food_id: str,
    grams: float | int,
    consumed_at: str | None = None,
    meal_type: str | None = None,
    note: str | None = None,
    source: str | None = None,
    recent_food_max_items: int = 20,
) -> FoodEntry:
    """Create and persist a food entry."""
    normalized_food_id = food_id.strip()
    if not normalized_food_id:
        raise BrizelFoodEntryValidationError("A food ID is required.")

    get_user(user_repository, profile_id)
    food = food_repository.get_food_by_id(normalized_food_id)
    food_entry = FoodEntry.create(
        profile_id=profile_id,
        food=food,
        grams=grams,
        consumed_at=consumed_at,
        meal_type=meal_type,
        note=note,
        source=source,
    )
    persisted_food_entry = await repository.add(food_entry)

    if recent_food_repository is not None:
        await remember_recent_food(
            recent_food_repository=recent_food_repository,
            food_repository=food_repository,
            profile_id=persisted_food_entry.profile_id,
            food_id=persisted_food_entry.food_id,
            used_at=persisted_food_entry.consumed_at,
            last_logged_grams=persisted_food_entry.grams,
            last_meal_type=persisted_food_entry.meal_type,
            max_items=recent_food_max_items,
        )

    return persisted_food_entry


async def delete_food_entry(
    repository: FoodEntryRepository,
    food_entry_id: str,
) -> FoodEntry:
    """Tombstone a food-log record and return the updated entry."""
    normalized_food_entry_id = food_entry_id.strip()
    if not normalized_food_entry_id:
        raise BrizelFoodEntryValidationError("A food entry ID is required.")

    return await repository.delete(normalized_food_entry_id)


def get_food_log_records_for_peer(
    repository: FoodEntryRepository,
    *,
    profile_id: str,
    include_deleted: bool = True,
) -> list[FoodEntry]:
    """Return food_log CoreRecords for the peer pilot."""
    return [
        entry
        for entry in repository.get_all_food_entries(
            include_deleted=include_deleted,
        )
        if entry.profile_id == str(profile_id).strip()
        and entry.record_type == "food_log"
    ]


async def upsert_food_log_peer_record(
    repository: FoodEntryRepository,
    *,
    incoming: FoodEntry,
) -> FoodLogPeerSyncResult:
    """Upsert one peer-synced food_log CoreRecord using v1 peer rules."""
    if incoming.record_type != "food_log":
        raise ValueError("Only food_log records are supported by this pilot.")

    try:
        existing = repository.get_food_entry_by_id(incoming.record_id)
    except BrizelFoodEntryNotFoundError:
        saved = await repository.add(incoming)
        return FoodLogPeerSyncResult(
            food_log=saved,
            imported=1,
            updated=0,
            ignored=0,
        )

    if existing.profile_id != incoming.profile_id:
        raise ValueError("Food log record_id belongs to another profile.")
    if existing.record_type != incoming.record_type:
        raise ValueError("Food log record_id belongs to another record type.")

    if not _incoming_food_log_wins(existing=existing, incoming=incoming):
        return FoodLogPeerSyncResult(
            food_log=existing,
            imported=0,
            updated=0,
            ignored=1,
        )

    saved = await repository.update(incoming)
    return FoodLogPeerSyncResult(
        food_log=saved,
        imported=0,
        updated=1,
        ignored=0,
    )


def _incoming_food_log_wins(
    *,
    existing: FoodEntry,
    incoming: FoodEntry,
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
