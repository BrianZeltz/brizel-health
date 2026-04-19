"""Storage manager for Brizel Health."""

from __future__ import annotations

from datetime import UTC, datetime
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


def _migrate_food_log_source(data: dict[str, Any]) -> None:
    """Normalize legacy food-entry source fields into source_type/source_detail."""
    legacy_source = str(data.get("source") or "manual").strip().lower()
    if not legacy_source:
        legacy_source = "manual"

    source_type = str(data.get("source_type") or "").strip().lower()
    source_detail = str(data.get("source_detail") or "").strip().lower()

    if source_type == "manual_entry":
        source_type = "manual"
    if not source_type:
        if legacy_source == "barcode":
            source_type = "external_import"
            source_detail = source_detail or "barcode"
        elif legacy_source == "photo_ai":
            source_type = "external_import"
            source_detail = source_detail or "photo_ai"
        elif legacy_source == "imported":
            source_type = "external_import"
            source_detail = source_detail or "imported_food"
        else:
            source_type = "manual"
            source_detail = source_detail or "home_assistant"
    elif not source_detail or source_detail == "unknown":
        source_detail = "home_assistant" if source_type == "manual" else "unknown"

    data["source_type"] = source_type
    data["source_detail"] = source_detail
    data.setdefault("source", legacy_source)


def _migrate_food_log_entries(nutrition: dict[str, Any]) -> None:
    """Migrate persisted FoodEntry rows toward food_log CoreRecords."""
    food_entries = nutrition.setdefault("food_entries", {})
    if not isinstance(food_entries, dict):
        nutrition["food_entries"] = {}
        return

    now = datetime.now(UTC).isoformat()
    for entry_key, data in list(food_entries.items()):
        if not isinstance(data, dict):
            continue

        record_id = str(
            data.get("record_id") or data.get("food_entry_id") or entry_key
        ).strip()
        if not record_id:
            continue

        created_at = str(
            data.get("created_at") or data.get("consumed_at") or now
        ).strip()
        updated_at = str(data.get("updated_at") or created_at).strip()
        origin_node_id = str(
            data.get("origin_node_id") or "home_assistant"
        ).strip()
        if not origin_node_id:
            origin_node_id = "home_assistant"

        data.setdefault("record_id", record_id)
        data.setdefault("food_entry_id", record_id)
        data.setdefault("record_type", "food_log")
        data.setdefault("created_at", created_at)
        data.setdefault("updated_at", updated_at)
        data.setdefault("origin_node_id", origin_node_id)
        data.setdefault("updated_by_node_id", origin_node_id)
        data.setdefault("revision", 1)
        data.setdefault("payload_version", 1)
        data.setdefault("deleted_at", None)
        if "amount_grams" not in data and "grams" in data:
            data["amount_grams"] = data["grams"]
        if "grams" not in data and "amount_grams" in data:
            data["grams"] = data["amount_grams"]
        _migrate_food_log_source(data)

        if str(entry_key) != record_id:
            food_entries[record_id] = data
            del food_entries[entry_key]


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
            body_goals = body.setdefault("goals", {})
            for goal_key, data in list(body_goals.items()):
                if not isinstance(data, dict):
                    continue
                profile_id = str(data.get("profile_id") or goal_key).strip()
                goal_type = str(data.get("goal_type") or "target_weight").strip()
                if not profile_id or not goal_type:
                    continue
                record_id = str(
                    data.get("record_id") or f"body_goal:{profile_id}:{goal_type}"
                ).strip()
                if not record_id:
                    continue
                data.setdefault("record_id", record_id)
                data.setdefault("record_type", "body_goal")
                data.setdefault("source_type", "manual")
                data.setdefault("source_detail", "home_assistant")
                data.setdefault("origin_node_id", "home_assistant")
                data.setdefault("updated_by_node_id", data["origin_node_id"])
                data.setdefault("revision", 1)
                data.setdefault("payload_version", 1)
                data.setdefault("deleted_at", None)
                data.setdefault("goal_type", goal_type)
                if "target_value" not in data and "target_weight_kg" in data:
                    data["target_value"] = data["target_weight_kg"]
                if "target_weight_kg" not in data and "target_value" in data:
                    data["target_weight_kg"] = data["target_value"]
                data.setdefault("note", None)
                if str(goal_key) != record_id:
                    body_goals[record_id] = data
                    del body_goals[goal_key]
            body_measurements = body.setdefault("measurements", {})
            for measurement_key, data in list(body_measurements.items()):
                if not isinstance(data, dict):
                    continue
                data.setdefault(
                    "record_id",
                    data.get("measurement_id") or str(measurement_key),
                )
                data.setdefault("measurement_id", data["record_id"])
                data.setdefault("record_type", "body_measurement")
                legacy_source = str(data.get("source") or "manual").strip().lower()
                if not legacy_source:
                    legacy_source = "manual"
                if not str(data.get("source_type") or "").strip():
                    if legacy_source == "synced":
                        data["source_type"] = "external_import"
                        synced_source_detail = str(
                            data.get("source_detail") or ""
                        ).strip()
                        data["source_detail"] = (
                            synced_source_detail
                            if synced_source_detail
                            and synced_source_detail != "unknown"
                            else "peer_sync"
                        )
                    elif legacy_source == "imported":
                        data["source_type"] = "device_import"
                        data["source_detail"] = data.get("source_detail") or "unknown"
                    else:
                        data["source_type"] = "manual"
                        manual_source_detail = str(
                            data.get("source_detail") or ""
                        ).strip()
                        data["source_detail"] = (
                            manual_source_detail
                            if manual_source_detail
                            and manual_source_detail != "unknown"
                            else "home_assistant"
                        )
                else:
                    normalized_source_type = str(data["source_type"]).strip().lower()
                    if normalized_source_type == "manual_entry":
                        data["source_type"] = "manual"
                        if not str(data.get("source_detail") or "").strip():
                            data["source_detail"] = "home_assistant"
                        elif data.get("source_detail") == "unknown":
                            data["source_detail"] = "home_assistant"
                    elif normalized_source_type == "peer_sync":
                        data["source_type"] = "external_import"
                        if not str(data.get("source_detail") or "").strip():
                            data["source_detail"] = "peer_sync"
                        elif data.get("source_detail") == "unknown":
                            data["source_detail"] = "peer_sync"
                    data.setdefault("source_detail", "unknown")
                data.setdefault("origin_node_id", "home_assistant")
                data.setdefault("updated_by_node_id", data["origin_node_id"])
                data.setdefault("revision", 1)
                data.setdefault("payload_version", 1)
                data.setdefault("deleted_at", None)
                record_id = str(data.get("record_id") or "").strip()
                if record_id and str(measurement_key) != record_id:
                    body_measurements[record_id] = data
                    del body_measurements[measurement_key]
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
            _migrate_food_log_entries(nutrition)

        return self.data

    async def async_save(self) -> None:
        """Persist current storage data."""
        await self.store.async_save(self.data)
