"""The Brizel Health integration."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from .const import (
    DATA_BRIZEL,
    FRONTEND_DIRECTORY,
    FRONTEND_RESOURCE_BASE_URL,
    PLATFORMS,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload one config entry after relevant options updates."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the Brizel Health integration domain."""
    from homeassistant.components.http import StaticPathConfig

    domain_data = hass.data.setdefault(DATA_BRIZEL, {})

    if not domain_data.get("frontend_registered", False):
        frontend_path = Path(__file__).parent / FRONTEND_DIRECTORY
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    FRONTEND_RESOURCE_BASE_URL,
                    str(frontend_path),
                    False,
                )
            ]
        )
        domain_data["frontend_registered"] = True

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Brizel Health from a config entry."""
    from .adapters.homeassistant.bootstrap import async_initialize_integration
    from .adapters.homeassistant.lovelace_resources import (
        async_ensure_lovelace_resources,
        async_schedule_lovelace_resource_retry,
    )

    await async_initialize_integration(hass, entry.entry_id, entry.options)

    if not await async_ensure_lovelace_resources(hass):
        async_schedule_lovelace_resource_retry(hass)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Brizel Health config entry."""
    from .adapters.homeassistant.bootstrap import async_finalize_integration

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    await async_finalize_integration(hass, entry.entry_id)
    return True
