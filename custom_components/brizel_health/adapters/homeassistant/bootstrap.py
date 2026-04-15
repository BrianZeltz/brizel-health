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
from ...infrastructure.repositories.ha_nutrition_repository import (
    HomeAssistantNutritionRepository,
)
from ...infrastructure.repositories.ha_recent_food_repository import (
    HomeAssistantRecentFoodRepository,
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
