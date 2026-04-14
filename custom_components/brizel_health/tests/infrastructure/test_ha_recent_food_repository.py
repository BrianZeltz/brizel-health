"""Tests for the recent food repository."""

from __future__ import annotations

import pytest

from custom_components.brizel_health.infrastructure.repositories.ha_recent_food_repository import (
    HomeAssistantRecentFoodRepository,
)


class FakeStoreManager:
    """Minimal store manager stub for recent-food repository tests."""

    def __init__(self, data: dict) -> None:
        self.data = data
        self.save_calls = 0

    async def async_save(self) -> None:
        self.save_calls += 1


@pytest.mark.asyncio
async def test_repository_touch_stores_recent_foods_per_profile_and_deduplicates() -> None:
    """Recent foods should be kept per profile without duplicating food data."""
    store_manager = FakeStoreManager({"nutrition": {}})
    repository = HomeAssistantRecentFoodRepository(store_manager)

    await repository.touch(
        profile_id="profile-1",
        food_id="food-1",
        used_at="2026-04-05T08:00:00+00:00",
    )
    await repository.touch(
        profile_id="profile-1",
        food_id="food-2",
        used_at="2026-04-05T09:00:00+00:00",
    )
    updated = await repository.touch(
        profile_id="profile-1",
        food_id="food-1",
        used_at="2026-04-05T10:00:00+00:00",
        last_logged_grams=125,
        last_meal_type="lunch",
    )
    await repository.touch(
        profile_id="profile-2",
        food_id="food-3",
        used_at="2026-04-05T11:00:00+00:00",
    )

    assert [reference.food_id for reference in updated] == ["food-1", "food-2"]
    assert updated[0].use_count == 2
    assert updated[0].last_logged_grams == 125
    assert updated[0].last_meal_type == "lunch"
    assert [
        reference.food_id for reference in repository.get_recent("profile-2")
    ] == ["food-3"]
    assert store_manager.save_calls == 4


def test_repository_get_recent_returns_profile_scoped_references() -> None:
    """Repository should return recent-food references in stored order."""
    repository = HomeAssistantRecentFoodRepository(
        FakeStoreManager(
            {
                "nutrition": {
                    "recent_foods_by_profile": {
                        "profile-1": [
                            {
                                "food_id": "food-1",
                                "last_used_at": "2026-04-05T10:00:00+00:00",
                                "use_count": 3,
                                "last_logged_grams": 90,
                                "last_meal_type": "breakfast",
                                "is_favorite": True,
                            },
                            {
                                "food_id": "food-2",
                                "last_used_at": "2026-04-05T09:00:00+00:00",
                            },
                        ]
                    }
                }
            }
        )
    )

    recent_references = repository.get_recent("profile-1")

    assert [reference.food_id for reference in recent_references] == [
        "food-1",
        "food-2",
    ]
    assert recent_references[0].use_count == 3
    assert recent_references[0].last_logged_grams == 90
    assert recent_references[0].last_meal_type == "breakfast"
    assert recent_references[0].is_favorite is True
