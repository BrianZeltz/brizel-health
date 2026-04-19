"""Read queries for nutrition food entries."""

from __future__ import annotations

from datetime import datetime

from ...core.interfaces.user_repository import UserRepository
from ...domains.nutrition.errors import BrizelFoodEntryValidationError
from ...domains.nutrition.interfaces.food_entry_repository import FoodEntryRepository
from ...domains.nutrition.models.food_entry import FoodEntry
from ..users.user_use_cases import get_user


def _load_food_entries(
    repository: FoodEntryRepository,
    *,
    include_deleted: bool = False,
) -> list[FoodEntry]:
    """Load food-log records while keeping legacy test repositories compatible."""
    try:
        food_entries = repository.get_all_food_entries(
            include_deleted=include_deleted,
        )
    except TypeError:
        food_entries = repository.get_all_food_entries()

    if include_deleted:
        return food_entries
    return [food_entry for food_entry in food_entries if not food_entry.is_deleted]


def get_food_entry(
    repository: FoodEntryRepository,
    food_entry_id: str,
) -> FoodEntry:
    """Return a single food entry."""
    normalized_food_entry_id = food_entry_id.strip()
    if not normalized_food_entry_id:
        raise BrizelFoodEntryValidationError("A food entry ID is required.")

    return repository.get_food_entry_by_id(normalized_food_entry_id)


def get_food_entries(
    repository: FoodEntryRepository,
    *,
    include_deleted: bool = False,
) -> list[FoodEntry]:
    """Return all food entries."""
    return _load_food_entries(repository, include_deleted=include_deleted)


def get_food_entries_for_profile(
    repository: FoodEntryRepository,
    user_repository: UserRepository,
    profile_id: str,
    *,
    include_deleted: bool = False,
) -> list[FoodEntry]:
    """Return all food entries for a given profile."""
    normalized_profile_id = profile_id.strip()
    if not normalized_profile_id:
        raise BrizelFoodEntryValidationError("A profile ID is required.")

    get_user(user_repository, normalized_profile_id)

    return [
        food_entry
        for food_entry in _load_food_entries(
            repository,
            include_deleted=include_deleted,
        )
        if food_entry.profile_id == normalized_profile_id
    ]


def get_food_entries_for_profile_date(
    repository: FoodEntryRepository,
    user_repository: UserRepository,
    profile_id: str,
    date: str,
    *,
    include_deleted: bool = False,
) -> list[FoodEntry]:
    """Return food entries for a profile and date."""
    normalized_date = date.strip()
    if not normalized_date:
        raise BrizelFoodEntryValidationError("A date is required.")

    try:
        datetime.strptime(normalized_date, "%Y-%m-%d")
    except ValueError as err:
        raise BrizelFoodEntryValidationError(
            "date must be in YYYY-MM-DD format."
        ) from err

    return [
        food_entry
        for food_entry in get_food_entries_for_profile(
            repository=repository,
            user_repository=user_repository,
            profile_id=profile_id,
            include_deleted=include_deleted,
        )
        if food_entry.consumed_at.startswith(normalized_date)
    ]
