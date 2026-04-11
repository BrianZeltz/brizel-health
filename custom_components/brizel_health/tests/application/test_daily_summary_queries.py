"""Tests for daily nutrition summary queries."""

from __future__ import annotations

from custom_components.brizel_health.application.nutrition.daily_summary_queries import (
    get_daily_summary,
)
from custom_components.brizel_health.core.users.brizel_user import BrizelUser
from custom_components.brizel_health.core.users.errors import BrizelUserNotFoundError
from custom_components.brizel_health.domains.nutrition.models.food_entry import (
    FoodEntry,
)


class InMemoryFoodEntryRepository:
    """Simple repository for daily summary tests."""

    def __init__(self, food_entries: list[FoodEntry]) -> None:
        self._food_entries = {
            food_entry.food_entry_id: food_entry for food_entry in food_entries
        }

    async def add(self, food_entry: FoodEntry) -> FoodEntry:
        self._food_entries[food_entry.food_entry_id] = food_entry
        return food_entry

    async def delete(self, food_entry_id: str) -> FoodEntry:
        return self._food_entries.pop(food_entry_id)

    def get_food_entry_by_id(self, food_entry_id: str) -> FoodEntry:
        return self._food_entries[food_entry_id]

    def get_all_food_entries(self) -> list[FoodEntry]:
        return list(self._food_entries.values())


class InMemoryUserRepository:
    """Simple user repository for daily summary tests."""

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
        return False


def _food_entry(
    food_entry_id: str,
    profile_id: str,
    consumed_at: str,
    kcal: float,
    protein: float,
    carbs: float,
    fat: float,
) -> FoodEntry:
    """Build a persisted food entry for summary tests."""
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
            "kcal": kcal,
            "protein": protein,
            "carbs": carbs,
            "fat": fat,
            "created_at": consumed_at,
        }
    )


def test_get_daily_summary_aggregates_entries_for_profile_and_date() -> None:
    """Daily summary query aggregates the filtered food entries."""
    repository = InMemoryFoodEntryRepository(
        [
            _food_entry(
                "entry-1",
                "user-1",
                "2026-04-05T08:00:00+00:00",
                78,
                0.45,
                21,
                0.3,
            ),
            _food_entry(
                "entry-2",
                "user-1",
                "2026-04-05T12:00:00+00:00",
                130,
                2.7,
                28,
                0.3,
            ),
            _food_entry(
                "entry-3",
                "user-1",
                "2026-04-06T08:00:00+00:00",
                50,
                1.0,
                10,
                0.1,
            ),
            _food_entry(
                "entry-4",
                "user-2",
                "2026-04-05T08:00:00+00:00",
                90,
                1.0,
                12,
                0.2,
            ),
        ]
    )
    user_repository = InMemoryUserRepository(
        [
            BrizelUser(
                user_id="user-1",
                display_name="Alice",
                linked_ha_user_id=None,
                created_at="2026-04-05T07:00:00+00:00",
            )
        ]
    )

    summary = get_daily_summary(repository, user_repository, "user-1", "2026-04-05")

    assert summary == {
        "kcal": 208.0,
        "protein": 3.15,
        "carbs": 49.0,
        "fat": 0.6,
    }
