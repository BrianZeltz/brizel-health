"""Focused tests for the Brizel app bridge profiles and Fit steps slice."""

from __future__ import annotations

import asyncio
import sys
import types
from dataclasses import dataclass
from datetime import UTC, date

import pytest

homeassistant_module = types.ModuleType("homeassistant")
helpers_module = types.ModuleType("homeassistant.helpers")
dispatcher_module = types.ModuleType("homeassistant.helpers.dispatcher")
dispatcher_module.async_dispatcher_send = lambda *args: None
sys.modules.setdefault("homeassistant", homeassistant_module)
sys.modules.setdefault("homeassistant.helpers", helpers_module)
sys.modules.setdefault("homeassistant.helpers.dispatcher", dispatcher_module)

from custom_components.brizel_health.adapters.homeassistant import bridge_router
from custom_components.brizel_health.adapters.homeassistant.bridge_router import (
    BridgeDomainError,
    BrizelAppBridgeRouter,
)
from custom_components.brizel_health.adapters.homeassistant.bridge_schemas import (
    ERROR_PROFILE_ACCESS_DENIED,
    ERROR_PROFILE_LINK_AMBIGUOUS,
    ERROR_PROFILE_NOT_LINKED,
    parse_body_measurement_peer_request,
)
from custom_components.brizel_health.const import DATA_BRIZEL
from custom_components.brizel_health.application.fit.step_queries import (
    get_last_successful_steps_sync,
    resolve_steps_for_date,
    get_today_steps,
)
from custom_components.brizel_health.infrastructure.repositories.ha_step_repository import (
    HomeAssistantStepRepository,
)
from custom_components.brizel_health.infrastructure.repositories.ha_body_goal_repository import (
    HomeAssistantBodyGoalRepository,
)
from custom_components.brizel_health.infrastructure.repositories.ha_body_measurement_repository import (
    HomeAssistantBodyMeasurementRepository,
)
from custom_components.brizel_health.infrastructure.repositories.ha_food_entry_repository import (
    HomeAssistantFoodEntryRepository,
)
from custom_components.brizel_health.domains.body.models.body_goal import BodyGoal
from custom_components.brizel_health.domains.nutrition.models.food_entry import (
    FoodEntry,
)


@dataclass(frozen=True)
class FakeProfile:
    """Small profile object matching the fields used by bridge serialization."""

    user_id: str
    display_name: str
    linked_ha_user_id: str | None = None


class FakeUserRepository:
    """Minimal in-memory user repository for bridge tests."""

    def __init__(self, profiles: list[FakeProfile]) -> None:
        self._profiles = {profile.user_id: profile for profile in profiles}

    def get_by_id(self, user_id: str) -> FakeProfile:
        return self._profiles[user_id]

    def get_all(self) -> list[FakeProfile]:
        return list(self._profiles.values())


class FakeStoreManager:
    """Store manager shim used by the HA step repository."""

    def __init__(self) -> None:
        self.data = {
            "body": {
                "goals": {},
                "measurements": {},
            },
            "fit": {
                "steps_by_profile": {},
                "steps_import_state_by_profile": {},
            },
            "nutrition": {
                "food_entries": {},
            },
        }
        self.save_count = 0

    async def async_save(self) -> None:
        self.save_count += 1


class FakeHass:
    """Small hass-like object carrying integration runtime data."""

    def __init__(
        self,
        *,
        user_repository: FakeUserRepository,
        step_repository: HomeAssistantStepRepository,
        body_goal_repository: HomeAssistantBodyGoalRepository | None = None,
        body_measurement_repository: HomeAssistantBodyMeasurementRepository | None = None,
        food_entry_repository: HomeAssistantFoodEntryRepository | None = None,
    ) -> None:
        self.data = {
            DATA_BRIZEL: {
                "user_repository": user_repository,
                "step_repository": step_repository,
            }
        }
        if body_goal_repository is not None:
            self.data[DATA_BRIZEL]["body_goal_repository"] = body_goal_repository
        if body_measurement_repository is not None:
            self.data[DATA_BRIZEL]["body_measurement_repository"] = (
                body_measurement_repository
            )
        if food_entry_repository is not None:
            self.data[DATA_BRIZEL]["food_entry_repository"] = food_entry_repository


def _step_payload(
    *,
    profile_id: str | None = "profile-a",
    message_id: str = "message-1",
    external_record_id: str = "steps-2026-04-18-0900-1000",
    steps: int = 1240,
) -> dict[str, object]:
    payload = {
        "external_record_id": external_record_id,
        "start": "2026-04-18T09:00:00Z",
        "end": "2026-04-18T10:00:00Z",
        "steps": steps,
        "timezone": "Europe/Berlin",
        "origin": "phone_sensor",
    }
    if profile_id is not None:
        payload["profile_id"] = profile_id

    return {
        "schema_version": "1.0",
        "message_id": message_id,
        "device_id": "android-device-123",
        "source": "brizel_health_android",
        "sent_at": "2026-04-18T10:10:00Z",
        "payload": payload,
    }


def _v1_step_payload(
    *,
    profile_id: str | None = "profile-a",
    message_id: str = "message-1",
    record_id: str = (
        "steps:profile-a:node-123:raw:"
        "com.google.android.apps.fitness:hc-record-1"
    ),
    origin_node_id: str = "node-123",
    step_count: int = 1240,
    updated_at: str = "2026-04-18T10:10:00Z",
    measurement_start: str = "2026-04-18T08:00:00Z",
    measurement_end: str = "2026-04-18T09:00:00Z",
    data_origin: str = "com.google.android.apps.fitness",
) -> dict[str, object]:
    payload = {
        "measurement_start": measurement_start,
        "measurement_end": measurement_end,
        "step_count": step_count,
        "timezone": "Europe/Berlin",
        "read_mode": "raw",
        "data_origin": data_origin,
    }

    body: dict[str, object] = {
        "schema_version": "1.0",
        "message_id": message_id,
        "sent_at": updated_at,
        "record_id": record_id,
        "record_type": "steps",
        "origin_node_id": origin_node_id,
        "created_at": "2026-04-18T10:10:00Z",
        "updated_at": updated_at,
        "updated_by_node_id": origin_node_id,
        "revision": 1,
        "payload_version": 1,
        "deleted_at": None,
        "source_type": "device_import",
        "source_detail": "health_connect",
        "payload": payload,
    }
    if profile_id is not None:
        body["profile_id"] = profile_id
    return body


def _body_goal_payload(
    *,
    profile_id: str | None = "profile-a",
    message_id: str = "goal-message-1",
    target_value: float = 75.0,
    revision: int = 1,
    updated_at: str = "2026-04-18T10:10:00Z",
    deleted_at: str | None = None,
    updated_by_node_id: str = "node-app-1",
) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": "1.0",
        "message_id": message_id,
        "sent_at": updated_at,
        "record_id": "body_goal:profile-a:target_weight",
        "record_type": "body_goal",
        "origin_node_id": "node-app-1",
        "created_at": "2026-04-18T10:10:00Z",
        "updated_at": updated_at,
        "updated_by_node_id": updated_by_node_id,
        "revision": revision,
        "payload_version": 1,
        "deleted_at": deleted_at,
        "source_type": "manual",
        "source_detail": "app_manual",
        "payload": {
            "goal_type": "target_weight",
            "target_value": target_value,
            "note": "mobile target",
        },
    }
    if profile_id is not None:
        body["profile_id"] = profile_id
    return body


def _body_measurement_payload(
    *,
    measurement_type: str,
    profile_id: str | None = "profile-a",
) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": "1.0",
        "message_id": f"measurement-message-{measurement_type}",
        "sent_at": "2026-04-18T10:10:00Z",
        "record_id": f"body_measurement:profile-a:node-app-1:manual:{measurement_type}",
        "record_type": "body_measurement",
        "origin_node_id": "node-app-1",
        "created_at": "2026-04-18T10:10:00Z",
        "updated_at": "2026-04-18T10:10:00Z",
        "updated_by_node_id": "node-app-1",
        "revision": 1,
        "payload_version": 1,
        "deleted_at": None,
        "source_type": "manual",
        "source_detail": "app_manual",
        "payload": {
            "measurement_type": measurement_type,
            "canonical_value": 88.5,
            "measured_at": "2026-04-18T07:30:00Z",
            "note": "mobile body measurement",
        },
    }
    if profile_id is not None:
        body["profile_id"] = profile_id
    return body


def _food_log_payload(
    *,
    profile_id: str | None = "profile-a",
    message_id: str = "food-log-message-1",
    record_id: str = "food_log:profile-a:node-app-1:manual:apple-1",
    revision: int = 1,
    updated_at: str = "2026-04-18T10:10:00Z",
    updated_by_node_id: str = "node-app-1",
    deleted_at: str | None = None,
    amount_grams: float = 150,
    kcal: float = 78,
) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": "1.0",
        "message_id": message_id,
        "sent_at": updated_at,
        "record_id": record_id,
        "record_type": "food_log",
        "origin_node_id": "node-app-1",
        "created_at": "2026-04-18T10:10:00Z",
        "updated_at": updated_at,
        "updated_by_node_id": updated_by_node_id,
        "revision": revision,
        "payload_version": 1,
        "deleted_at": deleted_at,
        "source_type": "manual",
        "source_detail": "app_manual",
        "payload": {
            "consumed_at": "2026-04-18T07:30:00Z",
            "food_id": "app_manual:apple",
            "food_name": "Apple",
            "food_brand": "Orchard",
            "amount_grams": amount_grams,
            "meal_type": "snack",
            "note": "mobile food log",
            "kcal": kcal,
            "protein": 0.45,
            "carbs": 21,
            "fat": 0.3,
        },
    }
    if profile_id is not None:
        body["profile_id"] = profile_id
    return body


def _router(
    *,
    ha_user_id: str | None = "ha-user-a",
    profiles: list[FakeProfile] | None = None,
) -> tuple[BrizelAppBridgeRouter, HomeAssistantStepRepository]:
    store_manager = FakeStoreManager()
    step_repository = HomeAssistantStepRepository(store_manager)
    body_goal_repository = HomeAssistantBodyGoalRepository(store_manager)
    user_repository = FakeUserRepository(
        profiles
        if profiles is not None
        else [
            FakeProfile(
                user_id="profile-b",
                display_name="Beta",
                linked_ha_user_id="ha-user-b",
            ),
            FakeProfile(
                user_id="profile-a",
                display_name="Alpha",
                linked_ha_user_id="ha-user-a",
            ),
        ]
    )
    return BrizelAppBridgeRouter(
        FakeHass(
            user_repository=user_repository,
            step_repository=step_repository,
            body_goal_repository=body_goal_repository,
        ),
        ha_user_id=ha_user_id,
    ), step_repository


def _body_goal_router(
    *,
    ha_user_id: str | None = "ha-user-a",
    profiles: list[FakeProfile] | None = None,
) -> tuple[BrizelAppBridgeRouter, HomeAssistantBodyGoalRepository]:
    store_manager = FakeStoreManager()
    step_repository = HomeAssistantStepRepository(store_manager)
    body_goal_repository = HomeAssistantBodyGoalRepository(store_manager)
    user_repository = FakeUserRepository(
        profiles
        if profiles is not None
        else [
            FakeProfile(
                user_id="profile-b",
                display_name="Beta",
                linked_ha_user_id="ha-user-b",
            ),
            FakeProfile(
                user_id="profile-a",
                display_name="Alpha",
                linked_ha_user_id="ha-user-a",
            ),
        ]
    )
    return BrizelAppBridgeRouter(
        FakeHass(
            user_repository=user_repository,
            step_repository=step_repository,
            body_goal_repository=body_goal_repository,
        ),
        ha_user_id=ha_user_id,
    ), body_goal_repository


def _body_measurement_router(
    *,
    ha_user_id: str | None = "ha-user-a",
    profiles: list[FakeProfile] | None = None,
) -> tuple[BrizelAppBridgeRouter, HomeAssistantBodyMeasurementRepository]:
    store_manager = FakeStoreManager()
    step_repository = HomeAssistantStepRepository(store_manager)
    body_measurement_repository = HomeAssistantBodyMeasurementRepository(
        store_manager
    )
    user_repository = FakeUserRepository(
        profiles
        if profiles is not None
        else [
            FakeProfile(
                user_id="profile-b",
                display_name="Beta",
                linked_ha_user_id="ha-user-b",
            ),
            FakeProfile(
                user_id="profile-a",
                display_name="Alpha",
                linked_ha_user_id="ha-user-a",
            ),
        ]
    )
    return BrizelAppBridgeRouter(
        FakeHass(
            user_repository=user_repository,
            step_repository=step_repository,
            body_measurement_repository=body_measurement_repository,
        ),
        ha_user_id=ha_user_id,
    ), body_measurement_repository


def _food_log_router(
    *,
    ha_user_id: str | None = "ha-user-a",
    profiles: list[FakeProfile] | None = None,
) -> tuple[BrizelAppBridgeRouter, HomeAssistantFoodEntryRepository]:
    store_manager = FakeStoreManager()
    step_repository = HomeAssistantStepRepository(store_manager)
    food_entry_repository = HomeAssistantFoodEntryRepository(store_manager)
    user_repository = FakeUserRepository(
        profiles
        if profiles is not None
        else [
            FakeProfile(
                user_id="profile-b",
                display_name="Beta",
                linked_ha_user_id="ha-user-b",
            ),
            FakeProfile(
                user_id="profile-a",
                display_name="Alpha",
                linked_ha_user_id="ha-user-a",
            ),
        ]
    )
    return BrizelAppBridgeRouter(
        FakeHass(
            user_repository=user_repository,
            step_repository=step_repository,
            food_entry_repository=food_entry_repository,
        ),
        ha_user_id=ha_user_id,
    ), food_entry_repository


def test_ping_capabilities_and_profiles_are_user_bound_bridge_responses() -> None:
    router, _step_repository = _router()

    ping = router.dispatch_get("ping")
    assert ping["ok"] is True
    assert ping["bridge_version"] == "1.0"

    capabilities = router.dispatch_get("capabilities")
    assert capabilities["ok"] is True
    assert capabilities["profiles_available"] is True
    assert capabilities["steps_import_available"] is True
    assert capabilities["available_endpoints"] == [
        "ping",
        "capabilities",
        "profiles",
        "sync_status",
        "steps",
        "body_measurements",
        "body_goals",
        "food_logs",
    ]

    profiles = router.dispatch_get("profiles")
    assert profiles["ok"] is True
    assert profiles["profiles"] == [
        {"profile_id": "profile-a", "display_name": "Alpha", "is_default": False},
    ]


def test_profiles_requires_linked_home_assistant_user() -> None:
    router, _step_repository = _router(ha_user_id="ha-user-missing")

    with pytest.raises(BridgeDomainError) as error:
        router.dispatch_get("profiles")

    assert error.value.error_code == ERROR_PROFILE_NOT_LINKED
    assert error.value.status_code == 403


def test_profiles_rejects_ambiguous_home_assistant_user_link() -> None:
    router, _step_repository = _router(
        profiles=[
            FakeProfile(
                user_id="profile-a",
                display_name="Alpha",
                linked_ha_user_id="ha-user-a",
            ),
            FakeProfile(
                user_id="profile-b",
                display_name="Beta",
                linked_ha_user_id="ha-user-a",
            ),
        ]
    )

    with pytest.raises(BridgeDomainError) as error:
        router.dispatch_get("profiles")

    assert error.value.error_code == ERROR_PROFILE_LINK_AMBIGUOUS
    assert error.value.status_code == 409


def test_steps_import_uses_linked_profile_when_payload_profile_is_missing() -> None:
    router, _step_repository = _router()

    result = asyncio.run(router.handle_steps_import(_step_payload(profile_id=None)))

    assert result["result"] == {"imported": 1, "updated": 0, "ignored_duplicates": 0}


def test_body_goals_returns_target_weight_goal_for_linked_profile() -> None:
    router, body_goal_repository = _body_goal_router()
    asyncio.run(
        body_goal_repository.upsert(
            BodyGoal.create(profile_id="profile-a", target_weight_kg=75)
        )
    )

    result = router.dispatch_get("body_goals")

    assert result["ok"] is True
    assert result["record_type"] == "body_goal"
    assert result["goal_type"] == "target_weight"
    assert result["profile_id"] == "profile-a"
    assert result["records"][0]["record_id"] == "body_goal:profile-a:target_weight"
    assert result["records"][0]["target_value"] == 75.0


@pytest.mark.parametrize(
    "measurement_type",
    (
        "weight",
        "height",
        "waist",
        "abdomen",
        "hip",
        "chest",
        "upper_arm",
        "forearm",
        "thigh",
        "calf",
        "neck",
    ),
)
def test_body_measurement_peer_schema_accepts_expansion_types(
    measurement_type: str,
) -> None:
    request = parse_body_measurement_peer_request(
        _body_measurement_payload(measurement_type=measurement_type)
    )

    assert request.measurement_type == measurement_type
    assert request.record_type == "body_measurement"
    assert request.profile_id == "profile-a"


def test_body_measurement_bridge_round_trips_all_supported_types() -> None:
    router, _body_measurement_repository = _body_measurement_router()
    expected_types = {
        "weight",
        "height",
        "waist",
        "abdomen",
        "hip",
        "chest",
        "upper_arm",
        "forearm",
        "thigh",
        "calf",
        "neck",
    }

    for measurement_type in expected_types:
        result = asyncio.run(
            router.handle_body_measurement_peer_upsert(
                _body_measurement_payload(
                    measurement_type=measurement_type,
                    profile_id=None,
                )
            )
        )
        assert result["record"]["measurement_type"] == measurement_type

    response = router.dispatch_get("body_measurements")

    assert set(response["measurement_types"]) == expected_types
    assert {
        record["measurement_type"]
        for record in response["records"]
    } == expected_types


def test_body_goal_peer_upsert_updates_and_preserves_tombstone() -> None:
    router, body_goal_repository = _body_goal_router()

    first = asyncio.run(router.handle_body_goal_peer_upsert(_body_goal_payload()))
    updated = asyncio.run(
        router.handle_body_goal_peer_upsert(
            _body_goal_payload(
                message_id="goal-message-2",
                target_value=74.0,
                revision=2,
                updated_at="2026-04-18T11:10:00Z",
            )
        )
    )
    deleted = asyncio.run(
        router.handle_body_goal_peer_upsert(
            _body_goal_payload(
                message_id="goal-message-3",
                target_value=74.0,
                revision=3,
                updated_at="2026-04-18T12:10:00Z",
                deleted_at="2026-04-18T12:10:00Z",
            )
        )
    )
    goal = body_goal_repository.get_by_profile_id(
        "profile-a",
        include_deleted=True,
    )

    assert first["result"] == {"imported": 1, "updated": 0, "ignored": 0}
    assert updated["result"] == {"imported": 0, "updated": 1, "ignored": 0}
    assert deleted["result"] == {"imported": 0, "updated": 1, "ignored": 0}
    assert goal is not None
    assert goal.record_id == "body_goal:profile-a:target_weight"
    assert goal.target_value == 74.0
    assert goal.revision == 3
    assert goal.deleted_at is not None
    assert body_goal_repository.get_by_profile_id("profile-a") is None


def test_body_goal_peer_upsert_rejects_foreign_profile_id() -> None:
    router, _body_goal_repository = _body_goal_router()

    with pytest.raises(BridgeDomainError) as error:
        asyncio.run(
            router.handle_body_goal_peer_upsert(
                _body_goal_payload(profile_id="profile-b")
            )
        )

    assert error.value.error_code == ERROR_PROFILE_ACCESS_DENIED
    assert error.value.status_code == 403


def test_body_goal_peer_upsert_rejects_invalid_record_identity() -> None:
    router, _body_goal_repository = _body_goal_router()
    payload = _body_goal_payload(profile_id=None)
    payload["record_id"] = "body_goal:profile-b:target_weight"

    with pytest.raises(BridgeDomainError) as error:
        asyncio.run(router.handle_body_goal_peer_upsert(payload))

    assert error.value.error_code == "INVALID_PAYLOAD"
    assert error.value.status_code == 409


def test_food_logs_returns_food_log_records_for_linked_profile() -> None:
    router, food_entry_repository = _food_log_router()
    asyncio.run(
        food_entry_repository.add(
            FoodEntry.from_dict(
                {
                    "record_id": "food_log:profile-a:node-app-1:manual:apple-1",
                    "record_type": "food_log",
                    "profile_id": "profile-a",
                    "source_type": "manual",
                    "source_detail": "app_manual",
                    "origin_node_id": "node-app-1",
                    "created_at": "2026-04-18T10:10:00Z",
                    "updated_at": "2026-04-18T10:10:00Z",
                    "updated_by_node_id": "node-app-1",
                    "revision": 1,
                    "payload_version": 1,
                    "deleted_at": None,
                    "food_id": "app_manual:apple",
                    "food_name": "Apple",
                    "food_brand": "Orchard",
                    "amount_grams": 150,
                    "meal_type": "snack",
                    "note": "mobile food log",
                    "consumed_at": "2026-04-18T07:30:00Z",
                    "kcal": 78,
                    "protein": 0.45,
                    "carbs": 21,
                    "fat": 0.3,
                }
            )
        )
    )

    result = router.dispatch_get("food_logs")

    assert result["ok"] is True
    assert result["record_type"] == "food_log"
    assert result["profile_id"] == "profile-a"
    assert result["records"][0]["record_id"] == (
        "food_log:profile-a:node-app-1:manual:apple-1"
    )
    assert result["records"][0]["food_name"] == "Apple"
    assert result["records"][0]["amount_grams"] == 150.0


def test_food_log_peer_upsert_updates_and_preserves_tombstone() -> None:
    router, food_entry_repository = _food_log_router()

    first = asyncio.run(router.handle_food_log_peer_upsert(_food_log_payload()))
    updated = asyncio.run(
        router.handle_food_log_peer_upsert(
            _food_log_payload(
                message_id="food-log-message-2",
                revision=2,
                updated_at="2026-04-18T11:10:00Z",
                amount_grams=175,
                kcal=91,
            )
        )
    )
    deleted = asyncio.run(
        router.handle_food_log_peer_upsert(
            _food_log_payload(
                message_id="food-log-message-3",
                revision=3,
                updated_at="2026-04-18T12:10:00Z",
                deleted_at="2026-04-18T12:10:00Z",
                amount_grams=175,
                kcal=91,
            )
        )
    )
    records = food_entry_repository.get_all_food_entries(include_deleted=True)

    assert first["result"] == {"imported": 1, "updated": 0, "ignored": 0}
    assert updated["result"] == {"imported": 0, "updated": 1, "ignored": 0}
    assert deleted["result"] == {"imported": 0, "updated": 1, "ignored": 0}
    assert len(records) == 1
    assert records[0].record_id == "food_log:profile-a:node-app-1:manual:apple-1"
    assert records[0].amount_grams == 175.0
    assert records[0].kcal == 91.0
    assert records[0].revision == 3
    assert records[0].deleted_at is not None
    assert food_entry_repository.get_all_food_entries() == []


def test_food_log_peer_upsert_rejects_foreign_profile_id() -> None:
    router, _food_entry_repository = _food_log_router()

    with pytest.raises(BridgeDomainError) as error:
        asyncio.run(
            router.handle_food_log_peer_upsert(
                _food_log_payload(profile_id="profile-b")
            )
        )

    assert error.value.error_code == ERROR_PROFILE_ACCESS_DENIED
    assert error.value.status_code == 403


def test_steps_import_rejects_foreign_profile_id() -> None:
    router, _step_repository = _router()

    with pytest.raises(BridgeDomainError) as error:
        asyncio.run(router.handle_steps_import(_step_payload(profile_id="profile-b")))

    assert error.value.error_code == ERROR_PROFILE_ACCESS_DENIED
    assert error.value.status_code == 403
    assert error.value.field_errors == {"payload.profile_id": "not_allowed"}


def test_app_bridge_steps_import_persists_profile_scoped_fit_entries_and_duplicate_ignore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router, step_repository = _router()
    monkeypatch.setattr(bridge_router, "async_dispatcher_send", lambda *args: None)

    first = asyncio.run(router.handle_steps_import(_step_payload()))
    duplicate = asyncio.run(
        router.handle_steps_import(
            _step_payload(message_id="message-duplicate"),
        )
    )

    assert first["result"] == {"imported": 1, "updated": 0, "ignored_duplicates": 0}
    assert duplicate["result"] == {
        "imported": 0,
        "updated": 0,
        "ignored_duplicates": 1,
    }
    assert len(step_repository.list_step_entries("profile-a")) == 1
    assert len(step_repository.list_step_entries("profile-b")) == 0
    legacy_resolution = resolve_steps_for_date(
        repository=step_repository,
        profile_id="profile-a",
        target_date=date(2026, 4, 18),
        time_zone=UTC,
    )
    assert legacy_resolution.total_steps == 0
    assert legacy_resolution.discarded_records[0].reason == "legacy_read_mode"
    assert (
        get_last_successful_steps_sync(
            repository=step_repository,
            profile_id="profile-a",
        )
        is not None
    )


def test_v1_same_raw_node_record_updates_revision_instead_of_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router, step_repository = _router()
    monkeypatch.setattr(bridge_router, "async_dispatcher_send", lambda *args: None)
    first = asyncio.run(router.handle_steps_import(_v1_step_payload()))
    updated = asyncio.run(
        router.handle_steps_import(
            _v1_step_payload(
                message_id="message-2",
                step_count=1400,
                updated_at="2026-04-18T11:10:00Z",
            )
        )
    )

    entries = step_repository.list_step_entries("profile-a")

    assert first["result"] == {"imported": 1, "updated": 0, "ignored_duplicates": 0}
    assert updated["result"] == {"imported": 0, "updated": 1, "ignored_duplicates": 0}
    assert len(entries) == 1
    assert entries[0].record_id == (
        "steps:profile-a:node-123:raw:"
        "com.google.android.apps.fitness:hc-record-1"
    )
    assert entries[0].record_type == "steps"
    assert entries[0].origin_node_id == "node-123"
    assert entries[0].updated_by_node_id == "node-123"
    assert entries[0].source_type == "device_import"
    assert entries[0].source_detail == "health_connect"
    assert entries[0].payload_version == 1
    assert entries[0].deleted_at is None
    assert entries[0].read_mode == "raw"
    assert entries[0].data_origin == "com.google.android.apps.fitness"
    assert entries[0].steps == 1400
    assert entries[0].revision == 2


def test_sync_status_reports_profile_scoped_fit_steps_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router, _step_repository = _router()
    monkeypatch.setattr(bridge_router, "async_dispatcher_send", lambda *args: None)
    asyncio.run(router.handle_steps_import(_step_payload()))

    status = router.dispatch_get("sync_status")

    assert status["ok"] is True
    assert status["bridge_version"] == "1.0"
    assert status["profiles"][0]["profile_id"] == "profile-a"
    assert status["profiles"][0]["last_steps_sync"].endswith("Z")
    assert status["profiles"][0]["last_steps_import_status"] == "success"
    assert len(status["profiles"]) == 1


def test_step_resolver_prefers_higher_priority_overlapping_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router, step_repository = _router()
    monkeypatch.setattr(bridge_router, "async_dispatcher_send", lambda *args: None)

    asyncio.run(
        router.handle_steps_import(
            _v1_step_payload(
                message_id="garmin-1",
                record_id="steps:profile-a:node-1:raw:garmin:1",
                origin_node_id="node-1",
                step_count=1200,
                data_origin="com.garmin.android.apps.connectmobile",
            )
        )
    )
    asyncio.run(
        router.handle_steps_import(
            _v1_step_payload(
                message_id="google-1",
                record_id="steps:profile-a:node-2:raw:google-fit:1",
                origin_node_id="node-2",
                step_count=1300,
                data_origin="android",
            )
        )
    )

    resolution = resolve_steps_for_date(
        repository=step_repository,
        profile_id="profile-a",
        target_date=date(2026, 4, 18),
        time_zone=UTC,
    )

    assert resolution.total_steps == 1200
    assert resolution.used_sources == ("com.garmin.android.apps.connectmobile",)
    assert resolution.discarded_sources == ("android",)
    assert resolution.discarded_records[0].reason == "overlap_lower_priority"
    assert (
        get_today_steps(
            repository=step_repository,
            profile_id="profile-a",
            today=date(2026, 4, 18),
            time_zone=UTC,
        )
        == 1200
    )


def test_step_resolver_adds_non_overlapping_raw_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router, step_repository = _router()
    monkeypatch.setattr(bridge_router, "async_dispatcher_send", lambda *args: None)

    asyncio.run(
        router.handle_steps_import(
            _v1_step_payload(
                message_id="garmin-morning",
                record_id="steps:profile-a:node-1:raw:garmin:morning",
                step_count=1200,
                data_origin="com.garmin.android.apps.connectmobile",
                measurement_start="2026-04-18T08:00:00Z",
                measurement_end="2026-04-18T09:00:00Z",
            )
        )
    )
    asyncio.run(
        router.handle_steps_import(
            _v1_step_payload(
                message_id="fitbit-noon",
                record_id="steps:profile-a:node-2:raw:fitbit:noon",
                origin_node_id="node-2",
                step_count=900,
                data_origin="com.fitbit.FitbitMobile",
                measurement_start="2026-04-18T12:00:00Z",
                measurement_end="2026-04-18T13:00:00Z",
            )
        )
    )

    assert (
        get_today_steps(
            repository=step_repository,
            profile_id="profile-a",
            today=date(2026, 4, 18),
            time_zone=UTC,
        )
        == 2100
    )


def test_step_resolver_uses_profile_source_priority_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router, step_repository = _router()
    monkeypatch.setattr(bridge_router, "async_dispatcher_send", lambda *args: None)
    asyncio.run(
        step_repository.set_step_source_priority(
            "profile-a",
            ("com.google.android.apps.fitness", "garmin"),
        )
    )
    asyncio.run(
        router.handle_steps_import(
            _v1_step_payload(
                message_id="garmin-1",
                record_id="steps:profile-a:node-1:raw:garmin:1",
                origin_node_id="node-1",
                step_count=1200,
                data_origin="com.garmin.android.apps.connectmobile",
            )
        )
    )
    asyncio.run(
        router.handle_steps_import(
            _v1_step_payload(
                message_id="google-1",
                record_id="steps:profile-a:node-2:raw:google-fit:1",
                origin_node_id="node-2",
                step_count=1300,
                data_origin="com.google.android.apps.fitness",
            )
        )
    )

    resolution = resolve_steps_for_date(
        repository=step_repository,
        profile_id="profile-a",
        target_date=date(2026, 4, 18),
        time_zone=UTC,
    )

    assert resolution.total_steps == 1300
    assert resolution.used_sources == ("com.google.android.apps.fitness",)
    assert resolution.discarded_sources == ("com.garmin.android.apps.connectmobile",)


def test_step_resolver_timeline_uses_measurement_time_not_import_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router, step_repository = _router()
    monkeypatch.setattr(bridge_router, "async_dispatcher_send", lambda *args: None)
    asyncio.run(
        router.handle_steps_import(
            _v1_step_payload(
                message_id="late-import",
                record_id="steps:profile-a:node-1:raw:garmin:late-import",
                step_count=1200,
                updated_at="2026-04-18T23:30:00Z",
                data_origin="com.garmin.android.apps.connectmobile",
                measurement_start="2026-04-18T08:00:00Z",
                measurement_end="2026-04-18T09:00:00Z",
            )
        )
    )

    resolution = resolve_steps_for_date(
        repository=step_repository,
        profile_id="profile-a",
        target_date=date(2026, 4, 18),
        time_zone=UTC,
    )

    assert resolution.timeline[0].measurement_start.hour == 8
    assert resolution.timeline[0].measurement_end.hour == 9
    assert resolution.timeline[0].step_count == 1200
