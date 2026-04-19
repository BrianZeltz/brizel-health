"""Tests for food entry read queries."""

from __future__ import annotations

import pytest

from custom_components.brizel_health.application.nutrition.food_entry_queries import (
    get_food_entry,
    get_food_entries,
    get_food_entries_for_profile,
    get_food_entries_for_profile_date,
)
from custom_components.brizel_health.core.users.brizel_user import BrizelUser
from custom_components.brizel_health.core.users.errors import BrizelUserNotFoundError
from custom_components.brizel_health.domains.nutrition.errors import (
    BrizelFoodEntryValidationError,
)
from custom_components.brizel_health.domains.nutrition.models.food_entry import (
    FoodEntry,
)


class InMemoryFoodEntryRepository:
    """Simple in-memory repository for food entry query tests."""

    def __init__(self, food_entries: list[FoodEntry]) -> None:
        self._food_entries = food_entries

    def get_food_entry_by_id(self, food_entry_id: str) -> FoodEntry:
        for food_entry in self._food_entries:
            if food_entry.food_entry_id == food_entry_id:
                return food_entry
        raise AssertionError("Expected test food entry to exist")

    def get_all_food_entries(self) -> list[FoodEntry]:
        return list(self._food_entries)


class InMemoryUserRepository:
    """Simple user repository for cross-slice query tests."""

    def __init__(self, users: list[BrizelUser]) -> None:
        self._users = {user.user_id: user for user in users}

    async def add(self, user: BrizelUser) -> BrizelUser:
        self._users[user.user_id] = user
        return user

    async def update(self, user: BrizelUser) -> BrizelUser:
        self._users[user.user_id] = user
        return user

    async def delete(self, user_id: str) -> BrizelUser:
        return self._users.pop(user_id)

    def get_by_id(self, user_id: str) -> BrizelUser:
        user = self._users.get(user_id)
        if user is None:
            raise BrizelUserNotFoundError(
                f"No profile found for profile_id '{user_id}'."
            )
        return user

    def get_all(self) -> list[BrizelUser]:
        return list(self._users.values())

    def display_name_exists(
        self,
        display_name: str,
        exclude_user_id: str | None = None,
    ) -> bool:
        normalized = display_name.strip().casefold()
        for user_id, user in self._users.items():
            if exclude_user_id is not None and user_id == exclude_user_id:
                continue
            if user.display_name.strip().casefold() == normalized:
                return True
        return False


def _food_entry(
    food_entry_id: str,
    profile_id: str,
    consumed_at: str,
) -> FoodEntry:
    """Build a persisted food entry model for tests."""
    return FoodEntry.from_dict(
        {
            "food_entry_id": food_entry_id,
            "profile_id": profile_id,
            "food_id": "food-1",
            "food_name": "Apple",
            "food_brand": "Orchard",
            "grams": 150,
            "meal_type": "snack",
            "note": "Fresh",
            "source": "manual",
            "consumed_at": consumed_at,
            "kcal": 78,
            "protein": 0.45,
            "carbs": 21,
            "fat": 0.3,
            "created_at": consumed_at,
        }
    )


def test_get_food_entries_returns_all_persisted_entries() -> None:
    """Read queries return all active food entries."""
    deleted_entry = _food_entry(
        "entry-deleted",
        "user-1",
        "2026-04-04T09:00:00+00:00",
    )
    deleted_entry.mark_deleted(deleted_at="2026-04-04T10:00:00+00:00")
    repository = InMemoryFoodEntryRepository(
        [
            _food_entry("entry-1", "user-1", "2026-04-04T08:00:00+00:00"),
            _food_entry("entry-2", "user-2", "2026-04-05T08:00:00+00:00"),
            deleted_entry,
        ]
    )

    entries = get_food_entries(repository)

    assert [entry.food_entry_id for entry in entries] == ["entry-1", "entry-2"]


def test_get_food_entry_returns_single_entry() -> None:
    """Single-entry query returns the requested food entry."""
    repository = InMemoryFoodEntryRepository(
        [
            _food_entry("entry-1", "user-1", "2026-04-04T08:00:00+00:00"),
            _food_entry("entry-2", "user-2", "2026-04-05T08:00:00+00:00"),
        ]
    )

    entry = get_food_entry(repository, " entry-2 ")

    assert entry.food_entry_id == "entry-2"


def test_get_food_entries_for_profile_filters_by_profile() -> None:
    """Profile queries keep the legacy profile filter behavior."""
    repository = InMemoryFoodEntryRepository(
        [
            _food_entry("entry-1", "user-1", "2026-04-04T08:00:00+00:00"),
            _food_entry("entry-2", "user-2", "2026-04-05T08:00:00+00:00"),
            _food_entry("entry-3", "user-1", "2026-04-06T08:00:00+00:00"),
        ]
    )
    user_repository = InMemoryUserRepository(
        [
            BrizelUser(
                user_id="user-1",
                display_name="Alice",
                linked_ha_user_id=None,
                created_at="2026-04-04T07:00:00+00:00",
            )
        ]
    )

    entries = get_food_entries_for_profile(repository, user_repository, " user-1 ")

    assert [entry.food_entry_id for entry in entries] == ["entry-1", "entry-3"]


def test_get_food_entries_for_profile_date_filters_by_date() -> None:
    """Date queries keep the legacy date filter behavior."""
    repository = InMemoryFoodEntryRepository(
        [
            _food_entry("entry-1", "user-1", "2026-04-04T08:00:00+00:00"),
            _food_entry("entry-2", "user-1", "2026-04-04T12:00:00+00:00"),
            _food_entry("entry-3", "user-1", "2026-04-05T08:00:00+00:00"),
        ]
    )
    user_repository = InMemoryUserRepository(
        [
            BrizelUser(
                user_id="user-1",
                display_name="Alice",
                linked_ha_user_id=None,
                created_at="2026-04-04T07:00:00+00:00",
            )
        ]
    )

    entries = get_food_entries_for_profile_date(
        repository,
        user_repository,
        "user-1",
        "2026-04-04",
    )

    assert [entry.food_entry_id for entry in entries] == ["entry-1", "entry-2"]


def test_get_food_entries_for_profile_date_validates_date_format() -> None:
    """Date validation stays in the food entry query layer."""
    repository = InMemoryFoodEntryRepository([])
    user_repository = InMemoryUserRepository([])

    with pytest.raises(BrizelFoodEntryValidationError):
        get_food_entries_for_profile_date(
            repository,
            user_repository,
            "user-1",
            "04-04-2026",
        )
