"""Lovelace resource registration for Brizel Health frontend cards."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from ...const import DATA_BRIZEL, FRONTEND_RESOURCE_URLS

if TYPE_CHECKING:
    from homeassistant.core import Event, HomeAssistant

_LOGGER = logging.getLogger(__name__)

_RESOURCE_TYPE = "module"
_RETRY_FLAG = "lovelace_resource_retry_registered"


async def _async_sync_resource_collection(
    resource_collection: Any,
    *,
    resource_urls: Sequence[str] = FRONTEND_RESOURCE_URLS,
) -> None:
    """Create or update the Brizel Health Lovelace resources idempotently."""
    if hasattr(resource_collection, "async_get_info"):
        await resource_collection.async_get_info()

    existing_by_url: dict[str, dict[str, Any]] = {}
    for item in resource_collection.async_items():
        if isinstance(item, dict) and isinstance(item.get("url"), str):
            existing_by_url[item["url"]] = item

    for url in resource_urls:
        try:
            existing = existing_by_url.get(url)
            if existing is None:
                await resource_collection.async_create_item(
                    {"url": url, "res_type": _RESOURCE_TYPE}
                )
                _LOGGER.info("Registered Lovelace resource for Brizel Health: %s", url)
                continue

            if existing.get("type") == _RESOURCE_TYPE:
                continue

            item_id = existing.get("id")
            if not item_id:
                _LOGGER.warning(
                    "Skipping Brizel Health Lovelace resource update for %s because "
                    "the existing resource has no item id.",
                    url,
                )
                continue

            await resource_collection.async_update_item(
                item_id,
                {"res_type": _RESOURCE_TYPE},
            )
            _LOGGER.info(
                "Updated Lovelace resource type for Brizel Health: %s -> %s",
                url,
                _RESOURCE_TYPE,
            )
        except Exception:  # pragma: no cover - defensive logging around HA internals
            _LOGGER.exception(
                "Failed to register or update Brizel Health Lovelace resource: %s",
                url,
            )


async def async_ensure_lovelace_resources(hass: HomeAssistant) -> bool:
    """Ensure packaged Brizel Health Lovelace resources exist.

    Returns `True` when no further retry is needed.
    Returns `False` when Lovelace is not ready yet and one retry should be scheduled.
    """

    from homeassistant.components.lovelace.const import LOVELACE_DATA, MODE_YAML

    lovelace_data = hass.data.get(LOVELACE_DATA)
    if lovelace_data is None:
        _LOGGER.debug(
            "Lovelace data is not available yet; Brizel Health resource registration "
            "will be retried later."
        )
        return False

    resource_mode = getattr(lovelace_data, "resource_mode", None)
    if resource_mode == MODE_YAML:
        _LOGGER.info(
            "Skipping automatic Brizel Health Lovelace resource registration because "
            "resource mode is %s. YAML-managed resources must still be configured "
            "manually.",
            resource_mode,
        )
        return True

    resource_collection = getattr(lovelace_data, "resources", None)
    if resource_collection is None:
        _LOGGER.debug(
            "Lovelace resources are not available yet in mode %s; Brizel Health "
            "resource registration will be retried later.",
            resource_mode,
        )
        return False

    try:
        await _async_sync_resource_collection(resource_collection)
    except Exception:  # pragma: no cover - defensive logging around HA internals
        _LOGGER.exception(
            "Failed to prepare Brizel Health Lovelace resources automatically."
        )

    return True


def async_schedule_lovelace_resource_retry(hass: HomeAssistant) -> None:
    """Schedule one deferred retry after Home Assistant startup completes."""

    from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
    from homeassistant.core import callback

    domain_data = hass.data.setdefault(DATA_BRIZEL, {})
    if domain_data.get(_RETRY_FLAG, False):
        return

    @callback
    def _async_retry(_: Event) -> None:
        domain_data[_RETRY_FLAG] = False
        hass.async_create_task(async_ensure_lovelace_resources(hass))

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _async_retry)
    domain_data[_RETRY_FLAG] = True
    _LOGGER.debug(
        "Scheduled a deferred retry for Brizel Health Lovelace resource registration."
    )
