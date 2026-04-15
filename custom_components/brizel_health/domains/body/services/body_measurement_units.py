"""Canonical metric storage and display/input unit conversions for Body."""

from __future__ import annotations

from ....core.users.brizel_user import (
    BrizelUser,
    PREFERRED_REGION_USA,
    PREFERRED_UNITS_IMPERIAL,
    PREFERRED_UNITS_METRIC,
)
from ..errors import BrizelBodyMeasurementValidationError
from ..models.body_measurement_type import (
    CANONICAL_UNIT_CM,
    CANONICAL_UNIT_KG,
    DISPLAY_UNIT_IN,
    DISPLAY_UNIT_LB,
    get_body_measurement_type,
)

BODY_UNIT_SYSTEM_METRIC = PREFERRED_UNITS_METRIC
BODY_UNIT_SYSTEM_IMPERIAL = PREFERRED_UNITS_IMPERIAL

_WEIGHT_UNIT_ALIASES = {
    CANONICAL_UNIT_KG: CANONICAL_UNIT_KG,
    "kgs": CANONICAL_UNIT_KG,
    "kilogram": CANONICAL_UNIT_KG,
    "kilograms": CANONICAL_UNIT_KG,
    DISPLAY_UNIT_LB: DISPLAY_UNIT_LB,
    "lbs": DISPLAY_UNIT_LB,
    "pound": DISPLAY_UNIT_LB,
    "pounds": DISPLAY_UNIT_LB,
}
_LENGTH_UNIT_ALIASES = {
    CANONICAL_UNIT_CM: CANONICAL_UNIT_CM,
    "centimeter": CANONICAL_UNIT_CM,
    "centimeters": CANONICAL_UNIT_CM,
    DISPLAY_UNIT_IN: DISPLAY_UNIT_IN,
    "inch": DISPLAY_UNIT_IN,
    "inches": DISPLAY_UNIT_IN,
}


def resolve_body_unit_system(profile: BrizelUser | None) -> str:
    """Resolve the effective body unit system from existing profile settings."""
    if profile is not None and profile.preferred_units in {
        PREFERRED_UNITS_METRIC,
        PREFERRED_UNITS_IMPERIAL,
    }:
        return profile.preferred_units
    if profile is not None and profile.preferred_region == PREFERRED_REGION_USA:
        return PREFERRED_UNITS_IMPERIAL
    return PREFERRED_UNITS_METRIC


def kilograms_to_pounds(value_kg: float | int) -> float:
    return float(value_kg) * 2.2046226218


def pounds_to_kilograms(value_lb: float | int) -> float:
    return float(value_lb) / 2.2046226218


def centimeters_to_inches(value_cm: float | int) -> float:
    return float(value_cm) / 2.54


def inches_to_centimeters(value_in: float | int) -> float:
    return float(value_in) * 2.54


def get_measurement_display_unit(
    measurement_type: str,
    unit_system: str,
) -> str:
    """Return the display/input unit for one measurement type and unit system."""
    definition = get_body_measurement_type(measurement_type)
    if unit_system == BODY_UNIT_SYSTEM_IMPERIAL:
        return definition.imperial_display_unit
    return definition.metric_display_unit


def _normalize_input_unit(measurement_type: str, unit: str | None) -> str:
    definition = get_body_measurement_type(measurement_type)
    if unit is None:
        return definition.canonical_unit

    normalized = str(unit).strip().lower()
    if not normalized:
        return definition.canonical_unit

    aliases = (
        _WEIGHT_UNIT_ALIASES
        if definition.canonical_unit == CANONICAL_UNIT_KG
        else _LENGTH_UNIT_ALIASES
    )
    normalized_unit = aliases.get(normalized)
    if normalized_unit is None:
        raise BrizelBodyMeasurementValidationError(
            f"unit '{unit}' is not supported for measurement_type '{definition.key}'."
        )
    return normalized_unit


def convert_input_to_canonical(
    *,
    measurement_type: str,
    value: float | int,
    unit: str | None,
) -> float:
    """Convert one user-entered value to the canonical metric storage unit."""
    definition = get_body_measurement_type(measurement_type)
    normalized_unit = _normalize_input_unit(measurement_type, unit)
    numeric_value = float(value)

    if definition.canonical_unit == CANONICAL_UNIT_KG:
        if normalized_unit == DISPLAY_UNIT_LB:
            return round(pounds_to_kilograms(numeric_value), 4)
        return round(numeric_value, 4)

    if normalized_unit == DISPLAY_UNIT_IN:
        return round(inches_to_centimeters(numeric_value), 4)
    return round(numeric_value, 4)


def convert_canonical_to_display(
    *,
    measurement_type: str,
    canonical_value: float | int | None,
    unit_system: str,
) -> float | None:
    """Convert one canonical metric value to the requested display unit."""
    if canonical_value is None:
        return None

    definition = get_body_measurement_type(measurement_type)
    numeric_value = float(canonical_value)
    if definition.canonical_unit == CANONICAL_UNIT_KG:
        if unit_system == BODY_UNIT_SYSTEM_IMPERIAL:
            return round(kilograms_to_pounds(numeric_value), 2)
        return round(numeric_value, 2)

    if unit_system == BODY_UNIT_SYSTEM_IMPERIAL:
        return round(centimeters_to_inches(numeric_value), 2)
    return round(numeric_value, 2)
