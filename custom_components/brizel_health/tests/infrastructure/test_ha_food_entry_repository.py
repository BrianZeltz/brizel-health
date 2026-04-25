"""Tests for the Home Assistant food entry repository."""

from __future__ import annotations

import pytest

from custom_components.brizel_health.domains.nutrition.errors import (
    BrizelFoodEntryNotFoundError,
)
from custom_components.brizel_health.domains.nutrition.models.food_entry import (
    FoodEntry,
)
from custom_components.brizel_health.infrastructure.repositories.ha_food_entry_repository import (
    HomeAssistantFoodEntryRepository,
)


class FakeStoreManager:
    """Minimal store manager stub for repository tests."""

    def __init__(self, data: dict) -> None:
        self.data = data
        self.save_calls = 0

    async def async_save(self) -> None:
        self.save_calls += 1


def test_repository_reads_food_entries_from_legacy_storage_shape() -> None:
    """Repository reads from nutrition.food_entries unchanged."""
    repository = HomeAssistantFoodEntryRepository(
        FakeStoreManager(
            {
                "nutrition": {
                    "food_entries": {
                        "entry-1": {
                            "food_entry_id": "entry-1",
                            "profile_id": "user-1",
                            "food_id": "food-1",
                            "food_name": "Apple",
                            "food_brand": "Orchard",
                            "grams": 150,
                            "meal_type": "snack",
                            "note": "Fresh",
                            "source": "manual",
                            "consumed_at": "2026-04-04T08:00:00+00:00",
                            "kcal": 78,
                            "protein": 0.45,
                            "carbs": 21,
                            "fat": 0.3,
                            "created_at": "2026-04-04T08:00:00+00:00",
                        }
                    }
                }
            }
        )
    )

    entries = repository.get_all_food_entries()

    assert len(entries) == 1
    assert entries[0].food_entry_id == "entry-1"
    assert entries[0].profile_id == "user-1"


def test_repository_reads_single_food_entry_from_legacy_storage_shape() -> None:
    """Repository loads a single entry from nutrition.food_entries."""
    repository = HomeAssistantFoodEntryRepository(
        FakeStoreManager(
            {
                "nutrition": {
                    "food_entries": {
                        "entry-1": {
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
                    }
                }
            }
        )
    )

    entry = repository.get_food_entry_by_id("entry-1")

    assert entry.food_entry_id == "entry-1"
    assert entry.food_name == "Apple"


@pytest.mark.asyncio
async def test_repository_add_persists_food_entry_in_legacy_storage_shape() -> None:
    """Repository writes new food entries into nutrition.food_entries."""
    store_manager = FakeStoreManager({"nutrition": {"food_entries": {}}})
    repository = HomeAssistantFoodEntryRepository(store_manager)

    food_entry = await repository.add(
        FoodEntry.from_dict(
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
    )

    stored = store_manager.data["nutrition"]["food_entries"]["entry-1"]
    assert stored["record_id"] == "entry-1"
    assert stored["record_type"] == "food_log"
    assert isinstance(stored["encrypted_payload"], dict)
    assert "food_name" not in stored
    assert food_entry.food_entry_id == "entry-1"
    assert store_manager.save_calls >= 1


@pytest.mark.asyncio
async def test_repository_delete_tombstones_food_entry_in_core_storage_shape() -> None:
    """Repository tombstones food entries instead of physically deleting them."""
    store_manager = FakeStoreManager(
        {
            "nutrition": {
                "food_entries": {
                    "entry-1": {
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
                }
            }
        }
    )
    repository = HomeAssistantFoodEntryRepository(store_manager)

    deleted_entry = await repository.delete("entry-1")

    assert deleted_entry.food_entry_id == "entry-1"
    stored_entry = store_manager.data["nutrition"]["food_entries"]["entry-1"]
    assert stored_entry["record_id"] == "entry-1"
    assert stored_entry["record_type"] == "food_log"
    assert stored_entry["deleted_at"] is not None
    assert stored_entry["revision"] == 2
    assert repository.get_all_food_entries() == []
    assert repository.get_all_food_entries(include_deleted=True)[0].record_id == "entry-1"
    assert store_manager.save_calls >= 1


@pytest.mark.asyncio
async def test_repository_delete_raises_not_found_for_missing_entry() -> None:
    """Repository keeps the legacy not-found behavior for deletes."""
    repository = HomeAssistantFoodEntryRepository(
        FakeStoreManager({"nutrition": {"food_entries": {}}})
    )

    with pytest.raises(BrizelFoodEntryNotFoundError):
        await repository.delete("missing-entry")
