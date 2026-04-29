"""Tests for Brizel Home Assistant sensor export configuration."""

from __future__ import annotations

from custom_components.brizel_health.adapters.homeassistant.sensor_export_configuration import (
    SENSOR_EXPORT_GROUP_BODY,
    SENSOR_EXPORT_GROUP_HYDRATION,
    SENSOR_EXPORT_GROUP_NUTRITION,
    SENSOR_EXPORT_GROUP_STEPS,
    SENSOR_EXPORT_GROUP_TARGETS,
    SENSOR_EXPORT_GROUPS,
    build_sensor_export_options,
    get_default_sensor_export_options,
    get_sensor_export_settings,
    resolve_sensor_export_group,
    sensor_export_form_suggested_values,
)


def test_default_sensor_export_options_disable_all_exports() -> None:
    """New entries should not export Brizel sensors by default."""
    defaults = get_default_sensor_export_options()
    settings = get_sensor_export_settings(defaults)

    assert settings.enabled is False
    assert settings.groups == {group: False for group in SENSOR_EXPORT_GROUPS}
    assert sensor_export_form_suggested_values({}) == {
        "sensor_exports_enabled": False,
        "sensor_export_group_nutrition": False,
        "sensor_export_group_hydration": False,
        "sensor_export_group_body": False,
        "sensor_export_group_steps": False,
        "sensor_export_group_targets": False,
    }


def test_build_sensor_export_options_round_trips_group_preferences() -> None:
    """Persisted config-entry options should preserve export toggles."""
    options = build_sensor_export_options(
        enabled=True,
        form_values={
            "sensor_export_group_nutrition": True,
            "sensor_export_group_hydration": False,
            "sensor_export_group_body": True,
            "sensor_export_group_steps": True,
            "sensor_export_group_targets": False,
        },
    )

    settings = get_sensor_export_settings(options)

    assert settings.enabled is True
    assert settings.groups == {
        SENSOR_EXPORT_GROUP_NUTRITION: True,
        SENSOR_EXPORT_GROUP_HYDRATION: False,
        SENSOR_EXPORT_GROUP_BODY: True,
        SENSOR_EXPORT_GROUP_STEPS: True,
        SENSOR_EXPORT_GROUP_TARGETS: False,
    }


def test_resolve_sensor_export_group_maps_summary_groups_conservatively() -> None:
    """Entity summary groups should map into the public export group model."""
    assert resolve_sensor_export_group("nutrition") == SENSOR_EXPORT_GROUP_NUTRITION
    assert resolve_sensor_export_group("hydration") == SENSOR_EXPORT_GROUP_HYDRATION
    assert resolve_sensor_export_group("body_profile") == SENSOR_EXPORT_GROUP_BODY
    assert resolve_sensor_export_group("body_measurements") == SENSOR_EXPORT_GROUP_BODY
    assert resolve_sensor_export_group("body_progress") == SENSOR_EXPORT_GROUP_BODY
    assert resolve_sensor_export_group("fit_steps") == SENSOR_EXPORT_GROUP_STEPS
    assert resolve_sensor_export_group("body_targets") == SENSOR_EXPORT_GROUP_TARGETS
    assert (
        resolve_sensor_export_group("body_target_status")
        == SENSOR_EXPORT_GROUP_TARGETS
    )
    assert resolve_sensor_export_group("unknown_group") is None
