"""Queries for interpreted daily target status values."""

from __future__ import annotations

from ...core.interfaces.user_repository import UserRepository
from ...domains.body.interfaces.body_measurement_repository import (
    BodyMeasurementRepository,
)
from ...domains.body.interfaces.body_profile_repository import BodyProfileRepository
from ...domains.body.services.targets import (
    TARGET_DAILY_FAT,
    TARGET_DAILY_KCAL,
    TARGET_DAILY_PROTEIN,
)
from ...domains.nutrition.interfaces.food_entry_repository import FoodEntryRepository
from ..nutrition.daily_summary_queries import get_daily_summary
from .body_target_queries import get_body_targets

STATUS_UNDER = "under"
STATUS_WITHIN = "within"
STATUS_OVER = "over"
STATUS_UNKNOWN = "unknown"

_TARGET_STATUS_CONFIG = {
    TARGET_DAILY_KCAL: {
        "summary_key": "kcal",
        "display_unit": "kcal",
    },
    TARGET_DAILY_PROTEIN: {
        "summary_key": "protein",
        "display_unit": "g protein",
    },
    TARGET_DAILY_FAT: {
        "summary_key": "fat",
        "display_unit": "g fat",
    },
}


def _round_status_value(value: float | int | None) -> float | int | None:
    """Round one status value conservatively for stable output."""
    if value is None:
        return None
    rounded = round(float(value), 2)
    if rounded.is_integer():
        return int(rounded)
    return rounded


def _format_status_value(value: float | int) -> str:
    """Format one numeric value for end-user display."""
    numeric = float(value)
    if numeric.is_integer():
        return str(int(numeric))
    if round(numeric, 1) == numeric:
        return f"{numeric:.1f}"
    return f"{numeric:.2f}"


def _build_display_text(
    *,
    status: str,
    display_unit: str,
    remaining_to_min: float | int | None,
    remaining_to_max: float | int | None,
    over_amount: float | int | None,
) -> str:
    """Return one user-friendly status sentence."""
    if status == STATUS_UNDER:
        return (
            f"You can eat {_format_status_value(remaining_to_min)}-"
            f"{_format_status_value(remaining_to_max)} {display_unit}"
        )
    if status == STATUS_WITHIN:
        return (
            "You are in range, "
            f"{_format_status_value(remaining_to_max)} {display_unit} left"
        )
    if status == STATUS_OVER:
        return (
            f"You are {_format_status_value(over_amount)} {display_unit} "
            "over your target"
        )
    return "Target range is not available yet."


def _get_target_status(
    *,
    food_entry_repository: FoodEntryRepository,
    body_profile_repository: BodyProfileRepository,
    body_measurement_repository: BodyMeasurementRepository | None = None,
    user_repository: UserRepository,
    profile_id: str,
    date: str,
    target_key: str,
    activity_level_override: str | None = None,
) -> dict[str, object]:
    """Return one interpreted target status for one profile and day."""
    config = _TARGET_STATUS_CONFIG[target_key]
    summary = get_daily_summary(
        repository=food_entry_repository,
        user_repository=user_repository,
        profile_id=profile_id,
        date=date,
    )
    targets = get_body_targets(
        repository=body_profile_repository,
        user_repository=user_repository,
        profile_id=profile_id,
        measurement_repository=body_measurement_repository,
        activity_level_override=activity_level_override,
    ).to_dict()
    target_range = targets["target_ranges"][target_key]

    consumed = _round_status_value(summary.get(config["summary_key"]))
    target_min = _round_status_value(target_range.get("minimum"))
    target_recommended = _round_status_value(target_range.get("recommended"))
    target_max = _round_status_value(target_range.get("maximum"))

    if (
        consumed is None
        or target_min is None
        or target_recommended is None
        or target_max is None
    ):
        return {
            "status": STATUS_UNKNOWN,
            "consumed": consumed,
            "target_min": target_min,
            "target_recommended": target_recommended,
            "target_max": target_max,
            "remaining_to_min": None,
            "remaining_to_max": None,
            "over_amount": None,
            "display_text": _build_display_text(
                status=STATUS_UNKNOWN,
                display_unit=config["display_unit"],
                remaining_to_min=None,
                remaining_to_max=None,
                over_amount=None,
            ),
        }

    if float(consumed) < float(target_min):
        remaining_to_min = _round_status_value(float(target_min) - float(consumed))
        remaining_to_max = _round_status_value(float(target_max) - float(consumed))
        status = STATUS_UNDER
        over_amount = None
    elif float(consumed) <= float(target_max):
        remaining_to_min = None
        remaining_to_max = _round_status_value(float(target_max) - float(consumed))
        status = STATUS_WITHIN
        over_amount = None
    else:
        remaining_to_min = None
        remaining_to_max = None
        over_amount = _round_status_value(float(consumed) - float(target_max))
        status = STATUS_OVER

    return {
        "status": status,
        "consumed": consumed,
        "target_min": target_min,
        "target_recommended": target_recommended,
        "target_max": target_max,
        "remaining_to_min": remaining_to_min,
        "remaining_to_max": remaining_to_max,
        "over_amount": over_amount,
        "display_text": _build_display_text(
            status=status,
            display_unit=config["display_unit"],
            remaining_to_min=remaining_to_min,
            remaining_to_max=remaining_to_max,
            over_amount=over_amount,
        ),
    }


def get_kcal_target_status(
    *,
    food_entry_repository: FoodEntryRepository,
    body_profile_repository: BodyProfileRepository,
    body_measurement_repository: BodyMeasurementRepository | None = None,
    user_repository: UserRepository,
    profile_id: str,
    date: str,
    activity_level_override: str | None = None,
) -> dict[str, object]:
    """Return interpreted kcal target status for one profile and day."""
    return _get_target_status(
        food_entry_repository=food_entry_repository,
        body_profile_repository=body_profile_repository,
        body_measurement_repository=body_measurement_repository,
        user_repository=user_repository,
        profile_id=profile_id,
        date=date,
        target_key=TARGET_DAILY_KCAL,
        activity_level_override=activity_level_override,
    )


def get_protein_target_status(
    *,
    food_entry_repository: FoodEntryRepository,
    body_profile_repository: BodyProfileRepository,
    body_measurement_repository: BodyMeasurementRepository | None = None,
    user_repository: UserRepository,
    profile_id: str,
    date: str,
    activity_level_override: str | None = None,
) -> dict[str, object]:
    """Return interpreted protein target status for one profile and day."""
    return _get_target_status(
        food_entry_repository=food_entry_repository,
        body_profile_repository=body_profile_repository,
        body_measurement_repository=body_measurement_repository,
        user_repository=user_repository,
        profile_id=profile_id,
        date=date,
        target_key=TARGET_DAILY_PROTEIN,
        activity_level_override=activity_level_override,
    )


def get_fat_target_status(
    *,
    food_entry_repository: FoodEntryRepository,
    body_profile_repository: BodyProfileRepository,
    body_measurement_repository: BodyMeasurementRepository | None = None,
    user_repository: UserRepository,
    profile_id: str,
    date: str,
    activity_level_override: str | None = None,
) -> dict[str, object]:
    """Return interpreted fat target status for one profile and day."""
    return _get_target_status(
        food_entry_repository=food_entry_repository,
        body_profile_repository=body_profile_repository,
        body_measurement_repository=body_measurement_repository,
        user_repository=user_repository,
        profile_id=profile_id,
        date=date,
        target_key=TARGET_DAILY_FAT,
        activity_level_override=activity_level_override,
    )
