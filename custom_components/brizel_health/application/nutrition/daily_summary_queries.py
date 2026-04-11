"""Queries for daily nutrition summaries."""

from __future__ import annotations

from ...core.interfaces.user_repository import UserRepository
from ...domains.nutrition.interfaces.food_entry_repository import FoodEntryRepository
from ...domains.nutrition.services.daily_summary import calculate_daily_summary
from .food_entry_queries import get_food_entries_for_profile_date


def get_daily_summary(
    repository: FoodEntryRepository,
    user_repository: UserRepository,
    profile_id: str,
    date: str,
) -> dict[str, float]:
    """Return the daily nutrition summary for a profile and date."""
    food_entries = get_food_entries_for_profile_date(
        repository=repository,
        user_repository=user_repository,
        profile_id=profile_id,
        date=date,
    )
    return calculate_daily_summary(food_entries)
