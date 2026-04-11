"""Home Assistant backed food entry repository."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...domains.nutrition.errors import BrizelFoodEntryNotFoundError
from ...domains.nutrition.models.food_entry import FoodEntry

if TYPE_CHECKING:
    from ..storage.store_manager import BrizelHealthStoreManager


class HomeAssistantFoodEntryRepository:
    """Persist food entries inside the integration store."""

    def __init__(self, store_manager: "BrizelHealthStoreManager") -> None:
        """Initialize the repository."""
        self._store_manager = store_manager

    def _food_entries(self) -> dict[str, dict]:
        """Return the mutable food entry bucket."""
        nutrition = self._store_manager.data.setdefault("nutrition", {})
        return nutrition.setdefault("food_entries", {})

    async def add(self, food_entry: FoodEntry) -> FoodEntry:
        """Persist a new food entry."""
        self._food_entries()[food_entry.food_entry_id] = food_entry.to_dict()
        await self._store_manager.async_save()
        return food_entry

    async def delete(self, food_entry_id: str) -> FoodEntry:
        """Delete a food entry and return the removed entity."""
        deleted_food_entry = self.get_food_entry_by_id(food_entry_id)
        del self._food_entries()[food_entry_id]
        await self._store_manager.async_save()
        return deleted_food_entry

    def get_food_entry_by_id(self, food_entry_id: str) -> FoodEntry:
        """Load a food entry by ID."""
        food_entry_data = self._food_entries().get(food_entry_id)
        if food_entry_data is None:
            raise BrizelFoodEntryNotFoundError(
                f"No food entry found for food_entry_id '{food_entry_id}'."
            )

        return FoodEntry.from_dict(food_entry_data)

    def get_all_food_entries(self) -> list[FoodEntry]:
        """Load all food entries."""
        return [FoodEntry.from_dict(data) for data in self._food_entries().values()]
