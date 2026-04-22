"""Sensor entities for Brizel Health."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfLength, UnitOfMass, UnitOfVolume
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ....application.body.body_profile_use_cases import get_body_profile
from ....application.body.body_measurement_queries import get_latest_measurement
from ....application.body.body_progress_queries import get_body_progress_summary
from ....application.body.body_target_status_queries import (
    get_fat_target_status,
    get_kcal_target_status,
    get_protein_target_status,
)
from ....application.body.body_target_queries import get_body_targets
from ....application.fit.step_queries import (
    get_last_successful_steps_sync,
    resolve_steps_for_date,
)
from ....application.nutrition.daily_summary_queries import get_daily_summary
from ....application.nutrition.hydration_queries import get_daily_hydration_summary
from ....application.users.user_use_cases import get_all_users
from ....const import (
    DATA_BRIZEL,
    DOMAIN,
    SIGNAL_BODY_DATA_UPDATED,
    SIGNAL_BODY_PROFILE_UPDATED,
    SIGNAL_FIT_STEPS_UPDATED,
    SIGNAL_FOOD_CATALOG_CHANGED,
    SIGNAL_FOOD_ENTRY_CHANGED,
    SIGNAL_PROFILE_CREATED,
    SIGNAL_PROFILE_DELETED,
    SIGNAL_PROFILE_UPDATED,
)
from ....domains.body.errors import (
    BrizelBodyGoalValidationError,
    BrizelBodyMeasurementValidationError,
    BrizelBodyProfileValidationError,
)
from ....core.users.errors import BrizelUserNotFoundError, BrizelUserValidationError
from ....domains.nutrition.errors import BrizelFoodEntryValidationError


@dataclass(frozen=True, slots=True)
class BrizelProfileSensorDescription(SensorEntityDescription):
    """Static definition for one profile-backed sensor."""

    summary_group: str = ""
    value_key: str = ""
    range_value_key: str = ""
    uses_current_date: bool = True


FIT_STEP_SENSOR_DESCRIPTIONS = (
    BrizelProfileSensorDescription(
        key="today_steps",
        name="Today Steps",
        icon="mdi:walk",
        native_unit_of_measurement="steps",
        summary_group="fit_steps",
        value_key="today_steps",
    ),
    BrizelProfileSensorDescription(
        key="last_steps_sync",
        name="Last Steps Sync",
        icon="mdi:sync",
        device_class=SensorDeviceClass.TIMESTAMP,
        summary_group="fit_steps",
        value_key="last_steps_sync",
        uses_current_date=False,
    ),
)


NUTRITION_SENSOR_DESCRIPTIONS = (
    BrizelProfileSensorDescription(
        key="daily_kcal",
        name="Daily Kcal",
        icon="mdi:fire",
        native_unit_of_measurement=UnitOfEnergy.KILO_CALORIE,
        state_class=SensorStateClass.MEASUREMENT,
        summary_group="nutrition",
        value_key="kcal",
    ),
    BrizelProfileSensorDescription(
        key="daily_protein",
        name="Daily Protein",
        icon="mdi:food-steak",
        native_unit_of_measurement=UnitOfMass.GRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        summary_group="nutrition",
        value_key="protein",
    ),
    BrizelProfileSensorDescription(
        key="daily_carbs",
        name="Daily Carbs",
        icon="mdi:bread-slice",
        native_unit_of_measurement=UnitOfMass.GRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        summary_group="nutrition",
        value_key="carbs",
    ),
    BrizelProfileSensorDescription(
        key="daily_fat",
        name="Daily Fat",
        icon="mdi:oil",
        native_unit_of_measurement=UnitOfMass.GRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        summary_group="nutrition",
        value_key="fat",
    ),
)

HYDRATION_SENSOR_DESCRIPTIONS = (
    BrizelProfileSensorDescription(
        key="daily_drank_ml",
        name="Drank Today",
        icon="mdi:cup-water",
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        state_class=SensorStateClass.MEASUREMENT,
        summary_group="hydration",
        value_key="drank_ml",
    ),
    BrizelProfileSensorDescription(
        key="daily_food_hydration_ml",
        name="Food Hydration Today",
        icon="mdi:fruit-watermelon",
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        state_class=SensorStateClass.MEASUREMENT,
        summary_group="hydration",
        value_key="food_hydration_ml",
    ),
    BrizelProfileSensorDescription(
        key="daily_total_hydration_ml",
        name="Total Hydration Today",
        icon="mdi:water",
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        state_class=SensorStateClass.MEASUREMENT,
        summary_group="hydration",
        value_key="total_hydration_ml",
    ),
)

def _build_target_sensor_descriptions() -> tuple[BrizelProfileSensorDescription, ...]:
    """Return the static target-range sensors shown per profile."""
    target_definitions = (
        ("target_daily_kcal", "Target Daily Kcal", UnitOfEnergy.KILO_CALORIE, "mdi:fire"),
        ("target_daily_protein", "Target Daily Protein", UnitOfMass.GRAMS, "mdi:food-steak"),
        ("target_daily_fat", "Target Daily Fat", UnitOfMass.GRAMS, "mdi:oil"),
    )
    range_definitions = (
        ("low", "Low", "minimum"),
        ("recommended", "Recommended", "recommended"),
        ("high", "High", "maximum"),
    )

    return tuple(
        BrizelProfileSensorDescription(
            key=f"{target_key}_{range_key}",
            name=f"{target_name} {range_name}",
            icon=icon,
            native_unit_of_measurement=unit,
            state_class=SensorStateClass.MEASUREMENT,
            summary_group="body_targets",
            value_key=target_key,
            range_value_key=range_value_key,
            uses_current_date=False,
        )
        for target_key, target_name, unit, icon in target_definitions
        for range_key, range_name, range_value_key in range_definitions
    )


TARGET_SENSOR_DESCRIPTIONS = _build_target_sensor_descriptions()

TARGET_STATUS_SENSOR_DESCRIPTIONS = (
    BrizelProfileSensorDescription(
        key="kcal_target_status",
        name="Kcal Target Status",
        icon="mdi:fire",
        summary_group="body_target_status",
        value_key="target_daily_kcal",
        uses_current_date=True,
    ),
    BrizelProfileSensorDescription(
        key="protein_target_status",
        name="Protein Target Status",
        icon="mdi:food-steak",
        summary_group="body_target_status",
        value_key="target_daily_protein",
        uses_current_date=True,
    ),
    BrizelProfileSensorDescription(
        key="fat_target_status",
        name="Fat Target Status",
        icon="mdi:oil",
        summary_group="body_target_status",
        value_key="target_daily_fat",
        uses_current_date=True,
    ),
)

LEGACY_TARGET_SENSOR_KEYS = (
    "target_daily_kcal",
    "target_daily_protein",
    "target_daily_fat",
)

BODY_PROFILE_SENSOR_DESCRIPTIONS = (
    BrizelProfileSensorDescription(
        key="body_age_years",
        name="Age",
        icon="mdi:calendar-account",
        summary_group="body_profile",
        value_key="age_years",
        uses_current_date=False,
    ),
    BrizelProfileSensorDescription(
        key="body_sex",
        name="Sex",
        icon="mdi:account-details",
        summary_group="body_profile",
        value_key="sex",
        uses_current_date=False,
    ),
    BrizelProfileSensorDescription(
        key="body_height_cm",
        name="Height",
        icon="mdi:human-male-height",
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        summary_group="body_profile",
        value_key="height_cm",
        uses_current_date=False,
    ),
    BrizelProfileSensorDescription(
        key="body_weight_kg",
        name="Weight",
        icon="mdi:scale-bathroom",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        summary_group="body_profile",
        value_key="weight_kg",
        uses_current_date=False,
    ),
    BrizelProfileSensorDescription(
        key="body_activity_level",
        name="Activity Level",
        icon="mdi:run",
        summary_group="body_profile",
        value_key="activity_level",
        uses_current_date=False,
    ),
)

BODY_PROGRESS_SENSOR_DESCRIPTIONS = (
    BrizelProfileSensorDescription(
        key="current_weight",
        name="Current Weight",
        icon="mdi:scale-bathroom",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        summary_group="body_progress",
        value_key="latest_canonical_value",
        uses_current_date=False,
    ),
    BrizelProfileSensorDescription(
        key="last_body_measurement_date",
        name="Last Body Measurement",
        icon="mdi:calendar-clock",
        summary_group="body_progress",
        value_key="latest_measured_at",
        uses_current_date=False,
    ),
    BrizelProfileSensorDescription(
        key="weight_change_since_start",
        name="Weight Change Since Start",
        icon="mdi:trending-up",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        summary_group="body_progress",
        value_key="change_since_start",
        uses_current_date=False,
    ),
    BrizelProfileSensorDescription(
        key="weight_change_7d",
        name="Weight Change 7d",
        icon="mdi:chart-line",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        summary_group="body_progress",
        value_key="trend_7d",
        uses_current_date=False,
    ),
    BrizelProfileSensorDescription(
        key="distance_to_goal_weight",
        name="Distance To Goal Weight",
        icon="mdi:bullseye-arrow",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        summary_group="body_progress",
        value_key="distance_to_goal",
        uses_current_date=False,
    ),
)

BODY_MEASUREMENT_SENSOR_DESCRIPTIONS = (
    BrizelProfileSensorDescription(
        key="latest_body_weight",
        name="Latest Body Weight",
        icon="mdi:scale-bathroom",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        summary_group="body_measurements",
        value_key="weight",
        uses_current_date=False,
    ),
    BrizelProfileSensorDescription(
        key="latest_body_height",
        name="Latest Body Height",
        icon="mdi:human-male-height",
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        summary_group="body_measurements",
        value_key="height",
        uses_current_date=False,
    ),
    BrizelProfileSensorDescription(
        key="latest_body_waist",
        name="Latest Body Waist",
        icon="mdi:tape-measure",
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        summary_group="body_measurements",
        value_key="waist",
        uses_current_date=False,
    ),
    BrizelProfileSensorDescription(
        key="latest_body_abdomen",
        name="Latest Body Abdomen",
        icon="mdi:tape-measure",
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        summary_group="body_measurements",
        value_key="abdomen",
        uses_current_date=False,
    ),
    BrizelProfileSensorDescription(
        key="latest_body_hip",
        name="Latest Body Hip",
        icon="mdi:tape-measure",
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        summary_group="body_measurements",
        value_key="hip",
        uses_current_date=False,
    ),
    BrizelProfileSensorDescription(
        key="latest_body_chest",
        name="Latest Body Chest",
        icon="mdi:tape-measure",
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        summary_group="body_measurements",
        value_key="chest",
        uses_current_date=False,
    ),
    BrizelProfileSensorDescription(
        key="latest_body_upper_arm",
        name="Latest Body Upper Arm",
        icon="mdi:tape-measure",
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        summary_group="body_measurements",
        value_key="upper_arm",
        uses_current_date=False,
    ),
    BrizelProfileSensorDescription(
        key="latest_body_forearm",
        name="Latest Body Forearm",
        icon="mdi:tape-measure",
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        summary_group="body_measurements",
        value_key="forearm",
        uses_current_date=False,
    ),
    BrizelProfileSensorDescription(
        key="latest_body_thigh",
        name="Latest Body Thigh",
        icon="mdi:tape-measure",
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        summary_group="body_measurements",
        value_key="thigh",
        uses_current_date=False,
    ),
    BrizelProfileSensorDescription(
        key="latest_body_calf",
        name="Latest Body Calf",
        icon="mdi:tape-measure",
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        summary_group="body_measurements",
        value_key="calf",
        uses_current_date=False,
    ),
    BrizelProfileSensorDescription(
        key="latest_body_neck",
        name="Latest Body Neck",
        icon="mdi:tape-measure",
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        summary_group="body_measurements",
        value_key="neck",
        uses_current_date=False,
    ),
)

SENSOR_DESCRIPTIONS = (
    NUTRITION_SENSOR_DESCRIPTIONS
    + HYDRATION_SENSOR_DESCRIPTIONS
    + BODY_PROFILE_SENSOR_DESCRIPTIONS
    + BODY_MEASUREMENT_SENSOR_DESCRIPTIONS
    + BODY_PROGRESS_SENSOR_DESCRIPTIONS
    + FIT_STEP_SENSOR_DESCRIPTIONS
    + TARGET_STATUS_SENSOR_DESCRIPTIONS
    + TARGET_SENSOR_DESCRIPTIONS
)


def _data(hass: HomeAssistant) -> dict:
    """Return integration runtime data."""
    return hass.data[DATA_BRIZEL]


def _resolve_fit_activity_level(
    domain_data: dict[str, object],
    profile_id: str,
) -> str | None:
    """Best-effort Fit-owned activity context without making Body the owner."""
    for key in ("fit_profile_repository", "activity_profile_repository"):
        repository = domain_data.get(key)
        if repository is None:
            continue
        for method_name in ("get_by_profile_id", "get_profile", "get"):
            method = getattr(repository, method_name, None)
            if method is None:
                continue
            try:
                fit_profile = method(profile_id)
            except TypeError:
                continue
            activity_level = str(
                getattr(fit_profile, "activity_level", "") or ""
            ).strip()
            if activity_level:
                return activity_level
    return None


def _today_date() -> str:
    """Return the current UTC date in ISO format."""
    return datetime.now(UTC).date().isoformat()


def _hass_time_zone(hass: HomeAssistant) -> tzinfo:
    """Return Home Assistant's configured time zone, falling back to UTC."""
    time_zone_name = getattr(hass.config, "time_zone", None)
    if time_zone_name:
        try:
            return ZoneInfo(time_zone_name)
        except ZoneInfoNotFoundError:
            return UTC
    return UTC


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Brizel Health sensors from a config entry."""
    runtime = _data(hass).setdefault("runtime", {})
    profile_entities: dict[str, list[BrizelProfileDailySensor]] = runtime.setdefault(
        "profile_sensor_entities",
        {},
    )

    @callback
    def _build_profile_sensors(
        profile_id: str,
        profile_name: str,
    ) -> list[BrizelProfileDailySensor]:
        return [
            BrizelProfileDailySensor(hass, profile_id, profile_name, description)
            for description in SENSOR_DESCRIPTIONS
        ]

    @callback
    def _schedule_profile_refresh(profile_id: str | None = None) -> None:
        if profile_id is None:
            for entities in profile_entities.values():
                for sensor in entities:
                    sensor.async_schedule_update_ha_state(True)
            return

        for sensor in profile_entities.get(profile_id, []):
            sensor.async_schedule_update_ha_state(True)

    async def _async_remove_profile_entities(profile_id: str) -> None:
        entities = profile_entities.pop(profile_id, [])
        entity_registry = er.async_get(hass)
        device_registry = dr.async_get(hass)

        for sensor in entities:
            entity_id = entity_registry.async_get_entity_id(
                "sensor",
                DOMAIN,
                sensor.unique_id,
            )
            if entity_id is not None:
                entity_registry.async_remove(entity_id)
            await sensor.async_remove()

        device = device_registry.async_get_device(
            identifiers={(DOMAIN, f"profile_{profile_id}")}
        )
        if device is not None:
            try:
                device_registry.async_remove_device(device.id)
            except Exception:
                pass

    async def _async_remove_legacy_target_entities(profile_id: str) -> None:
        entity_registry = er.async_get(hass)
        for legacy_key in LEGACY_TARGET_SENSOR_KEYS:
            entity_id = entity_registry.async_get_entity_id(
                "sensor",
                DOMAIN,
                f"brizel_{profile_id}_{legacy_key}",
            )
            if entity_id is not None:
                entity_registry.async_remove(entity_id)

    async def _async_sync_profiles() -> None:
        profiles = {
            user.user_id: user for user in get_all_users(_data(hass)["user_repository"])
        }
        desired_ids = set(profiles)
        current_ids = set(profile_entities)
        device_registry = dr.async_get(hass)

        for removed_profile_id in current_ids - desired_ids:
            await _async_remove_profile_entities(removed_profile_id)

        new_entities: list[BrizelProfileDailySensor] = []
        for profile_id, profile in profiles.items():
            await _async_remove_legacy_target_entities(profile_id)

            if profile_id not in profile_entities:
                entities = _build_profile_sensors(profile_id, profile.display_name)
                profile_entities[profile_id] = entities
                new_entities.extend(entities)
                continue

            device = device_registry.async_get_device(
                identifiers={(DOMAIN, f"profile_{profile_id}")}
            )
            if device is not None:
                device_registry.async_update_device(
                    device.id,
                    name=profile.display_name,
                )

            for sensor in profile_entities[profile_id]:
                sensor.set_profile_name(profile.display_name)
                sensor.async_write_ha_state()

        if new_entities:
            async_add_entities(new_entities, True)

    @callback
    def _handle_profile_change(payload: dict) -> None:
        hass.async_create_task(_async_sync_profiles())

    @callback
    def _handle_food_entry_changed(payload: dict) -> None:
        _schedule_profile_refresh(payload.get("profile_id"))

    @callback
    def _handle_food_catalog_changed(payload: dict) -> None:
        _schedule_profile_refresh()

    @callback
    def _handle_body_profile_changed(payload: dict) -> None:
        _schedule_profile_refresh(payload.get("profile_id"))

    @callback
    def _handle_body_data_changed(payload: dict) -> None:
        _schedule_profile_refresh(payload.get("profile_id"))

    @callback
    def _handle_fit_steps_updated(payload: dict) -> None:
        _schedule_profile_refresh(payload.get("profile_id"))

    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_PROFILE_CREATED, _handle_profile_change)
    )
    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_PROFILE_UPDATED, _handle_profile_change)
    )
    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_PROFILE_DELETED, _handle_profile_change)
    )
    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            SIGNAL_FOOD_ENTRY_CHANGED,
            _handle_food_entry_changed,
        )
    )
    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            SIGNAL_FOOD_CATALOG_CHANGED,
            _handle_food_catalog_changed,
        )
    )
    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            SIGNAL_BODY_PROFILE_UPDATED,
            _handle_body_profile_changed,
        )
    )
    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            SIGNAL_BODY_DATA_UPDATED,
            _handle_body_data_changed,
        )
    )
    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            SIGNAL_FIT_STEPS_UPDATED,
            _handle_fit_steps_updated,
        )
    )

    await _async_sync_profiles()


class BrizelProfileDailySensor(SensorEntity):
    """Per-profile nutrition, hydration, body, or target sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = True

    entity_description: BrizelProfileSensorDescription

    def __init__(
        self,
        hass: HomeAssistant,
        profile_id: str,
        profile_name: str,
        description: BrizelProfileSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._profile_id = profile_id
        self._profile_name = profile_name
        self.entity_description = description
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

    async def async_update(self) -> None:
        """Refresh the daily sensor value from application queries."""
        try:
            if self.entity_description.summary_group == "nutrition":
                today = _today_date()
                summary = get_daily_summary(
                    repository=_data(self.hass)["food_entry_repository"],
                    user_repository=_data(self.hass)["user_repository"],
                    profile_id=self._profile_id,
                    date=today,
                )
                extra_state_attributes = {
                    "profile_id": self._profile_id,
                    "date": today,
                    "summary_group": self.entity_description.summary_group,
                }
            elif self.entity_description.summary_group == "hydration":
                today = _today_date()
                summary = get_daily_hydration_summary(
                    food_entry_repository=_data(self.hass)["food_entry_repository"],
                    food_repository=_data(self.hass)["nutrition_repository"],
                    user_repository=_data(self.hass)["user_repository"],
                    profile_id=self._profile_id,
                    date=today,
                )
                extra_state_attributes = {
                    "profile_id": self._profile_id,
                    "date": today,
                    "summary_group": self.entity_description.summary_group,
                }
            elif self.entity_description.summary_group == "body_profile":
                summary = get_body_profile(
                    repository=_data(self.hass)["body_profile_repository"],
                    user_repository=_data(self.hass)["user_repository"],
                    profile_id=self._profile_id,
                ).to_dict()
                activity_level_override = _resolve_fit_activity_level(
                    _data(self.hass),
                    self._profile_id,
                )
                if activity_level_override:
                    summary["activity_level"] = activity_level_override
                extra_state_attributes = {
                    "profile_id": self._profile_id,
                    "summary_group": self.entity_description.summary_group,
                }
            elif self.entity_description.summary_group == "body_measurements":
                measurement = get_latest_measurement(
                    repository=_data(self.hass)["body_measurement_repository"],
                    user_repository=_data(self.hass)["user_repository"],
                    profile_id=self._profile_id,
                    measurement_type=self.entity_description.value_key,
                )
                self._attr_native_value = (
                    None if measurement is None else measurement.canonical_value
                )
                self._attr_extra_state_attributes = {
                    "profile_id": self._profile_id,
                    "summary_group": self.entity_description.summary_group,
                    "measurement_type": self.entity_description.value_key,
                    "record_id": None if measurement is None else measurement.record_id,
                    "measured_at": None if measurement is None else measurement.measured_at,
                    "updated_at": None if measurement is None else measurement.updated_at,
                    "revision": None if measurement is None else measurement.revision,
                    "source_type": None if measurement is None else measurement.source_type,
                    "source_detail": (
                        None if measurement is None else measurement.source_detail
                    ),
                }
                self._attr_available = True
                return
            elif self.entity_description.summary_group == "body_progress":
                summary = get_body_progress_summary(
                    measurement_repository=_data(self.hass)["body_measurement_repository"],
                    goal_repository=_data(self.hass)["body_goal_repository"],
                    body_profile_repository=_data(self.hass)["body_profile_repository"],
                    user_repository=_data(self.hass)["user_repository"],
                    profile_id=self._profile_id,
                    measurement_type="weight",
                ).to_dict()
                extra_state_attributes = {
                    "profile_id": self._profile_id,
                    "summary_group": self.entity_description.summary_group,
                    "measurement_type": "weight",
                    "history_count": summary["history_count"],
                    "goal_canonical_value": summary["goal_canonical_value"],
                    "latest_measured_at": summary["latest_measured_at"],
                }
            elif self.entity_description.summary_group == "fit_steps":
                repository = _data(self.hass)["step_repository"]
                if self.entity_description.value_key == "today_steps":
                    time_zone = _hass_time_zone(self.hass)
                    today = datetime.now(time_zone).date()
                    resolution = resolve_steps_for_date(
                        repository=repository,
                        profile_id=self._profile_id,
                        target_date=today,
                        time_zone=time_zone,
                    )
                    self._attr_native_value = resolution.total_steps
                    self._attr_extra_state_attributes = {
                        "profile_id": self._profile_id,
                        "date": today.isoformat(),
                        "summary_group": self.entity_description.summary_group,
                        "entry_count": len(resolution.timeline),
                        "discarded_entry_count": len(resolution.discarded_records),
                        "used_sources": list(resolution.used_sources),
                        "discarded_sources": list(resolution.discarded_sources),
                        "resolution_notes": list(resolution.notes),
                        "source": "fit_step_resolver_v1",
                    }
                else:
                    self._attr_native_value = get_last_successful_steps_sync(
                        repository=repository,
                        profile_id=self._profile_id,
                    )
                    self._attr_extra_state_attributes = {
                        "profile_id": self._profile_id,
                        "summary_group": self.entity_description.summary_group,
                        "source": "fit_step_repository",
                    }
                self._attr_available = True
                return
            elif self.entity_description.summary_group == "body_target_status":
                today = _today_date()
                activity_level_override = _resolve_fit_activity_level(
                    _data(self.hass),
                    self._profile_id,
                )
                if self.entity_description.value_key == "target_daily_kcal":
                    summary = get_kcal_target_status(
                        food_entry_repository=_data(self.hass)["food_entry_repository"],
                        body_profile_repository=_data(self.hass)["body_profile_repository"],
                        body_measurement_repository=_data(self.hass)["body_measurement_repository"],
                        user_repository=_data(self.hass)["user_repository"],
                        profile_id=self._profile_id,
                        date=today,
                        activity_level_override=activity_level_override,
                    )
                elif self.entity_description.value_key == "target_daily_protein":
                    summary = get_protein_target_status(
                        food_entry_repository=_data(self.hass)["food_entry_repository"],
                        body_profile_repository=_data(self.hass)["body_profile_repository"],
                        body_measurement_repository=_data(self.hass)["body_measurement_repository"],
                        user_repository=_data(self.hass)["user_repository"],
                        profile_id=self._profile_id,
                        date=today,
                        activity_level_override=activity_level_override,
                    )
                else:
                    summary = get_fat_target_status(
                        food_entry_repository=_data(self.hass)["food_entry_repository"],
                        body_profile_repository=_data(self.hass)["body_profile_repository"],
                        body_measurement_repository=_data(self.hass)["body_measurement_repository"],
                        user_repository=_data(self.hass)["user_repository"],
                        profile_id=self._profile_id,
                        date=today,
                        activity_level_override=activity_level_override,
                    )

                extra_state_attributes = {
                    "profile_id": self._profile_id,
                    "date": today,
                    "summary_group": self.entity_description.summary_group,
                    "consumed": summary["consumed"],
                    "target_min": summary["target_min"],
                    "target_recommended": summary["target_recommended"],
                    "target_max": summary["target_max"],
                    "remaining_to_min": summary["remaining_to_min"],
                    "remaining_to_max": summary["remaining_to_max"],
                    "over_amount": summary["over_amount"],
                    "display_text": summary["display_text"],
                }
                self._attr_native_value = summary["status"]
                self._attr_extra_state_attributes = extra_state_attributes
                self._attr_available = True
                return
            else:
                summary = get_body_targets(
                    repository=_data(self.hass)["body_profile_repository"],
                    measurement_repository=_data(self.hass)["body_measurement_repository"],
                    user_repository=_data(self.hass)["user_repository"],
                    profile_id=self._profile_id,
                    activity_level_override=_resolve_fit_activity_level(
                        _data(self.hass),
                        self._profile_id,
                    ),
                ).to_dict()
                target_range = summary["target_ranges"][
                    self.entity_description.value_key
                ]
                extra_state_attributes = {
                    "profile_id": self._profile_id,
                    "summary_group": self.entity_description.summary_group,
                    "target_min": target_range["minimum"],
                    "target_recommended": target_range["recommended"],
                    "target_max": target_range["maximum"],
                    "target_range_text": (
                        None
                        if target_range["minimum"] is None
                        or target_range["maximum"] is None
                        else f'{target_range["minimum"]} - {target_range["maximum"]}'
                    ),
                    "missing_fields": target_range["missing_fields"],
                    "unsupported_reasons": target_range["unsupported_reasons"],
                    "required_fields": target_range["required_fields"],
                    "calculation_method": target_range["method"],
                    "formula": target_range["formula"],
                    "inputs": target_range["inputs"],
                }
                self._attr_native_value = target_range[
                    self.entity_description.range_value_key
                ]
                self._attr_extra_state_attributes = extra_state_attributes
                self._attr_available = True
                return
        except (
            BrizelBodyGoalValidationError,
            BrizelBodyMeasurementValidationError,
            BrizelBodyProfileValidationError,
            BrizelFoodEntryValidationError,
            BrizelUserNotFoundError,
            BrizelUserValidationError,
        ):
            self._attr_available = False
            self._attr_native_value = None
            return

        self._attr_available = True
        self._attr_native_value = summary[self.entity_description.value_key]
        self._attr_extra_state_attributes = extra_state_attributes
