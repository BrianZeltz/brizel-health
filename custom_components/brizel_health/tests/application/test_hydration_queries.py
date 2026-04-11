"""Tests for hydration summary queries."""

from __future__ import annotations

import pytest

from custom_components.brizel_health.application.nutrition.add_water import add_water
from custom_components.brizel_health.application.nutrition.hydration_queries import (
    get_daily_hydration_breakdown,
    get_daily_hydration_report,
    get_daily_hydration_summary,
)
from custom_components.brizel_health.core.users.brizel_user import BrizelUser
from custom_components.brizel_health.core.users.errors import BrizelUserNotFoundError
from custom_components.brizel_health.domains.nutrition.errors import (
    BrizelFoodEntryNotFoundError,
    BrizelFoodNotFoundError,
)
from custom_components.brizel_health.domains.nutrition.models.food import (
    Food,
    HYDRATION_KIND_FOOD,
    HYDRATION_SOURCE_EXPLICIT,
    HYDRATION_SOURCE_INTERNAL,
)
from custom_components.brizel_health.domains.nutrition.models.food_entry import (
    FoodEntry,
)
from custom_components.brizel_health.domains.nutrition.services.water import (
    DEFAULT_WATER_AMOUNT_ML,
    INTERNAL_WATER_FOOD_ID,
)


class InMemoryFoodRepository:
    """Simple in-memory repository for hydration tests."""

    def __init__(self, foods: list[Food] | None = None) -> None:
        self._foods = {food.food_id: food for food in foods or []}

    async def add(self, food: Food) -> Food:
        self._foods[food.food_id] = food
        return food

    async def update(self, food: Food) -> Food:
        self._foods[food.food_id] = food
        return food

    async def delete(self, food_id: str) -> None:
        del self._foods[food_id]

    def get_food_by_id(self, food_id: str) -> Food:
        food = self._foods.get(food_id)
        if food is None:
            raise BrizelFoodNotFoundError(
                f"No food found for food_id '{food_id}'."
            )
        return food

    def get_all_foods(self) -> list[Food]:
        return list(self._foods.values())

    def food_name_exists(
        self,
        name: str,
        brand: str | None,
        exclude_food_id: str | None = None,
    ) -> bool:
        return False

    def barcode_exists(
        self,
        barcode: str | None,
        exclude_food_id: str | None = None,
    ) -> bool:
        return False


class InMemoryFoodEntryRepository:
    """Simple in-memory food entry repository for hydration tests."""

    def __init__(self, food_entries: list[FoodEntry] | None = None) -> None:
        self._food_entries = {
            food_entry.food_entry_id: food_entry for food_entry in food_entries or []
        }

    async def add(self, food_entry: FoodEntry) -> FoodEntry:
        self._food_entries[food_entry.food_entry_id] = food_entry
        return food_entry

    async def delete(self, food_entry_id: str) -> FoodEntry:
        food_entry = self._food_entries.get(food_entry_id)
        if food_entry is None:
            raise BrizelFoodEntryNotFoundError(
                f"No food entry found for food_entry_id '{food_entry_id}'."
            )
        del self._food_entries[food_entry_id]
        return food_entry

    def get_food_entry_by_id(self, food_entry_id: str) -> FoodEntry:
        return self._food_entries[food_entry_id]

    def get_all_food_entries(self) -> list[FoodEntry]:
        return list(self._food_entries.values())


class InMemoryUserRepository:
    """Simple user repository for hydration tests."""

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


def _user_repository() -> InMemoryUserRepository:
    """Build a repository with one local test user."""
    return InMemoryUserRepository(
        [
            BrizelUser(
                user_id="user-1",
                display_name="Alice",
                linked_ha_user_id=None,
                created_at="2026-04-05T10:00:00+00:00",
            )
        ]
    )


@pytest.mark.asyncio
async def test_daily_hydration_summary_counts_default_water_as_drank() -> None:
    """Water shortcut contributes to drank_ml via the normal food entry system."""
    food_repository = InMemoryFoodRepository()
    food_entry_repository = InMemoryFoodEntryRepository()
    user_repository = _user_repository()

    await add_water(
        food_repository=food_repository,
        food_entry_repository=food_entry_repository,
        user_repository=user_repository,
        recent_food_repository=None,
        profile_id="user-1",
        consumed_at="2026-04-05T08:00:00+00:00",
    )

    summary = get_daily_hydration_summary(
        food_entry_repository=food_entry_repository,
        food_repository=food_repository,
        user_repository=user_repository,
        profile_id="user-1",
        date="2026-04-05",
    )

    assert food_repository.get_food_by_id(INTERNAL_WATER_FOOD_ID).is_hydration_drink()
    assert summary == {
        "drank_ml": DEFAULT_WATER_AMOUNT_ML,
        "food_hydration_ml": 0.0,
        "total_hydration_ml": DEFAULT_WATER_AMOUNT_ML,
    }
    report = get_daily_hydration_report(
        food_entry_repository=food_entry_repository,
        food_repository=food_repository,
        user_repository=user_repository,
        profile_id="user-1",
        date="2026-04-05",
    )
    assert report["breakdown"] == [
        {
            "food_id": INTERNAL_WATER_FOOD_ID,
            "food_name": "Water",
            "food_brand": None,
            "hydration_kind": "drink",
            "hydration_source": HYDRATION_SOURCE_INTERNAL,
            "hydration_ml": DEFAULT_WATER_AMOUNT_ML,
            "entry_count": 1,
        }
    ]


@pytest.mark.asyncio
async def test_daily_hydration_summary_uses_custom_water_amount() -> None:
    """Custom water amounts stay fully compatible with hydration totals."""
    food_repository = InMemoryFoodRepository()
    food_entry_repository = InMemoryFoodEntryRepository()
    user_repository = _user_repository()

    await add_water(
        food_repository=food_repository,
        food_entry_repository=food_entry_repository,
        user_repository=user_repository,
        recent_food_repository=None,
        profile_id="user-1",
        amount_ml=300,
        consumed_at="2026-04-05T09:30:00+00:00",
    )

    summary = get_daily_hydration_summary(
        food_entry_repository=food_entry_repository,
        food_repository=food_repository,
        user_repository=user_repository,
        profile_id="user-1",
        date="2026-04-05",
    )

    assert summary["drank_ml"] == 300.0
    assert summary["total_hydration_ml"] == 300.0


def test_daily_hydration_summary_treats_foods_without_metadata_conservatively() -> None:
    """Foods without hydration metadata should not be guessed as hydrated."""
    food = Food.from_dict(
        {
            "food_id": "food-1",
            "name": "Apple",
            "brand": None,
            "barcode": None,
            "kcal_per_100g": 52,
            "protein_per_100g": 0.3,
            "carbs_per_100g": 14,
            "fat_per_100g": 0.2,
            "created_at": "2026-04-05T07:00:00+00:00",
        }
    )
    repository = InMemoryFoodRepository([food])
    food_entry_repository = InMemoryFoodEntryRepository(
        [
            FoodEntry.create(
                profile_id="user-1",
                food=food,
                grams=180,
                consumed_at="2026-04-05T12:00:00+00:00",
            )
        ]
    )

    summary = get_daily_hydration_summary(
        food_entry_repository=food_entry_repository,
        food_repository=repository,
        user_repository=_user_repository(),
        profile_id="user-1",
        date="2026-04-05",
    )

    assert summary == {
        "drank_ml": 0.0,
        "food_hydration_ml": 0.0,
        "total_hydration_ml": 0.0,
    }


def test_daily_hydration_summary_can_count_hydration_from_foods_later_on() -> None:
    """Hydration metadata already allows a later food-based hydration breakdown."""
    cucumber = Food.create(
        name="Cucumber",
        brand=None,
        barcode=None,
        kcal_per_100g=15,
        protein_per_100g=0.7,
        carbs_per_100g=3.6,
        fat_per_100g=0.1,
        hydration_kind=HYDRATION_KIND_FOOD,
        hydration_ml_per_100g=95,
        hydration_source=HYDRATION_SOURCE_EXPLICIT,
    )
    repository = InMemoryFoodRepository([cucumber])
    food_entry_repository = InMemoryFoodEntryRepository(
        [
            FoodEntry.create(
                profile_id="user-1",
                food=cucumber,
                grams=200,
                consumed_at="2026-04-05T13:00:00+00:00",
            )
        ]
    )

    summary = get_daily_hydration_summary(
        food_entry_repository=food_entry_repository,
        food_repository=repository,
        user_repository=_user_repository(),
        profile_id="user-1",
        date="2026-04-05",
    )

    assert summary == {
        "drank_ml": 0.0,
        "food_hydration_ml": 190.0,
        "total_hydration_ml": 190.0,
    }


@pytest.mark.asyncio
async def test_daily_hydration_report_groups_breakdown_by_food() -> None:
    """Hydration report should split drinks and foods and aggregate by food."""
    cucumber = Food.create(
        name="Cucumber",
        brand=None,
        barcode=None,
        kcal_per_100g=15,
        protein_per_100g=0.7,
        carbs_per_100g=3.6,
        fat_per_100g=0.1,
        hydration_kind=HYDRATION_KIND_FOOD,
        hydration_ml_per_100g=95,
        hydration_source=HYDRATION_SOURCE_EXPLICIT,
    )
    apple = Food.from_dict(
        {
            "food_id": "food-apple",
            "name": "Apple",
            "brand": None,
            "barcode": None,
            "kcal_per_100g": 52,
            "protein_per_100g": 0.3,
            "carbs_per_100g": 14,
            "fat_per_100g": 0.2,
            "created_at": "2026-04-05T07:00:00+00:00",
        }
    )
    food_repository = InMemoryFoodRepository([cucumber, apple])
    food_entry_repository = InMemoryFoodEntryRepository()
    user_repository = _user_repository()

    await add_water(
        food_repository=food_repository,
        food_entry_repository=food_entry_repository,
        user_repository=user_repository,
        recent_food_repository=None,
        profile_id="user-1",
        amount_ml=200,
        consumed_at="2026-04-05T08:00:00+00:00",
    )
    await add_water(
        food_repository=food_repository,
        food_entry_repository=food_entry_repository,
        user_repository=user_repository,
        recent_food_repository=None,
        profile_id="user-1",
        amount_ml=350,
        consumed_at="2026-04-05T09:00:00+00:00",
    )
    await food_entry_repository.add(
        FoodEntry.create(
            profile_id="user-1",
            food=cucumber,
            grams=200,
            consumed_at="2026-04-05T13:00:00+00:00",
        )
    )
    await food_entry_repository.add(
        FoodEntry.create(
            profile_id="user-1",
            food=apple,
            grams=180,
            consumed_at="2026-04-05T15:00:00+00:00",
        )
    )

    report = get_daily_hydration_report(
        food_entry_repository=food_entry_repository,
        food_repository=food_repository,
        user_repository=user_repository,
        profile_id="user-1",
        date="2026-04-05",
    )

    assert report["drank_ml"] == 550.0
    assert report["food_hydration_ml"] == 190.0
    assert report["total_hydration_ml"] == 740.0
    assert report["breakdown"] == [
        {
            "food_id": INTERNAL_WATER_FOOD_ID,
            "food_name": "Water",
            "food_brand": None,
            "hydration_kind": "drink",
            "hydration_source": HYDRATION_SOURCE_INTERNAL,
            "hydration_ml": 550.0,
            "entry_count": 2,
        },
        {
            "food_id": cucumber.food_id,
            "food_name": "Cucumber",
            "food_brand": None,
            "hydration_kind": "food",
            "hydration_source": HYDRATION_SOURCE_EXPLICIT,
            "hydration_ml": 190.0,
            "entry_count": 1,
        },
    ]


@pytest.mark.asyncio
async def test_daily_hydration_breakdown_returns_only_trusted_food_contributions() -> None:
    """The dedicated breakdown query should exclude foods without trusted hydration data."""
    cucumber = Food.create(
        name="Cucumber",
        brand=None,
        barcode=None,
        kcal_per_100g=15,
        protein_per_100g=0.7,
        carbs_per_100g=3.6,
        fat_per_100g=0.1,
        hydration_kind=HYDRATION_KIND_FOOD,
        hydration_ml_per_100g=95,
        hydration_source=HYDRATION_SOURCE_EXPLICIT,
    )
    apple = Food.from_dict(
        {
            "food_id": "food-apple",
            "name": "Apple",
            "brand": None,
            "barcode": None,
            "kcal_per_100g": 52,
            "protein_per_100g": 0.3,
            "carbs_per_100g": 14,
            "fat_per_100g": 0.2,
            "created_at": "2026-04-05T07:00:00+00:00",
        }
    )
    food_repository = InMemoryFoodRepository([cucumber, apple])
    food_entry_repository = InMemoryFoodEntryRepository(
        [
            FoodEntry.create(
                profile_id="user-1",
                food=cucumber,
                grams=200,
                consumed_at="2026-04-05T13:00:00+00:00",
            ),
            FoodEntry.create(
                profile_id="user-1",
                food=apple,
                grams=180,
                consumed_at="2026-04-05T15:00:00+00:00",
            ),
        ]
    )

    breakdown = get_daily_hydration_breakdown(
        food_entry_repository=food_entry_repository,
        food_repository=food_repository,
        user_repository=_user_repository(),
        profile_id="user-1",
        date="2026-04-05",
    )

    assert breakdown == [
        {
            "food_id": cucumber.food_id,
            "food_name": "Cucumber",
            "food_brand": None,
            "hydration_kind": "food",
            "hydration_source": HYDRATION_SOURCE_EXPLICIT,
            "hydration_ml": 190.0,
            "entry_count": 1,
        }
    ]
