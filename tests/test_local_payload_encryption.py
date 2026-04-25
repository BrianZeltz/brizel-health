"""Focused tests for the first real at-rest encryption pilot."""

from __future__ import annotations

import asyncio
import json
import sys
import types

import pytest

homeassistant_module = types.ModuleType("homeassistant")
core_module = types.ModuleType("homeassistant.core")
core_module.HomeAssistant = object
helpers_module = types.ModuleType("homeassistant.helpers")
storage_module = types.ModuleType("homeassistant.helpers.storage")


class _DummyStore:
    def __init__(self, *_args, **_kwargs) -> None:
        pass


storage_module.Store = _DummyStore
sys.modules.setdefault("homeassistant", homeassistant_module)
sys.modules.setdefault("homeassistant.core", core_module)
sys.modules.setdefault("homeassistant.helpers", helpers_module)
sys.modules.setdefault("homeassistant.helpers.storage", storage_module)

from custom_components.brizel_health.core.users.brizel_user import BrizelUser
from custom_components.brizel_health.domains.body.models.body_measurement_entry import (
    BodyMeasurementEntry,
)
from custom_components.brizel_health.domains.body.models.body_goal import BodyGoal
from custom_components.brizel_health.domains.body.models.body_profile import BodyProfile
from custom_components.brizel_health.domains.nutrition.models.food_entry import (
    FoodEntry,
)
from custom_components.brizel_health.infrastructure.repositories.ha_body_goal_repository import (
    HomeAssistantBodyGoalRepository,
)
from custom_components.brizel_health.infrastructure.repositories.ha_body_measurement_repository import (
    HomeAssistantBodyMeasurementRepository,
)
from custom_components.brizel_health.infrastructure.repositories.ha_body_profile_repository import (
    HomeAssistantBodyProfileRepository,
)
from custom_components.brizel_health.infrastructure.repositories.ha_food_entry_repository import (
    HomeAssistantFoodEntryRepository,
)
from custom_components.brizel_health.infrastructure.repositories.ha_history_sync_journal_repository import (
    HomeAssistantHistorySyncJournalRepository,
)
from custom_components.brizel_health.infrastructure.repositories.ha_user_repository import (
    HomeAssistantUserRepository,
)
from custom_components.brizel_health.infrastructure.storage.store_manager import (
    get_default_storage_data,
)


class FakeStoreManager:
    """Tiny async-save store shim for repository tests."""

    def __init__(self) -> None:
        self.data = get_default_storage_data()
        self.save_count = 0

    async def async_save(self) -> None:
        self.save_count += 1


def test_user_repository_encrypts_profile_context_payload_at_rest() -> None:
    store_manager = FakeStoreManager()
    repository = HomeAssistantUserRepository(store_manager)
    user = BrizelUser.create(display_name="Alpha Example")

    asyncio.run(repository.add(user))

    stored = store_manager.data["profiles"][user.user_id]
    serialized = json.dumps(stored)

    assert "display_name" not in stored
    assert "Alpha Example" not in serialized
    assert isinstance(stored["encrypted_payload"], dict)

    loaded = repository.get_by_id(user.user_id)

    assert loaded.display_name == "Alpha Example"


def test_body_profile_repository_encrypts_stable_context_but_keeps_visible_fallbacks() -> None:
    store_manager = FakeStoreManager()
    repository = HomeAssistantBodyProfileRepository(store_manager)
    profile = BodyProfile.create(
        profile_id="profile-a",
        birth_date="1990-05-20",
        sex="female",
        activity_level="moderate",
        height_cm=180,
        weight_kg=81,
    )

    asyncio.run(repository.upsert(profile))

    stored = store_manager.data["body"]["profiles"]["profile-a"]
    serialized = json.dumps(stored)

    assert stored["height_cm"] == 180.0
    assert stored["weight_kg"] == 81.0
    assert "birth_date" not in stored
    assert "female" not in serialized
    assert "1990-05-20" not in serialized
    assert isinstance(stored["encrypted_payload"], dict)

    loaded = repository.get_by_profile_id("profile-a")

    assert loaded is not None
    assert loaded.birth_date == "1990-05-20"
    assert loaded.sex == "female"
    assert loaded.activity_level == "moderate"
    assert loaded.height_cm == 180.0
    assert loaded.weight_kg == 81.0


def test_body_measurement_payload_is_encrypted_at_rest_and_journal_stays_sync_compatible() -> None:
    store_manager = FakeStoreManager()
    repository = HomeAssistantBodyMeasurementRepository(store_manager)
    journal = HomeAssistantHistorySyncJournalRepository(store_manager)
    measurement = BodyMeasurementEntry.create(
        profile_id="profile-a",
        measurement_type="weight",
        canonical_value=82.5,
        measured_at="2026-04-23T07:30:00Z",
        note="Morning weight",
    )

    saved = asyncio.run(repository.add(measurement))

    stored = store_manager.data["body"]["measurements"][saved.record_id]
    serialized = json.dumps(stored)

    assert "measurement_type" not in stored
    assert "Morning weight" not in serialized
    assert "82.5" not in serialized
    assert isinstance(stored["encrypted_payload"], dict)

    peer_changes = journal.list_changes(
        domain="body_measurements",
        profile_id="profile-a",
        requesting_node_id="node-app-a",
    )

    assert len(peer_changes) == 1
    assert peer_changes[0].record["measurement_type"] == "weight"
    assert peer_changes[0].record["canonical_value"] == 82.5
    assert peer_changes[0].record["note"] == "Morning weight"

    same_node_changes = journal.list_changes(
        domain="body_measurements",
        profile_id="profile-a",
        requesting_node_id="home_assistant",
    )

    assert same_node_changes == ()

    cursor = journal.latest_cursor(domain="body_measurements", profile_id="profile-a")
    assert cursor is not None
    assert (
        journal.list_changes(
            domain="body_measurements",
            profile_id="profile-a",
            after_cursor=cursor,
            requesting_node_id="node-app-a",
        )
        == ()
    )

    loaded = repository.get_by_id(saved.record_id)
    assert loaded.measurement_type == "weight"
    assert loaded.note == "Morning weight"


def test_body_measurement_encrypted_payload_fails_cleanly_without_local_key_path() -> None:
    store_manager = FakeStoreManager()
    repository = HomeAssistantBodyMeasurementRepository(store_manager)
    measurement = BodyMeasurementEntry.create(
        profile_id="profile-a",
        measurement_type="weight",
        canonical_value=82.5,
        measured_at="2026-04-23T07:30:00Z",
        note="Morning weight",
    )

    saved = asyncio.run(repository.add(measurement))
    store_manager.data["security"]["metadata"]["key_envelopes"] = {}

    with pytest.raises(ValueError, match="Local direct-access envelope is missing"):
        repository.get_by_id(saved.record_id)


def test_body_goal_payload_is_encrypted_at_rest_and_journal_stays_sync_compatible() -> None:
    store_manager = FakeStoreManager()
    repository = HomeAssistantBodyGoalRepository(store_manager)
    journal = HomeAssistantHistorySyncJournalRepository(store_manager)
    goal = BodyGoal.create(
        profile_id="profile-a",
        target_weight_kg=74.5,
        note="Target for summer",
    )

    saved = asyncio.run(repository.upsert(goal))

    stored = store_manager.data["body"]["goals"][saved.record_id]
    serialized = json.dumps(stored)

    assert "goal_type" not in stored
    assert "target_value" not in stored
    assert "Target for summer" not in serialized
    assert "74.5" not in serialized
    assert isinstance(stored["encrypted_payload"], dict)

    peer_changes = journal.list_changes(
        domain="body_goals",
        profile_id="profile-a",
        requesting_node_id="node-app-a",
    )

    assert len(peer_changes) == 1
    assert peer_changes[0].record["goal_type"] == "target_weight"
    assert peer_changes[0].record["target_value"] == 74.5
    assert peer_changes[0].record["note"] == "Target for summer"

    same_node_changes = journal.list_changes(
        domain="body_goals",
        profile_id="profile-a",
        requesting_node_id="home_assistant",
    )

    assert same_node_changes == ()

    loaded = repository.get_by_profile_id("profile-a")
    assert loaded is not None
    assert loaded.goal_type == "target_weight"
    assert loaded.target_value == 74.5
    assert loaded.note == "Target for summer"


def test_food_log_payload_is_encrypted_at_rest_and_journal_stays_sync_compatible() -> None:
    store_manager = FakeStoreManager()
    repository = HomeAssistantFoodEntryRepository(store_manager)
    journal = HomeAssistantHistorySyncJournalRepository(store_manager)
    food_log = FoodEntry.from_dict(
        {
            "record_id": "food_log:profile-a:home_assistant:manual:apple-1",
            "record_type": "food_log",
            "profile_id": "profile-a",
            "source_type": "manual",
            "source_detail": "home_assistant",
            "origin_node_id": "home_assistant",
            "created_at": "2026-04-25T07:30:00Z",
            "updated_at": "2026-04-25T07:30:00Z",
            "updated_by_node_id": "home_assistant",
            "revision": 1,
            "payload_version": 1,
            "deleted_at": None,
            "food_id": "app_manual:orchard:apple",
            "food_name": "Apple",
            "food_brand": "Orchard",
            "amount_grams": 150,
            "meal_type": "snack",
            "note": "Morning snack",
            "consumed_at": "2026-04-25T07:30:00Z",
            "kcal": 78,
            "protein": 0.45,
            "carbs": 21,
            "fat": 0.3,
        }
    )

    saved = asyncio.run(repository.add(food_log))

    stored = store_manager.data["nutrition"]["food_entries"][saved.record_id]
    serialized = json.dumps(stored)

    assert "food_name" not in stored
    assert "amount_grams" not in stored
    assert "Morning snack" not in serialized
    assert "Apple" not in serialized
    assert isinstance(stored["encrypted_payload"], dict)

    peer_changes = journal.list_changes(
        domain="food_logs",
        profile_id="profile-a",
        requesting_node_id="node-app-a",
    )

    assert len(peer_changes) == 1
    assert peer_changes[0].record["food_name"] == "Apple"
    assert peer_changes[0].record["amount_grams"] == 150
    assert peer_changes[0].record["note"] == "Morning snack"

    same_node_changes = journal.list_changes(
        domain="food_logs",
        profile_id="profile-a",
        requesting_node_id="home_assistant",
    )

    assert same_node_changes == ()

    loaded = repository.get_food_entry_by_id(saved.record_id)
    assert loaded.food_name == "Apple"
    assert loaded.amount_grams == 150
    assert loaded.note == "Morning snack"
