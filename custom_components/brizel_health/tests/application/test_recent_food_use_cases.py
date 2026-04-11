"""Tests for recent-food use cases."""

from __future__ import annotations

import pytest

from custom_components.brizel_health.application.nutrition.recent_food_use_cases import (
    get_recent_foods,
    remember_recent_food,
)
from custom_components.brizel_health.domains.nutrition.errors import (
    BrizelFoodNotFoundError,
)
from custom_components.brizel_health.domains.nutrition.models.food import Food
from custom_components.brizel_health.domains.nutrition.models.recent_food_reference import (
    RecentFoodReference,
)


class InMemoryFoodRepository:
    """Simple in-memory food repository for recent-food tests."""

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


class InMemoryRecentFoodRepository:
    """Simple in-memory recent-food repository for use case tests."""

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
        current = self._entries.get(profile_id, [])
        updated = [reference] + [
            item for item in current if item.food_id != reference.food_id
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
async def test_remember_recent_food_is_profile_scoped_and_deduplicated() -> None:
    """Recent foods should be stored per profile and moved to the front on reuse."""
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
    recent_repository = InMemoryRecentFoodRepository()

    await remember_recent_food(
        recent_repository,
        food_repository,
        "profile-1",
        apple.food_id,
        used_at="2026-04-05T08:00:00+00:00",
    )
    await remember_recent_food(
        recent_repository,
        food_repository,
        "profile-1",
        rice.food_id,
        used_at="2026-04-05T09:00:00+00:00",
    )
    recent_references = await remember_recent_food(
        recent_repository,
        food_repository,
        "profile-1",
        apple.food_id,
        used_at="2026-04-05T10:00:00+00:00",
    )
    await remember_recent_food(
        recent_repository,
        food_repository,
        "profile-2",
        rice.food_id,
        used_at="2026-04-05T11:00:00+00:00",
    )

    assert [reference.food_id for reference in recent_references] == [
        apple.food_id,
        rice.food_id,
    ]
    assert [
        reference.food_id
        for reference in recent_repository.get_recent("profile-2")
    ] == [rice.food_id]


def test_get_recent_foods_resolves_existing_foods_only() -> None:
    """Recent-food query should return only foods still present in the catalog."""
    apple = Food.create(
        name="Apple",
        brand=None,
        barcode=None,
        kcal_per_100g=52,
        protein_per_100g=0.3,
        carbs_per_100g=14,
        fat_per_100g=0.2,
    )
    food_repository = InMemoryFoodRepository([apple])
    recent_repository = InMemoryRecentFoodRepository()
    recent_repository._entries["profile-1"] = [
        RecentFoodReference.create(apple.food_id, "2026-04-05T10:00:00+00:00"),
        RecentFoodReference.create("missing-food", "2026-04-05T09:00:00+00:00"),
    ]

    foods = get_recent_foods(recent_repository, food_repository, "profile-1")

    assert [food.food_id for food in foods] == [apple.food_id]
