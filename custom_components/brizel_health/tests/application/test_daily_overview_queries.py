"""Tests for daily overview queries."""

from __future__ import annotations

from custom_components.brizel_health.application.queries.daily_overview_queries import (
    get_daily_overview,
)
from custom_components.brizel_health.core.users.brizel_user import BrizelUser
from custom_components.brizel_health.core.users.errors import BrizelUserNotFoundError
from custom_components.brizel_health.domains.body.models.body_profile import (
    ACTIVITY_LEVEL_MODERATE,
    SEX_MALE,
    BodyProfile,
)
from custom_components.brizel_health.domains.nutrition.models.food_entry import FoodEntry


class InMemoryUserRepository:
    """Simple user repository for overview tests."""

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


class InMemoryBodyProfileRepository:
    """Simple body profile repository for overview tests."""

    def __init__(self, body_profile: BodyProfile | None = None) -> None:
        self._body_profile = body_profile

    async def upsert(self, body_profile: BodyProfile) -> BodyProfile:
        self._body_profile = body_profile
        return body_profile

    def get_by_profile_id(self, profile_id: str) -> BodyProfile | None:
        if self._body_profile is None or self._body_profile.profile_id != profile_id:
            return None
        return self._body_profile


class InMemoryFoodEntryRepository:
    """Simple food entry repository for overview tests."""

    def __init__(self, food_entries: list[FoodEntry]) -> None:
        self._food_entries = food_entries

    def get_all_food_entries(self) -> list[FoodEntry]:
        return list(self._food_entries)

    def get_food_entry_by_id(self, food_entry_id: str) -> FoodEntry:
        for food_entry in self._food_entries:
            if food_entry.food_entry_id == food_entry_id:
                return food_entry
        raise AssertionError("Expected food entry to exist in tests")


def _user_repository() -> InMemoryUserRepository:
    return InMemoryUserRepository(
        [
            BrizelUser(
                user_id="profile-1",
                display_name="Alice",
                linked_ha_user_id=None,
                created_at="2026-04-10T08:00:00+00:00",
            )
        ]
    )


def _complete_body_profile() -> BodyProfile:
    return BodyProfile.create(
        profile_id="profile-1",
        age_years=35,
        sex=SEX_MALE,
        height_cm=180,
        weight_kg=80,
        activity_level=ACTIVITY_LEVEL_MODERATE,
    )


def _food_entry(
    *,
    food_entry_id: str,
    kcal: float,
    protein: float,
    fat: float,
    consumed_at: str = "2026-04-10T12:00:00+00:00",
) -> FoodEntry:
    return FoodEntry.from_dict(
        {
            "food_entry_id": food_entry_id,
            "profile_id": "profile-1",
            "food_id": "food-1",
            "food_name": "Test Food",
            "food_brand": None,
            "grams": 100,
            "meal_type": "snack",
            "note": None,
            "source": "manual",
            "consumed_at": consumed_at,
            "kcal": kcal,
            "protein": protein,
            "carbs": 0,
            "fat": fat,
            "created_at": consumed_at,
        }
    )


def test_get_daily_overview_returns_all_three_macro_statuses() -> None:
    """Daily overview should bundle kcal, protein and fat statuses."""
    overview = get_daily_overview(
        food_entry_repository=InMemoryFoodEntryRepository(
            [_food_entry(food_entry_id="entry-1", kcal=1984, protein=120, fat=95)]
        ),
        body_profile_repository=InMemoryBodyProfileRepository(_complete_body_profile()),
        user_repository=_user_repository(),
        profile_id="profile-1",
        date="2026-04-10",
    )

    assert overview["date"] == "2026-04-10"
    assert overview["has_data"] is True
    assert overview["kcal"]["status"] == "under"
    assert overview["protein"]["status"] == "within"
    assert overview["fat"]["status"] == "over"


def test_get_daily_overview_marks_empty_day_as_no_data() -> None:
    """Overview should expose the empty-day state for the hero card."""
    overview = get_daily_overview(
        food_entry_repository=InMemoryFoodEntryRepository([]),
        body_profile_repository=InMemoryBodyProfileRepository(_complete_body_profile()),
        user_repository=_user_repository(),
        profile_id="profile-1",
        date="2026-04-10",
    )

    assert overview["has_data"] is False
    assert overview["kcal"]["consumed"] == 0
    assert overview["protein"]["consumed"] == 0
    assert overview["fat"]["consumed"] == 0
