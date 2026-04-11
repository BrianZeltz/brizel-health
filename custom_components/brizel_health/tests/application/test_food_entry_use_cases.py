"""Tests for food entry write use cases."""

from __future__ import annotations

import pytest

from custom_components.brizel_health.application.nutrition.food_entry_use_cases import (
    create_food_entry,
    delete_food_entry,
)
from custom_components.brizel_health.application.queries.compatibility_queries import (
    get_food_compatibility,
)
from custom_components.brizel_health.core.users.brizel_user import BrizelUser
from custom_components.brizel_health.core.users.errors import BrizelUserNotFoundError
from custom_components.brizel_health.domains.body.models.dietary_restrictions import (
    DietaryRestrictions,
)
from custom_components.brizel_health.domains.nutrition.errors import (
    BrizelFoodEntryNotFoundError,
)
from custom_components.brizel_health.domains.nutrition.models.food import Food
from custom_components.brizel_health.domains.nutrition.models.food_compatibility import (
    FOOD_COMPATIBILITY_SOURCE_EXPLICIT,
    FoodCompatibilityMetadata,
)
from custom_components.brizel_health.domains.nutrition.models.food_entry import (
    FoodEntry,
)
from custom_components.brizel_health.domains.nutrition.models.recent_food_reference import (
    RecentFoodReference,
)


class InMemoryFoodEntryRepository:
    """Simple in-memory repository for food entry write tests."""

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

    def get_all_food_entries(self) -> list[FoodEntry]:
        return list(self._food_entries.values())


class InMemoryFoodRepository:
    """Simple in-memory food repository for cross-slice write tests."""

    def __init__(self, foods: list[Food]) -> None:
        self._foods = {food.food_id: food for food in foods}

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
            raise AssertionError("Expected test food to exist")
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


class InMemoryUserRepository:
    """Simple user repository for cross-slice write tests."""

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
    """Simple recent-food repository for entry write tests."""

    def __init__(self) -> None:
        self._entries: dict[str, list[RecentFoodReference]] = {}

    async def touch(
        self,
        profile_id: str,
        food_id: str,
        used_at: str | None = None,
        max_items: int = 20,
    ) -> list[RecentFoodReference]:
        reference = RecentFoodReference.create(food_id, used_at)
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


@pytest.mark.asyncio
async def test_create_food_entry_creates_macros_from_catalog_food() -> None:
    """Create use case persists a new food entry from catalog data."""
    food_entry_repository = InMemoryFoodEntryRepository()
    user_repository = InMemoryUserRepository(
        [
            BrizelUser(
                user_id="user-1",
                display_name="Alice",
                linked_ha_user_id=None,
                created_at="2026-04-05T08:00:00+00:00",
            )
        ]
    )
    food_repository = InMemoryFoodRepository(
        [
            Food.from_dict(
                {
                    "food_id": "food-1",
                    "name": "Apple",
                    "brand": "Orchard",
                    "barcode": "12345",
                    "kcal_per_100g": 52,
                    "protein_per_100g": 0.3,
                    "carbs_per_100g": 14,
                    "fat_per_100g": 0.2,
                    "created_at": "2026-04-05T07:00:00+00:00",
                }
            )
        ]
    )

    food_entry = await create_food_entry(
        repository=food_entry_repository,
        user_repository=user_repository,
        food_repository=food_repository,
        recent_food_repository=None,
        profile_id=" user-1 ",
        food_id=" food-1 ",
        grams=150,
        meal_type="snack",
        note=" Fresh ",
        source="manual",
    )

    assert food_entry.profile_id == "user-1"
    assert food_entry.food_id == "food-1"
    assert food_entry.food_name == "Apple"
    assert food_entry.note == "Fresh"
    assert food_entry.kcal == 78.0
    assert food_entry_repository.get_all_food_entries()[0].food_entry_id == (
        food_entry.food_entry_id
    )


@pytest.mark.asyncio
async def test_delete_food_entry_returns_removed_entry() -> None:
    """Delete use case returns the deleted food entry for follow-up handling."""
    existing_entry = FoodEntry.from_dict(
        {
            "food_entry_id": "entry-1",
            "profile_id": "user-1",
            "food_id": "food-1",
            "food_name": "Apple",
            "food_brand": "Orchard",
            "grams": 150,
            "meal_type": "snack",
            "note": "Fresh",
            "source": "manual",
            "consumed_at": "2026-04-05T08:00:00+00:00",
            "kcal": 78,
            "protein": 0.45,
            "carbs": 21,
            "fat": 0.3,
            "created_at": "2026-04-05T08:00:00+00:00",
        }
    )
    repository = InMemoryFoodEntryRepository([existing_entry])

    deleted_entry = await delete_food_entry(repository, " entry-1 ")

    assert deleted_entry.food_entry_id == "entry-1"
    assert repository.get_all_food_entries() == []


@pytest.mark.asyncio
async def test_create_food_entry_is_not_blocked_by_informational_compatibility_result() -> None:
    """Compatibility assessment stays advisory and does not block entry creation."""
    food_entry_repository = InMemoryFoodEntryRepository()
    user_repository = InMemoryUserRepository(
        [
            BrizelUser(
                user_id="user-1",
                display_name="Alice",
                linked_ha_user_id=None,
                created_at="2026-04-05T08:00:00+00:00",
            )
        ]
    )
    yogurt = Food.create(
        name="Yogurt",
        brand=None,
        barcode=None,
        kcal_per_100g=61,
        protein_per_100g=3.5,
        carbs_per_100g=4.7,
        fat_per_100g=3.3,
        compatibility=FoodCompatibilityMetadata.create(
            allergens=["milk"],
            allergens_known=True,
            source=FOOD_COMPATIBILITY_SOURCE_EXPLICIT,
        ),
    )
    food_repository = InMemoryFoodRepository([yogurt])

    assessment = get_food_compatibility(
        repository=food_repository,
        food_id=yogurt.food_id,
        restrictions=DietaryRestrictions.create(allergens=["milk"]),
    )
    food_entry = await create_food_entry(
        repository=food_entry_repository,
        user_repository=user_repository,
        food_repository=food_repository,
        recent_food_repository=None,
        profile_id="user-1",
        food_id=yogurt.food_id,
        grams=150,
    )

    assert assessment["status"] == "incompatible"
    assert food_entry.food_id == yogurt.food_id
    assert food_entry_repository.get_all_food_entries()[0].food_entry_id == (
        food_entry.food_entry_id
    )


@pytest.mark.asyncio
async def test_create_food_entry_updates_recent_foods_for_the_profile() -> None:
    """Recent foods should be touched when an entry is created from a catalog food."""
    food_entry_repository = InMemoryFoodEntryRepository()
    user_repository = InMemoryUserRepository(
        [
            BrizelUser(
                user_id="user-1",
                display_name="Alice",
                linked_ha_user_id=None,
                created_at="2026-04-05T08:00:00+00:00",
            )
        ]
    )
    apple = Food.create(
        name="Apple",
        brand=None,
        barcode=None,
        kcal_per_100g=52,
        protein_per_100g=0.3,
        carbs_per_100g=14,
        fat_per_100g=0.2,
    )
    rice = Food.create(
        name="Rice",
        brand=None,
        barcode=None,
        kcal_per_100g=130,
        protein_per_100g=2.7,
        carbs_per_100g=28,
        fat_per_100g=0.3,
    )
    food_repository = InMemoryFoodRepository([apple, rice])
    recent_food_repository = InMemoryRecentFoodRepository()

    await create_food_entry(
        repository=food_entry_repository,
        user_repository=user_repository,
        food_repository=food_repository,
        recent_food_repository=recent_food_repository,
        profile_id="user-1",
        food_id=rice.food_id,
        grams=150,
        consumed_at="2026-04-05T08:00:00+00:00",
    )
    created_entry = await create_food_entry(
        repository=food_entry_repository,
        user_repository=user_repository,
        food_repository=food_repository,
        recent_food_repository=recent_food_repository,
        profile_id="user-1",
        food_id=apple.food_id,
        grams=120,
        consumed_at="2026-04-05T09:00:00+00:00",
    )

    recent = recent_food_repository.get_recent("user-1")

    assert created_entry.food_id == apple.food_id
    assert [reference.food_id for reference in recent] == [
        apple.food_id,
        rice.food_id,
    ]
