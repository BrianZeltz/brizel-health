"""Target calculations for the Body module."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from ..models.body_profile import (
    ACTIVITY_LEVEL_ACTIVE,
    ACTIVITY_LEVEL_LIGHT,
    ACTIVITY_LEVEL_MODERATE,
    ACTIVITY_LEVEL_SEDENTARY,
    ACTIVITY_LEVEL_VERY_ACTIVE,
    SEX_MALE,
    BodyProfile,
)
from ..models.body_target_range import BodyTargetRange
from ..models.body_targets import BodyTargets

TARGET_DAILY_KCAL = "target_daily_kcal"
TARGET_DAILY_PROTEIN = "target_daily_protein"
TARGET_DAILY_FAT = "target_daily_fat"
KCAL_RANGE_RATIO = 0.05

ACTIVITY_MULTIPLIERS = {
    ACTIVITY_LEVEL_SEDENTARY: 1.2,
    ACTIVITY_LEVEL_LIGHT: 1.375,
    ACTIVITY_LEVEL_MODERATE: 1.55,
    ACTIVITY_LEVEL_ACTIVE: 1.725,
    ACTIVITY_LEVEL_VERY_ACTIVE: 1.9,
}

PROTEIN_RANGE_FACTORS = {
    ACTIVITY_LEVEL_SEDENTARY: (1.0, 1.1, 1.2),
    ACTIVITY_LEVEL_LIGHT: (1.2, 1.3, 1.4),
    ACTIVITY_LEVEL_MODERATE: (1.4, 1.5, 1.6),
    ACTIVITY_LEVEL_ACTIVE: (1.6, 1.75, 1.9),
    ACTIVITY_LEVEL_VERY_ACTIVE: (1.8, 2.0, 2.2),
}

FAT_RANGE_FACTORS = (0.8, 0.9, 1.0)
UNSUPPORTED_REASON_ADULT_ONLY_KCAL = "adult_only_kcal_estimate"
METHOD_MIFFLIN_ST_JEOR_MAINTENANCE = "mifflin_st_jeor_maintenance"
METHOD_WEIGHT_BASED_ACTIVITY_FACTOR = "weight_based_activity_factor"
METHOD_WEIGHT_BASED_FIXED_FACTOR = "weight_based_fixed_factor"

KCAL_REQUIRED_FIELDS = (
    "birth_date",
    "sex",
    "height_cm",
    "weight_kg",
    "activity_level",
)
PROTEIN_REQUIRED_FIELDS = (
    "weight_kg",
    "activity_level",
)
FAT_REQUIRED_FIELDS = ("weight_kg",)


def _round_macro_target(value: float) -> float:
    """Round a macro target to one decimal place."""
    return round(value, 1)


def _round_kcal_target(value: float) -> int:
    """Round a calorie target to a whole-kcal value."""
    return int(round(value))


def _missing_fields(
    body_profile: BodyProfile,
    required_fields: tuple[str, ...],
) -> tuple[str, ...]:
    """Return the missing required fields for one target."""
    return tuple(
        field_name
        for field_name in required_fields
        if getattr(body_profile, field_name) is None
    )


def _age_years_from_birth_date(birth_date: str | None) -> int | None:
    """Derive full years from the Body-owned birth date."""
    if birth_date is None:
        return None
    try:
        normalized = birth_date.strip()
        if "T" in normalized or " " in normalized:
            parsed = datetime.fromisoformat(
                normalized.replace("Z", "+00:00")
            ).date()
        else:
            parsed = date.fromisoformat(normalized)
    except ValueError:
        return None

    today = date.today()
    years = today.year - parsed.year - (
        (today.month, today.day) < (parsed.month, parsed.day)
    )
    return years if years >= 0 else None


def _target_age_years(body_profile: BodyProfile) -> int | None:
    """Return target-calculation age, preferring native birth_date over legacy age."""
    return _age_years_from_birth_date(body_profile.birth_date) or body_profile.age_years


def _missing_kcal_fields(
    body_profile: BodyProfile,
    age_years: int | None,
) -> tuple[str, ...]:
    """Return kcal missing fields while allowing legacy age_years fallback."""
    missing = []
    if age_years is None:
        missing.append("birth_date")
    for field_name in ("sex", "height_cm", "weight_kg", "activity_level"):
        if getattr(body_profile, field_name) is None:
            missing.append(field_name)
    return tuple(missing)


def _target_range(
    *,
    minimum: float | int | None,
    recommended: float | int | None,
    maximum: float | int | None,
    method: str,
    formula: str,
    required_fields: tuple[str, ...],
    missing_fields: tuple[str, ...],
    unsupported_reasons: tuple[str, ...] = (),
    inputs: dict[str, Any] | None = None,
) -> BodyTargetRange:
    """Build a transparent target-range object."""
    return BodyTargetRange(
        minimum=minimum,
        recommended=recommended,
        maximum=maximum,
        method=method,
        formula=formula,
        required_fields=required_fields,
        missing_fields=missing_fields,
        unsupported_reasons=unsupported_reasons,
        inputs=inputs or {},
    )


def calculate_body_targets(body_profile: BodyProfile) -> BodyTargets:
    """Calculate conservative daily target ranges from the current body profile."""
    target_daily_kcal: int | None = None
    target_daily_protein: float | None = None
    target_daily_fat: float | None = None

    age_years = _target_age_years(body_profile)
    kcal_missing_fields = _missing_kcal_fields(body_profile, age_years)
    protein_missing_fields = _missing_fields(body_profile, PROTEIN_REQUIRED_FIELDS)
    fat_missing_fields = _missing_fields(body_profile, FAT_REQUIRED_FIELDS)
    kcal_unsupported_reasons: tuple[str, ...] = ()

    fat_range_min: float | None = None
    fat_range_recommended: float | None = None
    fat_range_max: float | None = None
    if not fat_missing_fields:
        fat_range_min = _round_macro_target(
            body_profile.weight_kg * FAT_RANGE_FACTORS[0]
        )
        fat_range_recommended = _round_macro_target(
            body_profile.weight_kg * FAT_RANGE_FACTORS[1]
        )
        fat_range_max = _round_macro_target(
            body_profile.weight_kg * FAT_RANGE_FACTORS[2]
        )
        target_daily_fat = fat_range_recommended
    fat_range = _target_range(
        minimum=fat_range_min,
        recommended=fat_range_recommended,
        maximum=fat_range_max,
        method=METHOD_WEIGHT_BASED_FIXED_FACTOR,
        formula=(
            "minimum=round(weight_kg * 0.8, 1), "
            "recommended=round(weight_kg * 0.9, 1), "
            "maximum=round(weight_kg * 1.0, 1)"
        ),
        required_fields=FAT_REQUIRED_FIELDS,
        missing_fields=fat_missing_fields,
        inputs={
            "weight_kg": body_profile.weight_kg,
            "fat_factors_g_per_kg": list(FAT_RANGE_FACTORS),
        },
    )

    protein_range_min: float | None = None
    protein_range_recommended: float | None = None
    protein_range_max: float | None = None
    if not protein_missing_fields:
        protein_factors = PROTEIN_RANGE_FACTORS[body_profile.activity_level]
        protein_range_min = _round_macro_target(
            body_profile.weight_kg * protein_factors[0]
        )
        protein_range_recommended = _round_macro_target(
            body_profile.weight_kg * protein_factors[1]
        )
        protein_range_max = _round_macro_target(
            body_profile.weight_kg * protein_factors[2]
        )
        target_daily_protein = protein_range_recommended
    protein_range = _target_range(
        minimum=protein_range_min,
        recommended=protein_range_recommended,
        maximum=protein_range_max,
        method=METHOD_WEIGHT_BASED_ACTIVITY_FACTOR,
        formula=(
            "minimum=round(weight_kg * protein_min_factor_g_per_kg, 1), "
            "recommended=round(weight_kg * protein_recommended_factor_g_per_kg, 1), "
            "maximum=round(weight_kg * protein_max_factor_g_per_kg, 1)"
        ),
        required_fields=PROTEIN_REQUIRED_FIELDS,
        missing_fields=protein_missing_fields,
        inputs={
            "weight_kg": body_profile.weight_kg,
            "activity_level": body_profile.activity_level,
            "protein_factors_g_per_kg": (
                None
                if body_profile.activity_level is None
                else list(PROTEIN_RANGE_FACTORS[body_profile.activity_level])
            ),
        },
    )

    kcal_range_min: int | None = None
    kcal_range_recommended: int | None = None
    kcal_range_max: int | None = None
    if age_years is not None and age_years < 18:
        kcal_unsupported_reasons = (UNSUPPORTED_REASON_ADULT_ONLY_KCAL,)
    elif not kcal_missing_fields:
        sex_adjustment = 5 if body_profile.sex == SEX_MALE else -161
        bmr = (
            10 * body_profile.weight_kg
            + 6.25 * body_profile.height_cm
            - 5 * age_years
            + sex_adjustment
        )
        kcal_center = bmr * ACTIVITY_MULTIPLIERS[body_profile.activity_level]
        kcal_range_min = _round_kcal_target(kcal_center * (1 - KCAL_RANGE_RATIO))
        kcal_range_recommended = _round_kcal_target(kcal_center)
        kcal_range_max = _round_kcal_target(kcal_center * (1 + KCAL_RANGE_RATIO))
        target_daily_kcal = kcal_range_recommended
        kcal_inputs = {
            "birth_date": body_profile.birth_date,
            "age_years": age_years,
            "sex": body_profile.sex,
            "height_cm": body_profile.height_cm,
            "weight_kg": body_profile.weight_kg,
            "activity_level": body_profile.activity_level,
            "sex_adjustment": sex_adjustment,
            "activity_multiplier": ACTIVITY_MULTIPLIERS[body_profile.activity_level],
            "bmr_kcal": round(bmr, 2),
            "range_ratio": KCAL_RANGE_RATIO,
            "maintenance_center_kcal": round(kcal_center, 2),
        }
    else:
        kcal_inputs = {
            "birth_date": body_profile.birth_date,
            "age_years": age_years,
            "sex": body_profile.sex,
            "height_cm": body_profile.height_cm,
            "weight_kg": body_profile.weight_kg,
            "activity_level": body_profile.activity_level,
            "sex_adjustment": None,
            "activity_multiplier": (
                None
                if body_profile.activity_level is None
                else ACTIVITY_MULTIPLIERS[body_profile.activity_level]
            ),
            "bmr_kcal": None,
            "range_ratio": KCAL_RANGE_RATIO,
            "maintenance_center_kcal": None,
        }

    if age_years is not None and age_years < 18:
        kcal_inputs = {
            "birth_date": body_profile.birth_date,
            "age_years": age_years,
            "sex": body_profile.sex,
            "height_cm": body_profile.height_cm,
            "weight_kg": body_profile.weight_kg,
            "activity_level": body_profile.activity_level,
            "sex_adjustment": None,
            "activity_multiplier": (
                None
                if body_profile.activity_level is None
                else ACTIVITY_MULTIPLIERS[body_profile.activity_level]
            ),
            "bmr_kcal": None,
            "range_ratio": KCAL_RANGE_RATIO,
            "maintenance_center_kcal": None,
        }

    kcal_range = _target_range(
        minimum=kcal_range_min,
        recommended=kcal_range_recommended,
        maximum=kcal_range_max,
        method=METHOD_MIFFLIN_ST_JEOR_MAINTENANCE,
        formula=(
            "center=round(((10 * weight_kg) + (6.25 * height_cm) - (5 * age_years) + sex_adjustment) "
            "* activity_multiplier), "
            "minimum=round(center * 0.95), "
            "maximum=round(center * 1.05)"
        ),
        required_fields=KCAL_REQUIRED_FIELDS,
        missing_fields=kcal_missing_fields,
        unsupported_reasons=kcal_unsupported_reasons,
        inputs=kcal_inputs,
    )

    target_ranges = {
        TARGET_DAILY_KCAL: kcal_range,
        TARGET_DAILY_PROTEIN: protein_range,
        TARGET_DAILY_FAT: fat_range,
    }
    missing_fields = tuple(
        sorted(
            {
                *kcal_missing_fields,
                *protein_missing_fields,
                *fat_missing_fields,
            }
        )
    )
    unsupported_reasons = tuple(sorted(kcal_unsupported_reasons))

    return BodyTargets(
        profile_id=body_profile.profile_id,
        target_daily_kcal=target_daily_kcal,
        target_daily_protein=target_daily_protein,
        target_daily_fat=target_daily_fat,
        missing_fields=missing_fields,
        unsupported_reasons=unsupported_reasons,
        target_ranges=target_ranges,
    )
