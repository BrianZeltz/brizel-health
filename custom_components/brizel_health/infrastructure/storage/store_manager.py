"""Storage manager for Brizel Health."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from ...const import STORAGE_KEY, STORAGE_VERSION


def get_default_storage_data() -> dict[str, Any]:
    """Return the default persistent storage structure."""
    return {
        "profiles": {},
        "body": {
            "profiles": {},
            "goals": {},
            "measurements": {},
        },
        "nutrition": {
            "foods": {},
            "food_entries": {},
            "imported_food_cache": {},
            "recent_foods_by_profile": {},
        },
    }


class BrizelHealthStoreManager:
    """Manage persistent storage access for Brizel Health."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the store manager."""
        self.hass = hass
        self.store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.data: dict[str, Any] = get_default_storage_data()

    async def async_load(self) -> dict[str, Any]:
        """Load data from the Home Assistant store."""
        stored_data = await self.store.async_load()
        self.data = get_default_storage_data()

        if stored_data is not None:
            self.data.update(stored_data)
            body = self.data.setdefault("body", {})
            body.setdefault("profiles", {})
            body.setdefault("goals", {})
            body.setdefault("measurements", {})
            nutrition = self.data.setdefault("nutrition", {})
            nutrition.setdefault("foods", {})
            nutrition.setdefault("food_entries", {})
            nutrition.setdefault("imported_food_cache", {})
            nutrition.setdefault("recent_foods_by_profile", {})

            legacy_entries = nutrition.pop("entries", None)
            if "food_entries" not in nutrition:
                nutrition["food_entries"] = legacy_entries or {}
            elif legacy_entries:
                nutrition["food_entries"].update(legacy_entries)

        return self.data

    async def async_save(self) -> None:
        """Persist current storage data."""
        await self.store.async_save(self.data)
