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
        "fit": {
            "steps_by_profile": {},
            "steps_import_state_by_profile": {},
            "step_source_priority_by_profile": {},
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
            fit = self.data.setdefault("fit", {})
            steps_by_profile = fit.setdefault("steps_by_profile", {})
            legacy_steps = fit.pop("steps", None)
            if legacy_steps:
                for external_record_id, data in legacy_steps.items():
                    profile_id = str(data.get("profile_id", "")).strip()
                    if not profile_id:
                        continue
                    steps_by_profile.setdefault(profile_id, {})[
                        str(external_record_id)
                    ] = data
            for profile_id, profile_steps in steps_by_profile.items():
                for external_record_id, data in profile_steps.items():
                    if not isinstance(data, dict):
                        continue
                    data.setdefault("external_record_id", str(external_record_id))
                    data.setdefault("profile_id", str(profile_id))
                    data.setdefault(
                        "record_id",
                        data.get("external_record_id")
                        or f"{profile_id}:{external_record_id}",
                    )
                    data.setdefault("record_type", "steps")
                    data.setdefault(
                        "origin_node_id",
                        data.get("device_id") or "unknown_node",
                    )
                    data.setdefault("source_type", "app_bridge")
                    data.setdefault("source_detail", data.get("source") or "unknown")
                    data.setdefault("updated_by_node_id", data["origin_node_id"])
                    data.setdefault("payload_version", 1)
                    data.setdefault("deleted_at", None)
                    data.setdefault("read_mode", data.get("origin") or "legacy")
                    data.setdefault("data_origin", None)
            fit.setdefault("steps_import_state_by_profile", {})
            fit.setdefault("step_source_priority_by_profile", {})
            fit.pop("steps_import_state", None)
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
