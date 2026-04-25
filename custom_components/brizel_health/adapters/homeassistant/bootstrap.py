"""Home Assistant bootstrap for Brizel Health."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.core import HomeAssistant

from ...const import DATA_BRIZEL
from ...infrastructure.repositories.ha_food_entry_repository import (
    HomeAssistantFoodEntryRepository,
)
from ...infrastructure.repositories.ha_body_profile_repository import (
    HomeAssistantBodyProfileRepository,
)
from ...infrastructure.repositories.ha_body_goal_repository import (
    HomeAssistantBodyGoalRepository,
)
from ...infrastructure.repositories.ha_body_measurement_repository import (
    HomeAssistantBodyMeasurementRepository,
)
from ...infrastructure.repositories.ha_imported_food_cache_repository import (
    HomeAssistantImportedFoodCacheRepository,
)
from ...infrastructure.repositories.ha_history_sync_journal_repository import (
    HomeAssistantHistorySyncJournalRepository,
)
from ...infrastructure.repositories.ha_key_hierarchy_repository import (
    HomeAssistantKeyHierarchyRepository,
)
from ...infrastructure.repositories.ha_nutrition_repository import (
    HomeAssistantNutritionRepository,
)
from ...infrastructure.repositories.ha_recent_food_repository import (
    HomeAssistantRecentFoodRepository,
)
from ...infrastructure.repositories.ha_step_repository import (
    HomeAssistantStepRepository,
)
from ...infrastructure.repositories.ha_user_repository import (
    HomeAssistantUserRepository,
)
from ...infrastructure.storage.store_manager import BrizelHealthStoreManager
from .source_configuration import create_food_source_registry
from .services import async_register_services, async_unregister_services


async def async_initialize_integration(
    hass: HomeAssistant,
    entry_id: str | None = None,
    entry_options: Mapping[str, Any] | None = None,
) -> None:
    """Initialize shared integration runtime objects."""
    domain_data = hass.data.setdefault(DATA_BRIZEL, {})
    domain_data.setdefault("config_entries", set())

    if entry_id is not None:
        domain_data["config_entries"].add(entry_id)

    if "storage" not in domain_data:
        storage = BrizelHealthStoreManager(hass)
        await storage.async_load()

        domain_data["storage"] = storage
        domain_data["profiles"] = storage.data.get("profiles", {})

    if "user_repository" not in domain_data:
        domain_data["user_repository"] = HomeAssistantUserRepository(
            domain_data["storage"]
        )

    if "body_profile_repository" not in domain_data:
        domain_data["body_profile_repository"] = HomeAssistantBodyProfileRepository(
            domain_data["storage"]
        )

    if "body_goal_repository" not in domain_data:
        domain_data["body_goal_repository"] = HomeAssistantBodyGoalRepository(
            domain_data["storage"]
        )

    if "body_measurement_repository" not in domain_data:
        domain_data["body_measurement_repository"] = (
            HomeAssistantBodyMeasurementRepository(domain_data["storage"])
        )

    if "nutrition_repository" not in domain_data:
        domain_data["nutrition_repository"] = HomeAssistantNutritionRepository(
            domain_data["storage"]
        )

    if "food_entry_repository" not in domain_data:
        domain_data["food_entry_repository"] = HomeAssistantFoodEntryRepository(
            domain_data["storage"]
        )

    if "imported_food_cache_repository" not in domain_data:
        domain_data["imported_food_cache_repository"] = (
            HomeAssistantImportedFoodCacheRepository(domain_data["storage"])
        )

    if "recent_food_repository" not in domain_data:
        domain_data["recent_food_repository"] = HomeAssistantRecentFoodRepository(
            domain_data["storage"]
        )

    if "step_repository" not in domain_data:
        domain_data["step_repository"] = HomeAssistantStepRepository(
            domain_data["storage"]
        )

    if "history_sync_journal_repository" not in domain_data:
        domain_data["history_sync_journal_repository"] = (
            HomeAssistantHistorySyncJournalRepository(domain_data["storage"])
        )

    if "key_hierarchy_repository" not in domain_data:
        domain_data["key_hierarchy_repository"] = HomeAssistantKeyHierarchyRepository(
            domain_data["storage"]
        )

    if not domain_data.get("legacy_plaintext_migration_completed", False):
        migrated_records = 0
        migrated_records += await domain_data[
            "body_profile_repository"
        ].migrate_legacy_plaintext_profiles()
        migrated_records += await domain_data[
            "body_goal_repository"
        ].migrate_legacy_plaintext_goals()
        migrated_records += await domain_data[
            "body_measurement_repository"
        ].migrate_legacy_plaintext_measurements()
        migrated_records += await domain_data[
            "food_entry_repository"
        ].migrate_legacy_plaintext_food_entries()
        migrated_records += await domain_data[
            "step_repository"
        ].migrate_legacy_plaintext_step_entries()
        domain_data["legacy_plaintext_migration_completed"] = True
        domain_data["legacy_plaintext_migrated_records"] = migrated_records

    domain_data["source_registry"] = create_food_source_registry(entry_options)

    if not domain_data.get("services_registered", False):
        await async_register_services(hass)
        domain_data["services_registered"] = True


async def async_finalize_integration(
    hass: HomeAssistant,
    entry_id: str,
) -> None:
    """Tear down shared integration runtime objects when the last entry unloads."""
    domain_data = hass.data.get(DATA_BRIZEL)
    if domain_data is None:
        return

    config_entries = domain_data.setdefault("config_entries", set())
    config_entries.discard(entry_id)

    if config_entries:
        return

    if domain_data.get("services_registered", False):
        await async_unregister_services(hass)

    hass.data.pop(DATA_BRIZEL, None)
