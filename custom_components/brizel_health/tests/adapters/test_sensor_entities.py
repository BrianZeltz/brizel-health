"""Tests for optional Brizel sensor export setup."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from types import ModuleType
from types import SimpleNamespace

import pytest

homeassistant_module = sys.modules.setdefault("homeassistant", ModuleType("homeassistant"))
components_module = sys.modules.setdefault(
    "homeassistant.components",
    ModuleType("homeassistant.components"),
)
sensor_component_module = sys.modules.setdefault(
    "homeassistant.components.sensor",
    ModuleType("homeassistant.components.sensor"),
)


@dataclass(frozen=True)
class _SensorEntityDescription:
    key: str = ""
    name: str | None = None
    icon: str | None = None
    native_unit_of_measurement: object | None = None
    device_class: object | None = None
    state_class: object | None = None


class _SensorEntity:
    @property
    def unique_id(self) -> str | None:
        return getattr(self, "_attr_unique_id", None)

    def async_schedule_update_ha_state(self, force_refresh: bool = False) -> None:
        return None

    def async_write_ha_state(self) -> None:
        return None

    async def async_remove(self) -> None:
        return None


sensor_component_module.SensorDeviceClass = SimpleNamespace(TIMESTAMP="timestamp")
sensor_component_module.SensorEntity = _SensorEntity
sensor_component_module.SensorEntityDescription = _SensorEntityDescription
sensor_component_module.SensorStateClass = SimpleNamespace(MEASUREMENT="measurement")

config_entries_module = sys.modules.setdefault(
    "homeassistant.config_entries",
    ModuleType("homeassistant.config_entries"),
)
config_entries_module.ConfigEntry = object

const_module = sys.modules.setdefault(
    "homeassistant.const",
    ModuleType("homeassistant.const"),
)
const_module.UnitOfEnergy = SimpleNamespace(KILO_CALORIE="kcal")
const_module.UnitOfLength = SimpleNamespace(CENTIMETERS="cm")
const_module.UnitOfMass = SimpleNamespace(GRAMS="g", KILOGRAMS="kg")
const_module.UnitOfVolume = SimpleNamespace(MILLILITERS="ml")

core_module = sys.modules.setdefault(
    "homeassistant.core",
    ModuleType("homeassistant.core"),
)
core_module.HomeAssistant = object
core_module.callback = lambda func: func

helpers_module = sys.modules.setdefault(
    "homeassistant.helpers",
    ModuleType("homeassistant.helpers"),
)
device_registry_module = sys.modules.setdefault(
    "homeassistant.helpers.device_registry",
    ModuleType("homeassistant.helpers.device_registry"),
)
device_registry_module.DeviceEntryType = SimpleNamespace(SERVICE="service")
device_registry_module.DeviceInfo = dict
entity_registry_module = sys.modules.setdefault(
    "homeassistant.helpers.entity_registry",
    ModuleType("homeassistant.helpers.entity_registry"),
)
dispatcher_module = sys.modules.setdefault(
    "homeassistant.helpers.dispatcher",
    ModuleType("homeassistant.helpers.dispatcher"),
)
dispatcher_module.async_dispatcher_connect = lambda hass, signal, callback: (lambda: None)
entity_platform_module = sys.modules.setdefault(
    "homeassistant.helpers.entity_platform",
    ModuleType("homeassistant.helpers.entity_platform"),
)
entity_platform_module.AddEntitiesCallback = object
setattr(homeassistant_module, "components", components_module)
setattr(homeassistant_module, "config_entries", config_entries_module)
setattr(homeassistant_module, "const", const_module)
setattr(homeassistant_module, "core", core_module)
setattr(homeassistant_module, "helpers", helpers_module)
setattr(components_module, "sensor", sensor_component_module)
setattr(helpers_module, "device_registry", device_registry_module)
setattr(helpers_module, "entity_registry", entity_registry_module)
setattr(helpers_module, "dispatcher", dispatcher_module)
setattr(helpers_module, "entity_platform", entity_platform_module)

from custom_components.brizel_health.adapters.homeassistant.entities import sensor
from custom_components.brizel_health.adapters.homeassistant.sensor_export_configuration import (
    build_sensor_export_options,
)
from custom_components.brizel_health.const import DATA_BRIZEL


class _FakeEntry:
    """Small config entry stand-in for entity setup tests."""

    def __init__(self, options: dict[str, object]) -> None:
        self.options = options
        self.unload_callbacks: list[object] = []

    def async_on_unload(self, callback: object) -> None:
        self.unload_callbacks.append(callback)


class _FakeEntityRegistry:
    """Entity registry stand-in used by the sensor platform."""

    def __init__(self) -> None:
        self.removed_ids: list[str] = []

    def async_get_entity_id(
        self,
        platform: str,
        domain: str,
        unique_id: str,
    ) -> None:
        return None

    def async_remove(self, entity_id: str) -> None:
        self.removed_ids.append(entity_id)


class _FakeDeviceRegistry:
    """Device registry stand-in used by the sensor platform."""

    def async_get_device(self, identifiers: object) -> None:
        return None

    def async_update_device(self, device_id: str, **changes: object) -> None:
        return None


class _FakeProfile(SimpleNamespace):
    """Profile object with the fields the sensor platform reads."""


@pytest.fixture
def sensor_runtime(monkeypatch: pytest.MonkeyPatch) -> tuple[object, list[object]]:
    """Provide one minimal hass runtime and capture added entities."""
    added_entities: list[object] = []
    entity_registry = _FakeEntityRegistry()
    device_registry = _FakeDeviceRegistry()

    monkeypatch.setattr(
        sensor.er,
        "async_get",
        lambda hass: entity_registry,
        raising=False,
    )
    monkeypatch.setattr(
        sensor.dr,
        "async_get",
        lambda hass: device_registry,
        raising=False,
    )
    monkeypatch.setattr(
        sensor,
        "async_dispatcher_connect",
        lambda hass, signal, callback: (lambda: None),
    )
    monkeypatch.setattr(
        sensor,
        "get_all_users",
        lambda repository: [
            _FakeProfile(user_id="profile-a", display_name="Alpha"),
        ],
    )

    hass = SimpleNamespace(
        data={
            DATA_BRIZEL: {
                "runtime": {},
                "user_repository": object(),
            }
        },
        config=SimpleNamespace(time_zone="UTC"),
    )

    return hass, added_entities


@pytest.mark.asyncio
async def test_sensor_setup_adds_no_entities_when_exports_are_disabled(
    sensor_runtime: tuple[object, list[object]],
) -> None:
    """The sensor platform should stay silent when exports are off."""
    hass, added_entities = sensor_runtime
    entry = _FakeEntry(options={})

    await sensor.async_setup_entry(
        hass,
        entry,
        lambda entities, update_before_add=False: added_entities.extend(entities),
    )

    assert added_entities == []


@pytest.mark.asyncio
async def test_sensor_setup_adds_only_enabled_group_entities(
    sensor_runtime: tuple[object, list[object]],
) -> None:
    """Group toggles should constrain which sensor entities are exported."""
    hass, added_entities = sensor_runtime
    entry = _FakeEntry(
        options=build_sensor_export_options(
            enabled=True,
            form_values={
                "sensor_export_group_nutrition": False,
                "sensor_export_group_hydration": False,
                "sensor_export_group_body": False,
                "sensor_export_group_steps": True,
                "sensor_export_group_targets": False,
            },
        )
    )

    await sensor.async_setup_entry(
        hass,
        entry,
        lambda entities, update_before_add=False: added_entities.extend(entities),
    )

    assert added_entities
    assert {entity.entity_description.summary_group for entity in added_entities} == {
        "fit_steps"
    }
    assert {entity.entity_description.key for entity in added_entities} == {
        "today_steps",
        "last_steps_sync",
    }
