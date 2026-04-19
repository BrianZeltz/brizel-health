"""Food entry repository contract."""

from __future__ import annotations

from typing import Protocol

from ..models.food_entry import FoodEntry


class FoodEntryRepository(Protocol):
    """Persistence contract for nutrition food entries."""

    async def add(self, food_entry: FoodEntry) -> FoodEntry:
        """Persist a new food entry."""

    async def update(self, food_entry: FoodEntry) -> FoodEntry:
        """Persist an updated food entry."""

    async def delete(self, food_entry_id: str) -> FoodEntry:
        """Tombstone a food entry and return the updated entity."""

    def get_food_entry_by_id(self, food_entry_id: str) -> FoodEntry:
        """Load a food entry by ID."""

    def get_all_food_entries(
        self,
        *,
        include_deleted: bool = False,
    ) -> list[FoodEntry]:
        """Load all food entries."""
