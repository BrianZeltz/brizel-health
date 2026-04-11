"""Queries for user-facing daily nutrition overview data."""

from __future__ import annotations

from ...core.interfaces.user_repository import UserRepository
from ...domains.body.interfaces.body_profile_repository import BodyProfileRepository
from ...domains.nutrition.interfaces.food_entry_repository import FoodEntryRepository
from ..body.body_target_status_queries import (
    get_fat_target_status,
    get_kcal_target_status,
    get_protein_target_status,
)


def get_daily_overview(
    *,
    food_entry_repository: FoodEntryRepository,
    body_profile_repository: BodyProfileRepository,
    user_repository: UserRepository,
    profile_id: str,
    date: str,
) -> dict[str, object]:
    """Return interpreted daily overview data for one profile and day."""
    kcal = get_kcal_target_status(
        food_entry_repository=food_entry_repository,
        body_profile_repository=body_profile_repository,
        user_repository=user_repository,
        profile_id=profile_id,
        date=date,
    )
    protein = get_protein_target_status(
        food_entry_repository=food_entry_repository,
        body_profile_repository=body_profile_repository,
        user_repository=user_repository,
        profile_id=profile_id,
        date=date,
    )
    fat = get_fat_target_status(
        food_entry_repository=food_entry_repository,
        body_profile_repository=body_profile_repository,
        user_repository=user_repository,
        profile_id=profile_id,
        date=date,
    )

    consumed_values = (
        kcal.get("consumed"),
        protein.get("consumed"),
        fat.get("consumed"),
    )
    has_data = any(
        value is not None and float(value) > 0 for value in consumed_values
    )

    return {
        "date": date,
        "has_data": has_data,
        "kcal": kcal,
        "protein": protein,
        "fat": fat,
    }
