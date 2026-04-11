"""Queries for hydration summaries built on top of food entries."""

from __future__ import annotations

from ...core.interfaces.user_repository import UserRepository
from ...domains.nutrition.interfaces.food_entry_repository import FoodEntryRepository
from ...domains.nutrition.interfaces.food_repository import FoodRepository
from ...domains.nutrition.models.food import Food
from ...domains.nutrition.models.food_entry import FoodEntry
from ...domains.nutrition.services.hydration import (
    HydrationBreakdownItem,
    HydrationReport,
    calculate_hydration_report,
)
from .food_entry_queries import get_food_entries_for_profile_date


def _load_daily_hydration_context(
    food_entry_repository: FoodEntryRepository,
    food_repository: FoodRepository,
    user_repository: UserRepository,
    profile_id: str,
    date: str,
) -> tuple[list[FoodEntry], dict[str, Food]]:
    """Load the food entries and foods needed for hydration calculations."""
    food_entries = get_food_entries_for_profile_date(
        repository=food_entry_repository,
        user_repository=user_repository,
        profile_id=profile_id,
        date=date,
    )
    foods_by_id = {food.food_id: food for food in food_repository.get_all_foods()}
    return food_entries, foods_by_id


def get_daily_hydration_report(
    food_entry_repository: FoodEntryRepository,
    food_repository: FoodRepository,
    user_repository: UserRepository,
    profile_id: str,
    date: str,
) -> HydrationReport:
    """Return hydration totals plus a food-level breakdown for a profile and date."""
    food_entries, foods_by_id = _load_daily_hydration_context(
        food_entry_repository=food_entry_repository,
        food_repository=food_repository,
        user_repository=user_repository,
        profile_id=profile_id,
        date=date,
    )

    return calculate_hydration_report(
        food_entries=food_entries,
        foods_by_id=foods_by_id,
    )


def get_daily_hydration_breakdown(
    food_entry_repository: FoodEntryRepository,
    food_repository: FoodRepository,
    user_repository: UserRepository,
    profile_id: str,
    date: str,
) -> list[HydrationBreakdownItem]:
    """Return only the food-level hydration breakdown for a profile and date."""
    report = get_daily_hydration_report(
        food_entry_repository=food_entry_repository,
        food_repository=food_repository,
        user_repository=user_repository,
        profile_id=profile_id,
        date=date,
    )
    return report["breakdown"]


def get_daily_hydration_summary(
    food_entry_repository: FoodEntryRepository,
    food_repository: FoodRepository,
    user_repository: UserRepository,
    profile_id: str,
    date: str,
) -> dict[str, float]:
    """Return the hydration totals for a profile and date."""
    report = get_daily_hydration_report(
        food_entry_repository=food_entry_repository,
        food_repository=food_repository,
        user_repository=user_repository,
        profile_id=profile_id,
        date=date,
    )
    return {
        "drank_ml": float(report["drank_ml"]),
        "food_hydration_ml": float(report["food_hydration_ml"]),
        "total_hydration_ml": float(report["total_hydration_ml"]),
    }
