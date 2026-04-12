"""Button entities for Brizel Health."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ....application.nutrition.add_water import add_water, remove_water
from ....application.users.user_use_cases import get_all_users
from ....const import (
    DATA_BRIZEL,
    DOMAIN,
    SIGNAL_FOOD_ENTRY_CHANGED,
    SIGNAL_PROFILE_CREATED,
    SIGNAL_PROFILE_DELETED,
    SIGNAL_PROFILE_UPDATED,
)
from ....core.users.errors import (
    BrizelUserNotFoundError,
    BrizelUserValidationError,
)
from ....domains.nutrition.errors import (
    BrizelFoodEntryNotFoundError,
    BrizelFoodEntryValidationError,
    BrizelFoodNotFoundError,
    BrizelFoodValidationError,
)

_PRESS_TRANSLATABLE_ERRORS = (
    BrizelUserNotFoundError,
    BrizelUserValidationError,
    BrizelFoodEntryNotFoundError,
    BrizelFoodEntryValidationError,
    BrizelFoodNotFoundError,
    BrizelFoodValidationError,
)


@dataclass(frozen=True, kw_only=True)
class BrizelProfileButtonDescription(ButtonEntityDescription):
    """Static definition for one profile-scoped button."""


BUTTON_DESCRIPTIONS = (
    BrizelProfileButtonDescription(
        key="add_water",
        name="Add Water",
        icon="mdi:cup-water",
    ),
    BrizelProfileButtonDescription(
        key="remove_water",
        name="Remove Water",
        icon="mdi:cup-off",
    ),
)


def _data(hass: HomeAssistant) -> dict:
    """Return integration runtime data."""
    return hass.data[DATA_BRIZEL]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Brizel Health profile buttons from a config entry."""
    runtime = _data(hass).setdefault("runtime", {})
    # Always rebuild button entity objects on platform setup so HA never keeps
    # stale in-memory button instances across reloads or entity-shape changes.
    runtime["profile_button_entities"] = {}
    profile_entities: dict[str, list[BrizelProfileWaterButton]] = runtime[
        "profile_button_entities"
    ]

    @callback
    def _build_profile_buttons(
        profile_id: str,
        profile_name: str,
    ) -> list[BrizelProfileWaterButton]:
        return [
            BrizelProfileWaterButton(hass, profile_id, profile_name, description)
            for description in BUTTON_DESCRIPTIONS
        ]

    async def _async_remove_profile_buttons(profile_id: str) -> None:
        buttons = profile_entities.pop(profile_id, None)
        if buttons is None:
            return

        entity_registry = er.async_get(hass)
        for button in buttons:
            entity_id = entity_registry.async_get_entity_id(
                "button",
                DOMAIN,
                button.unique_id,
            )
            if entity_id is not None:
                entity_registry.async_remove(entity_id)
            await button.async_remove()

    async def _async_sync_profiles() -> None:
        profiles = {
            user.user_id: user for user in get_all_users(_data(hass)["user_repository"])
        }
        desired_ids = set(profiles)
        current_ids = set(profile_entities)

        for removed_profile_id in current_ids - desired_ids:
            await _async_remove_profile_buttons(removed_profile_id)

        new_entities: list[BrizelProfileWaterButton] = []
        for profile_id, profile in profiles.items():
            if profile_id not in profile_entities:
                buttons = _build_profile_buttons(profile_id, profile.display_name)
                profile_entities[profile_id] = buttons
                new_entities.extend(buttons)
                continue

            for button in profile_entities[profile_id]:
                button.set_profile_name(profile.display_name)
                button.async_write_ha_state()

        if new_entities:
            async_add_entities(new_entities, True)

    @callback
    def _handle_profile_change(payload: dict) -> None:
        hass.async_create_task(_async_sync_profiles())

    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_PROFILE_CREATED, _handle_profile_change)
    )
    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_PROFILE_UPDATED, _handle_profile_change)
    )
    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_PROFILE_DELETED, _handle_profile_change)
    )

    await _async_sync_profiles()


class BrizelProfileWaterButton(ButtonEntity):
    """Profile-scoped quick action for the water shortcut."""

    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        profile_id: str,
        profile_name: str,
        description: BrizelProfileButtonDescription,
    ) -> None:
        """Initialize the button."""
        self.hass = hass
        self._profile_id = profile_id
        self._profile_name = profile_name
        self.entity_description = description
        self._attr_name = description.name
        self._attr_icon = description.icon
        self._attr_unique_id = f"brizel_{profile_id}_{description.key}"
        self._attr_available = True

    def set_profile_name(self, profile_name: str) -> None:
        """Update the stored profile name."""
        self._profile_name = profile_name

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the shared profile device."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"profile_{self._profile_id}")},
            name=self._profile_name,
            manufacturer="Brizel",
            model="Brizel Health Profile",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Expose the related profile ID."""
        return {"profile_id": self._profile_id}

    async def async_press(self) -> None:
        """Execute the configured water shortcut for the related profile."""
        try:
            if self.entity_description.key == "add_water":
                food_entry = await add_water(
                    food_repository=_data(self.hass)["nutrition_repository"],
                    food_entry_repository=_data(self.hass)["food_entry_repository"],
                    user_repository=_data(self.hass)["user_repository"],
                    recent_food_repository=_data(self.hass).get(
                        "recent_food_repository"
                    ),
                    profile_id=self._profile_id,
                )
            else:
                food_entry = await remove_water(
                    food_repository=_data(self.hass)["nutrition_repository"],
                    food_entry_repository=_data(self.hass)["food_entry_repository"],
                    user_repository=_data(self.hass)["user_repository"],
                    profile_id=self._profile_id,
                )
        except _PRESS_TRANSLATABLE_ERRORS as err:
            raise HomeAssistantError(str(err)) from err

        async_dispatcher_send(
            self.hass,
            SIGNAL_FOOD_ENTRY_CHANGED,
            {"profile_id": food_entry.profile_id},
        )
