"""Central registry for supported body measurement types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import BrizelBodyMeasurementValidationError

MEASUREMENT_TYPE_WEIGHT = "weight"
MEASUREMENT_TYPE_WAIST = "waist"
MEASUREMENT_TYPE_ABDOMEN = "abdomen"
MEASUREMENT_TYPE_HIP = "hip"
MEASUREMENT_TYPE_CHEST = "chest"
MEASUREMENT_TYPE_UPPER_ARM = "upper_arm"
MEASUREMENT_TYPE_FOREARM = "forearm"
MEASUREMENT_TYPE_THIGH = "thigh"
MEASUREMENT_TYPE_CALF = "calf"
MEASUREMENT_TYPE_NECK = "neck"

CANONICAL_UNIT_KG = "kg"
CANONICAL_UNIT_CM = "cm"
DISPLAY_UNIT_LB = "lb"
DISPLAY_UNIT_IN = "in"


@dataclass(frozen=True, slots=True)
class BodyMeasurementTypeDefinition:
    """Static metadata for one supported body measurement type."""

    key: str
    label: str
    canonical_unit: str
    metric_display_unit: str
    imperial_display_unit: str
    sort_order: int
    prominent: bool = False
    description: str | None = None
    guidance: str | None = None
    minimum_canonical_value: float | None = None
    maximum_canonical_value: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize one measurement type for API/UI use."""
        return {
            "key": self.key,
            "label": self.label,
            "canonical_unit": self.canonical_unit,
            "metric_display_unit": self.metric_display_unit,
            "imperial_display_unit": self.imperial_display_unit,
            "sort_order": self.sort_order,
            "prominent": self.prominent,
            "description": self.description,
            "guidance": self.guidance,
            "minimum_canonical_value": self.minimum_canonical_value,
            "maximum_canonical_value": self.maximum_canonical_value,
        }


_MEASUREMENT_TYPE_DEFINITIONS = (
    BodyMeasurementTypeDefinition(
        key=MEASUREMENT_TYPE_WEIGHT,
        label="Weight",
        canonical_unit=CANONICAL_UNIT_KG,
        metric_display_unit=CANONICAL_UNIT_KG,
        imperial_display_unit=DISPLAY_UNIT_LB,
        sort_order=10,
        prominent=True,
        description="Body weight stored canonically in kilograms.",
        guidance="Measure under comparable conditions for meaningful trends.",
        minimum_canonical_value=10.0,
        maximum_canonical_value=400.0,
    ),
    BodyMeasurementTypeDefinition(
        key=MEASUREMENT_TYPE_WAIST,
        label="Waist",
        canonical_unit=CANONICAL_UNIT_CM,
        metric_display_unit=CANONICAL_UNIT_CM,
        imperial_display_unit=DISPLAY_UNIT_IN,
        sort_order=20,
        prominent=True,
        description="Waist circumference.",
        guidance="Measure around the natural waistline without pulling the tape tight.",
        minimum_canonical_value=5.0,
        maximum_canonical_value=400.0,
    ),
    BodyMeasurementTypeDefinition(
        key=MEASUREMENT_TYPE_ABDOMEN,
        label="Abdomen",
        canonical_unit=CANONICAL_UNIT_CM,
        metric_display_unit=CANONICAL_UNIT_CM,
        imperial_display_unit=DISPLAY_UNIT_IN,
        sort_order=30,
        prominent=True,
        description="Abdomen circumference.",
        guidance="Measure at the fullest point of the abdomen.",
        minimum_canonical_value=5.0,
        maximum_canonical_value=400.0,
    ),
    BodyMeasurementTypeDefinition(
        key=MEASUREMENT_TYPE_HIP,
        label="Hip",
        canonical_unit=CANONICAL_UNIT_CM,
        metric_display_unit=CANONICAL_UNIT_CM,
        imperial_display_unit=DISPLAY_UNIT_IN,
        sort_order=40,
        prominent=True,
        description="Hip circumference.",
        guidance="Measure around the widest part of the hips.",
        minimum_canonical_value=5.0,
        maximum_canonical_value=400.0,
    ),
    BodyMeasurementTypeDefinition(
        key=MEASUREMENT_TYPE_CHEST,
        label="Chest",
        canonical_unit=CANONICAL_UNIT_CM,
        metric_display_unit=CANONICAL_UNIT_CM,
        imperial_display_unit=DISPLAY_UNIT_IN,
        sort_order=50,
        prominent=True,
        description="Chest circumference.",
        guidance="Measure around the fullest part of the chest with relaxed posture.",
        minimum_canonical_value=5.0,
        maximum_canonical_value=400.0,
    ),
    BodyMeasurementTypeDefinition(
        key=MEASUREMENT_TYPE_UPPER_ARM,
        label="Upper arm",
        canonical_unit=CANONICAL_UNIT_CM,
        metric_display_unit=CANONICAL_UNIT_CM,
        imperial_display_unit=DISPLAY_UNIT_IN,
        sort_order=60,
        description="Upper-arm circumference.",
        guidance="Measure around the midpoint of the relaxed upper arm.",
        minimum_canonical_value=5.0,
        maximum_canonical_value=200.0,
    ),
    BodyMeasurementTypeDefinition(
        key=MEASUREMENT_TYPE_FOREARM,
        label="Forearm",
        canonical_unit=CANONICAL_UNIT_CM,
        metric_display_unit=CANONICAL_UNIT_CM,
        imperial_display_unit=DISPLAY_UNIT_IN,
        sort_order=70,
        description="Forearm circumference.",
        guidance="Measure around the widest part of the forearm.",
        minimum_canonical_value=5.0,
        maximum_canonical_value=200.0,
    ),
    BodyMeasurementTypeDefinition(
        key=MEASUREMENT_TYPE_THIGH,
        label="Thigh",
        canonical_unit=CANONICAL_UNIT_CM,
        metric_display_unit=CANONICAL_UNIT_CM,
        imperial_display_unit=DISPLAY_UNIT_IN,
        sort_order=80,
        description="Thigh circumference.",
        guidance="Measure around the upper thigh at a consistent point.",
        minimum_canonical_value=5.0,
        maximum_canonical_value=300.0,
    ),
    BodyMeasurementTypeDefinition(
        key=MEASUREMENT_TYPE_CALF,
        label="Calf",
        canonical_unit=CANONICAL_UNIT_CM,
        metric_display_unit=CANONICAL_UNIT_CM,
        imperial_display_unit=DISPLAY_UNIT_IN,
        sort_order=90,
        description="Calf circumference.",
        guidance="Measure around the widest part of the calf.",
        minimum_canonical_value=5.0,
        maximum_canonical_value=200.0,
    ),
    BodyMeasurementTypeDefinition(
        key=MEASUREMENT_TYPE_NECK,
        label="Neck",
        canonical_unit=CANONICAL_UNIT_CM,
        metric_display_unit=CANONICAL_UNIT_CM,
        imperial_display_unit=DISPLAY_UNIT_IN,
        sort_order=100,
        description="Neck circumference.",
        guidance="Measure around the neck just below the larynx.",
        minimum_canonical_value=5.0,
        maximum_canonical_value=200.0,
    ),
)

BODY_MEASUREMENT_TYPES_BY_KEY = {
    definition.key: definition for definition in _MEASUREMENT_TYPE_DEFINITIONS
}


def get_body_measurement_type(key: str) -> BodyMeasurementTypeDefinition:
    """Return one supported measurement-type definition."""
    normalized_key = str(key).strip().lower()
    definition = BODY_MEASUREMENT_TYPES_BY_KEY.get(normalized_key)
    if definition is None:
        raise BrizelBodyMeasurementValidationError(
            f"measurement_type must be one of {sorted(BODY_MEASUREMENT_TYPES_BY_KEY)}."
        )
    return definition


def get_body_measurement_types() -> tuple[BodyMeasurementTypeDefinition, ...]:
    """Return all supported measurement types in stable display order."""
    return tuple(
        sorted(
            BODY_MEASUREMENT_TYPES_BY_KEY.values(),
            key=lambda definition: definition.sort_order,
        )
    )
