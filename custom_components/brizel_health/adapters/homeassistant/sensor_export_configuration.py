"""Configuration helpers for optional Brizel Home Assistant sensor exports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping

SENSOR_EXPORTS_ENABLED_OPTION = "sensor_exports_enabled"
SENSOR_EXPORT_GROUPS_OPTION = "sensor_export_groups"

SENSOR_EXPORT_GROUP_NUTRITION = "nutrition"
SENSOR_EXPORT_GROUP_HYDRATION = "hydration"
SENSOR_EXPORT_GROUP_BODY = "body"
SENSOR_EXPORT_GROUP_STEPS = "steps"
SENSOR_EXPORT_GROUP_TARGETS = "targets"

SENSOR_EXPORT_GROUPS = (
    SENSOR_EXPORT_GROUP_NUTRITION,
    SENSOR_EXPORT_GROUP_HYDRATION,
    SENSOR_EXPORT_GROUP_BODY,
    SENSOR_EXPORT_GROUP_STEPS,
    SENSOR_EXPORT_GROUP_TARGETS,
)

SENSOR_EXPORT_GROUP_FORM_FIELDS = {
    SENSOR_EXPORT_GROUP_NUTRITION: "sensor_export_group_nutrition",
    SENSOR_EXPORT_GROUP_HYDRATION: "sensor_export_group_hydration",
    SENSOR_EXPORT_GROUP_BODY: "sensor_export_group_body",
    SENSOR_EXPORT_GROUP_STEPS: "sensor_export_group_steps",
    SENSOR_EXPORT_GROUP_TARGETS: "sensor_export_group_targets",
}

_SUMMARY_GROUP_TO_EXPORT_GROUP = {
    "nutrition": SENSOR_EXPORT_GROUP_NUTRITION,
    "hydration": SENSOR_EXPORT_GROUP_HYDRATION,
    "body_profile": SENSOR_EXPORT_GROUP_BODY,
    "body_measurements": SENSOR_EXPORT_GROUP_BODY,
    "body_progress": SENSOR_EXPORT_GROUP_BODY,
    "fit_steps": SENSOR_EXPORT_GROUP_STEPS,
    "body_targets": SENSOR_EXPORT_GROUP_TARGETS,
    "body_target_status": SENSOR_EXPORT_GROUP_TARGETS,
}


@dataclass(frozen=True, slots=True)
class SensorExportSettings:
    """Normalized sensor export settings for one config entry."""

    enabled: bool
    groups: dict[str, bool]

    def is_group_enabled(self, group: str | None) -> bool:
        """Return whether one export group should currently create entities."""
        if group is None:
            return False
        return self.enabled and bool(self.groups.get(group, False))


def get_default_sensor_export_options() -> dict[str, Any]:
    """Return the conservative default sensor export options payload."""
    return {
        SENSOR_EXPORTS_ENABLED_OPTION: False,
        SENSOR_EXPORT_GROUPS_OPTION: {
            group: False for group in SENSOR_EXPORT_GROUPS
        },
    }


def get_sensor_export_settings(
    options: Mapping[str, Any] | None = None,
) -> SensorExportSettings:
    """Normalize one config-entry options mapping into sensor export settings."""
    defaults = get_default_sensor_export_options()
    groups = dict(defaults[SENSOR_EXPORT_GROUPS_OPTION])

    if isinstance(options, Mapping):
        raw_groups = options.get(SENSOR_EXPORT_GROUPS_OPTION)
        if isinstance(raw_groups, Mapping):
            for group in SENSOR_EXPORT_GROUPS:
                if group in raw_groups:
                    groups[group] = bool(raw_groups[group])
        enabled = bool(options.get(SENSOR_EXPORTS_ENABLED_OPTION, False))
    else:
        enabled = False

    return SensorExportSettings(enabled=enabled, groups=groups)


def sensor_export_form_suggested_values(
    options: Mapping[str, Any] | None = None,
) -> dict[str, bool]:
    """Return flat form values for the HA options flow."""
    settings = get_sensor_export_settings(options)
    values = {SENSOR_EXPORTS_ENABLED_OPTION: settings.enabled}
    for group, field_name in SENSOR_EXPORT_GROUP_FORM_FIELDS.items():
        values[field_name] = bool(settings.groups.get(group, False))
    return values


def build_sensor_export_options(
    *,
    enabled: bool,
    form_values: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one persisted config-entry option patch for sensor exports."""
    groups = {
        group: False for group in SENSOR_EXPORT_GROUPS
    }
    if isinstance(form_values, Mapping):
        for group, field_name in SENSOR_EXPORT_GROUP_FORM_FIELDS.items():
            groups[group] = bool(form_values.get(field_name, False))

    return {
        SENSOR_EXPORTS_ENABLED_OPTION: bool(enabled),
        SENSOR_EXPORT_GROUPS_OPTION: groups,
    }


def resolve_sensor_export_group(summary_group: str) -> str | None:
    """Map one internal sensor summary group into the public export group model."""
    return _SUMMARY_GROUP_TO_EXPORT_GROUP.get(summary_group)
