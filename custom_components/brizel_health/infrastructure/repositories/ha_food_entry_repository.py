"""Home Assistant backed food entry repository."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...adapters.homeassistant.bridge_schemas import serialize_food_log_peer_record
from ...domains.nutrition.errors import BrizelFoodEntryNotFoundError
from ...domains.nutrition.models.food_entry import FoodEntry
from .ha_history_sync_journal_repository import (
    HomeAssistantHistorySyncJournalRepository,
)

if TYPE_CHECKING:
    from ..storage.store_manager import BrizelHealthStoreManager


class HomeAssistantFoodEntryRepository:
    """Persist food entries inside the integration store."""

    def __init__(self, store_manager: "BrizelHealthStoreManager") -> None:
        """Initialize the repository."""
        self._store_manager = store_manager
        self._history_journal = HomeAssistantHistorySyncJournalRepository(
            store_manager
        )

    def _food_entries(self) -> dict[str, dict]:
        """Return the mutable food entry bucket."""
        nutrition = self._store_manager.data.setdefault("nutrition", {})
        return nutrition.setdefault("food_entries", {})

    async def add(self, food_entry: FoodEntry) -> FoodEntry:
        """Persist a new food entry."""
        self._food_entries()[food_entry.record_id] = food_entry.to_dict()
        await self._store_manager.async_save()
        await self._history_journal.record_snapshot(
            domain="food_logs",
            profile_id=food_entry.profile_id,
            records=(food_entry,),
            serialize_record=serialize_food_log_peer_record,
        )
        return food_entry

    async def update(self, food_entry: FoodEntry) -> FoodEntry:
        """Persist an updated food entry."""
        self.get_food_entry_by_id(food_entry.record_id)
        self._food_entries()[food_entry.record_id] = food_entry.to_dict()
        await self._store_manager.async_save()
        await self._history_journal.record_snapshot(
            domain="food_logs",
            profile_id=food_entry.profile_id,
            records=(food_entry,),
            serialize_record=serialize_food_log_peer_record,
        )
        return food_entry

    async def delete(self, food_entry_id: str) -> FoodEntry:
        """Tombstone a food entry and return the updated entity."""
        deleted_food_entry = self.get_food_entry_by_id(food_entry_id)
        deleted_food_entry.mark_deleted()
        self._food_entries()[deleted_food_entry.record_id] = deleted_food_entry.to_dict()
        await self._store_manager.async_save()
        await self._history_journal.record_snapshot(
            domain="food_logs",
            profile_id=deleted_food_entry.profile_id,
            records=(deleted_food_entry,),
            serialize_record=serialize_food_log_peer_record,
        )
        return deleted_food_entry

    def get_food_entry_by_id(self, food_entry_id: str) -> FoodEntry:
        """Load a food entry by ID."""
        normalized_id = str(food_entry_id).strip()
        food_entry_data = self._food_entries().get(normalized_id)
        if food_entry_data is None:
            food_entry_data = next(
                (
                    data
                    for data in self._food_entries().values()
                    if str(data.get("record_id") or data.get("food_entry_id") or "").strip()
                    == normalized_id
                ),
                None,
            )
        if food_entry_data is None:
            raise BrizelFoodEntryNotFoundError(
                f"No food entry found for food_entry_id '{food_entry_id}'."
            )

        return FoodEntry.from_dict(food_entry_data)

    def get_all_food_entries(
        self,
        *,
        include_deleted: bool = False,
    ) -> list[FoodEntry]:
        """Load all food entries."""
        entries = [FoodEntry.from_dict(data) for data in self._food_entries().values()]
        if include_deleted:
            return entries
        return [entry for entry in entries if not entry.is_deleted]
