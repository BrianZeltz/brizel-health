"""Tests for the water shortcut use cases."""

from __future__ import annotations

import pytest

from custom_components.brizel_health.application.nutrition.add_water import (
    add_water,
    remove_water,
)
from custom_components.brizel_health.core.users.brizel_user import BrizelUser
from custom_components.brizel_health.core.users.errors import BrizelUserNotFoundError
from custom_components.brizel_health.domains.nutrition.errors import (
    BrizelFoodEntryNotFoundError,
    BrizelFoodNotFoundError,
)
from custom_components.brizel_health.domains.nutrition.models.food import (
    Food,
    HYDRATION_SOURCE_INTERNAL,
)
from custom_components.brizel_health.domains.nutrition.models.food_entry import (
    FoodEntry,
)
from custom_components.brizel_health.domains.nutrition.models.recent_food_reference import (
    RecentFoodReference,
)
from custom_components.brizel_health.domains.nutrition.services.water import (
    DEFAULT_WATER_AMOUNT_ML,
    INTERNAL_WATER_FOOD_ID,
)


class InMemoryFoodRepository:
    """Simple in-memory food repository for water tests."""

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
    """Simple in-memory food entry repository for water tests."""

    def __init__(self) -> None:
        self._food_entries: dict[str, FoodEntry] = {}

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
    """Simple in-memory user repository for water tests."""

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


class InMemoryRecentFoodRepository:
    """Simple in-memory recent-food repository for water tests."""

    def __init__(self) -> None:
        self._entries: dict[str, list[RecentFoodReference]] = {}

    async def touch(
        self,
        profile_id: str,
        food_id: str,
        used_at: str | None = None,
        last_logged_grams: float | int | None = None,
        last_meal_type: str | None = None,
        max_items: int = 20,
    ) -> list[RecentFoodReference]:
        existing = next(
            (item for item in self._entries.get(profile_id, []) if item.food_id == food_id),
            None,
        )
        reference = RecentFoodReference.create(
            food_id,
            used_at,
            use_count=(existing.use_count + 1) if existing is not None else 1,
            last_logged_grams=last_logged_grams
            if last_logged_grams is not None
            else (existing.last_logged_grams if existing is not None else None),
            last_meal_type=last_meal_type
            if last_meal_type is not None
            else (existing.last_meal_type if existing is not None else None),
            is_favorite=existing.is_favorite if existing is not None else False,
        )
        updated = [reference] + [
            item
            for item in self._entries.get(profile_id, [])
            if item.food_id != reference.food_id
        ]
        updated = updated[:max_items]
        self._entries[profile_id] = updated
        return updated

    def get_recent(
        self,
        profile_id: str,
        limit: int = 10,
    ) -> list[RecentFoodReference]:
        return self._entries.get(profile_id, [])[:limit]


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
async def test_add_water_uses_default_amount() -> None:
    """Water shortcut uses the default amount when none is provided."""
    food_repository = InMemoryFoodRepository()
    food_entry_repository = InMemoryFoodEntryRepository()

    food_entry = await add_water(
        food_repository=food_repository,
        food_entry_repository=food_entry_repository,
        user_repository=_user_repository(),
        recent_food_repository=None,
        profile_id="user-1",
    )

    assert food_entry.grams == DEFAULT_WATER_AMOUNT_ML
    assert food_entry.food_id == INTERNAL_WATER_FOOD_ID
    assert food_entry.kcal == 0
    assert len(food_repository.get_all_foods()) == 1


@pytest.mark.asyncio
async def test_add_water_accepts_custom_amount() -> None:
    """Water shortcut stores custom water amounts as normal food entry grams."""
    food_repository = InMemoryFoodRepository()
    food_entry_repository = InMemoryFoodEntryRepository()

    food_entry = await add_water(
        food_repository=food_repository,
        food_entry_repository=food_entry_repository,
        user_repository=_user_repository(),
        recent_food_repository=None,
        profile_id="user-1",
        amount_ml=300,
    )

    assert food_entry.grams == 300
    assert food_entry.kcal == 0
    assert food_entry.carbs == 0
    assert food_entry.protein == 0
    assert food_entry.fat == 0


@pytest.mark.asyncio
async def test_add_water_persists_as_normal_food_entry_and_reuses_water_food() -> None:
    """Water shortcut stays inside the existing food and food entry system."""
    food_repository = InMemoryFoodRepository()
    food_entry_repository = InMemoryFoodEntryRepository()
    user_repository = _user_repository()

    first_entry = await add_water(
        food_repository=food_repository,
        food_entry_repository=food_entry_repository,
        user_repository=user_repository,
        recent_food_repository=None,
        profile_id="user-1",
        amount_ml=200,
    )
    second_entry = await add_water(
        food_repository=food_repository,
        food_entry_repository=food_entry_repository,
        user_repository=user_repository,
        recent_food_repository=None,
        profile_id="user-1",
        amount_ml=350,
    )

    stored_entries = food_entry_repository.get_all_food_entries()
    stored_water_food = food_repository.get_food_by_id(INTERNAL_WATER_FOOD_ID)

    assert [entry.food_entry_id for entry in stored_entries] == [
        first_entry.food_entry_id,
        second_entry.food_entry_id,
    ]
    assert len(food_repository.get_all_foods()) == 1
    assert stored_water_food.name == "Water"
    assert stored_water_food.kcal_per_100g == 0
    assert stored_water_food.hydration_source == HYDRATION_SOURCE_INTERNAL
    assert stored_entries[0].food_name == "Water"
    assert stored_entries[1].food_id == INTERNAL_WATER_FOOD_ID


@pytest.mark.asyncio
async def test_add_water_updates_recent_foods_for_the_profile() -> None:
    """Water shortcut should also keep the profile recent-food list current."""
    food_repository = InMemoryFoodRepository()
    food_entry_repository = InMemoryFoodEntryRepository()
    recent_food_repository = InMemoryRecentFoodRepository()

    await add_water(
        food_repository=food_repository,
        food_entry_repository=food_entry_repository,
        user_repository=_user_repository(),
        recent_food_repository=recent_food_repository,
        profile_id="user-1",
        amount_ml=250,
        consumed_at="2026-04-05T10:00:00+00:00",
    )

    recent = recent_food_repository.get_recent("user-1")

    assert [reference.food_id for reference in recent] == [INTERNAL_WATER_FOOD_ID]
    assert recent[0].last_logged_grams == 250


@pytest.mark.asyncio
async def test_remove_water_deletes_latest_matching_water_entry() -> None:
    """Remove water should delete the latest matching water entry amount."""
    food_repository = InMemoryFoodRepository()
    food_entry_repository = InMemoryFoodEntryRepository()
    user_repository = _user_repository()

    first_entry = await add_water(
        food_repository=food_repository,
        food_entry_repository=food_entry_repository,
        user_repository=user_repository,
        recent_food_repository=None,
        profile_id="user-1",
        amount_ml=250,
        consumed_at="2026-04-05T10:00:00+00:00",
    )
    second_entry = await add_water(
        food_repository=food_repository,
        food_entry_repository=food_entry_repository,
        user_repository=user_repository,
        recent_food_repository=None,
        profile_id="user-1",
        amount_ml=250,
        consumed_at="2026-04-05T11:00:00+00:00",
    )

    removed_entry = await remove_water(
        food_repository=food_repository,
        food_entry_repository=food_entry_repository,
        user_repository=user_repository,
        profile_id="user-1",
        amount_ml=250,
    )

    remaining_entries = food_entry_repository.get_all_food_entries()

    assert removed_entry.food_entry_id == second_entry.food_entry_id
    assert [entry.food_entry_id for entry in remaining_entries] == [
        first_entry.food_entry_id
    ]


@pytest.mark.asyncio
async def test_remove_water_requires_a_matching_amount() -> None:
    """Remove water should stay conservative when no matching water entry exists."""
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
        consumed_at="2026-04-05T10:00:00+00:00",
    )

    with pytest.raises(BrizelFoodEntryNotFoundError):
        await remove_water(
            food_repository=food_repository,
            food_entry_repository=food_entry_repository,
            user_repository=user_repository,
            profile_id="user-1",
            amount_ml=250,
        )
