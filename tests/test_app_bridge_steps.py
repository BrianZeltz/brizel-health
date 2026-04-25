"""Focused tests for the Brizel app bridge profiles and Fit steps slice."""

from __future__ import annotations

import asyncio
import sys
import types
from base64 import urlsafe_b64encode
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

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
    ERROR_JOIN_REQUEST_EXPIRED,
    ERROR_JOIN_REQUEST_STATE,
    BridgeValidationError,
    parse_body_measurement_peer_request,
    parse_join_request_create_request,
    parse_profile_context_sync_request,
    parse_sync_pull_request,
)
from custom_components.brizel_health.const import DATA_BRIZEL
from custom_components.brizel_health.application.fit.step_queries import (
    get_last_successful_steps_sync,
    resolve_steps_for_date,
    get_today_steps,
)
from custom_components.brizel_health.application.fit.step_use_cases import (
    import_step_entry,
)
from custom_components.brizel_health.application.body.body_measurement_use_cases import (
    add_body_measurement,
    delete_body_measurement,
)
from custom_components.brizel_health.application.body.body_goal_use_cases import (
    set_body_goal,
    delete_body_goal,
)
from custom_components.brizel_health.infrastructure.repositories.ha_step_repository import (
    HomeAssistantStepRepository,
)
from custom_components.brizel_health.infrastructure.repositories.ha_body_goal_repository import (
    HomeAssistantBodyGoalRepository,
)
from custom_components.brizel_health.infrastructure.repositories.ha_body_profile_repository import (
    HomeAssistantBodyProfileRepository,
)
from custom_components.brizel_health.infrastructure.repositories.ha_body_measurement_repository import (
    HomeAssistantBodyMeasurementRepository,
)
from custom_components.brizel_health.infrastructure.repositories.ha_food_entry_repository import (
    HomeAssistantFoodEntryRepository,
)
from custom_components.brizel_health.infrastructure.repositories.ha_history_sync_journal_repository import (
    HomeAssistantHistorySyncJournalRepository,
)
from custom_components.brizel_health.infrastructure.repositories.ha_key_hierarchy_repository import (
    HomeAssistantKeyHierarchyRepository,
)
from custom_components.brizel_health.domains.body.models.body_goal import BodyGoal
from custom_components.brizel_health.domains.nutrition.models.food_entry import (
    FoodEntry,
)
from custom_components.brizel_health.domains.security.models.key_hierarchy import (
    JoinEnrollmentRequest,
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

    def display_name_exists(
        self,
        display_name: str,
        exclude_user_id: str | None = None,
    ) -> bool:
        normalized_name = display_name.strip().casefold()
        for user_id, profile in self._profiles.items():
            if exclude_user_id is not None and user_id == exclude_user_id:
                continue
            if profile.display_name.strip().casefold() == normalized_name:
                return True
        return False

    async def update(self, user: FakeProfile) -> FakeProfile:
        self._profiles[user.user_id] = user
        return user


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
        storage: FakeStoreManager | None = None,
        user_repository: FakeUserRepository,
        step_repository: HomeAssistantStepRepository,
        body_goal_repository: HomeAssistantBodyGoalRepository | None = None,
        body_profile_repository: HomeAssistantBodyProfileRepository | None = None,
        body_measurement_repository: HomeAssistantBodyMeasurementRepository | None = None,
        food_entry_repository: HomeAssistantFoodEntryRepository | None = None,
        history_sync_journal_repository: (
            HomeAssistantHistorySyncJournalRepository | None
        ) = None,
        key_hierarchy_repository: HomeAssistantKeyHierarchyRepository | None = None,
    ) -> None:
        self.data = {
            DATA_BRIZEL: {
                "user_repository": user_repository,
                "step_repository": step_repository,
            }
        }
        if storage is not None:
            self.data[DATA_BRIZEL]["storage"] = storage
        if body_goal_repository is not None:
            self.data[DATA_BRIZEL]["body_goal_repository"] = body_goal_repository
        if body_profile_repository is not None:
            self.data[DATA_BRIZEL]["body_profile_repository"] = (
                body_profile_repository
            )
        if body_measurement_repository is not None:
            self.data[DATA_BRIZEL]["body_measurement_repository"] = (
                body_measurement_repository
            )
        if food_entry_repository is not None:
            self.data[DATA_BRIZEL]["food_entry_repository"] = food_entry_repository
        if history_sync_journal_repository is not None:
            self.data[DATA_BRIZEL]["history_sync_journal_repository"] = (
                history_sync_journal_repository
            )
        if key_hierarchy_repository is not None:
            self.data[DATA_BRIZEL]["key_hierarchy_repository"] = (
                key_hierarchy_repository
            )


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


def _profile_context_router(
    *,
    ha_user_id: str | None = "ha-user-a",
    profiles: list[FakeProfile] | None = None,
) -> tuple[
    BrizelAppBridgeRouter,
    HomeAssistantBodyProfileRepository,
]:
    store_manager = FakeStoreManager()
    step_repository = HomeAssistantStepRepository(store_manager)
    body_profile_repository = HomeAssistantBodyProfileRepository(store_manager)
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
            body_profile_repository=body_profile_repository,
        ),
        ha_user_id=ha_user_id,
    ), body_profile_repository


def _sync_router(
    *,
    ha_user_id: str | None = "ha-user-a",
    profiles: list[FakeProfile] | None = None,
) -> tuple[
    BrizelAppBridgeRouter,
    HomeAssistantStepRepository,
]:
    store_manager = FakeStoreManager()
    step_repository = HomeAssistantStepRepository(store_manager)
    body_profile_repository = HomeAssistantBodyProfileRepository(store_manager)
    body_goal_repository = HomeAssistantBodyGoalRepository(store_manager)
    body_measurement_repository = HomeAssistantBodyMeasurementRepository(
        store_manager
    )
    food_entry_repository = HomeAssistantFoodEntryRepository(store_manager)
    history_sync_journal_repository = HomeAssistantHistorySyncJournalRepository(
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
            body_profile_repository=body_profile_repository,
            body_goal_repository=body_goal_repository,
            body_measurement_repository=body_measurement_repository,
            food_entry_repository=food_entry_repository,
            history_sync_journal_repository=history_sync_journal_repository,
        ),
        ha_user_id=ha_user_id,
    ), step_repository


def _join_request_payload(
    *,
    profile_id: str | None = "profile-a",
    request_id: str = "join-request-1",
    requesting_node_id: str = "node-app-b",
    recipient_node_id: str = "node-app-b",
    recipient_key_id: str = "node-enroll-app-b",
    public_key_b64: str | None = None,
    requested_at: str = "2026-04-20T10:10:00Z",
    expires_at: str = "2099-04-20T11:10:00Z",
) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": "1.0",
        "message_id": f"{request_id}-message",
        "sent_at": requested_at,
        "request_id": request_id,
        "requested_at": requested_at,
        "expires_at": expires_at,
        "requesting_node_id": requesting_node_id,
        "recipient": {
            "node_id": recipient_node_id,
            "recipient_key_id": recipient_key_id,
            "key_version": 1,
            "algorithm": "node_enrollment_x25519_hkdf_sha256_v1",
            "public_key_b64": public_key_b64 or _fixed_base64url_bytes(b"r" * 32),
            "created_at": "2026-04-20T10:00:00Z",
            "updated_at": "2026-04-20T10:00:00Z",
        },
    }
    if profile_id is not None:
        body["profile_id"] = profile_id
    return body


def _join_action_payload(
    *,
    request_id: str,
    message_id: str,
    sent_at: str = "2026-04-20T10:15:00Z",
    approval_id: str | None = None,
    reason: str | None = None,
) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": "1.0",
        "message_id": message_id,
        "sent_at": sent_at,
        "request_id": request_id,
    }
    if approval_id is not None:
        body["approval_id"] = approval_id
    if reason is not None:
        body["reason"] = reason
    return body


def _join_router(
    *,
    ha_user_id: str | None = "ha-user-a",
    profiles: list[FakeProfile] | None = None,
) -> tuple[
    BrizelAppBridgeRouter,
    HomeAssistantKeyHierarchyRepository,
]:
    store_manager = FakeStoreManager()
    step_repository = HomeAssistantStepRepository(store_manager)
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
    key_hierarchy_repository = HomeAssistantKeyHierarchyRepository(store_manager)
    router = BrizelAppBridgeRouter(
        FakeHass(
            storage=store_manager,
            user_repository=user_repository,
            step_repository=step_repository,
            key_hierarchy_repository=key_hierarchy_repository,
        ),
        ha_user_id=ha_user_id,
    )
    return router, key_hierarchy_repository


def _fixed_base64url_bytes(value: bytes) -> str:
    return urlsafe_b64encode(value).decode("ascii").rstrip("=")


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
        "profile_context",
        "join_requests",
        "join_authorize",
        "join_complete",
        "join_invalidate",
        "sync_status",
        "sync_pull",
        "steps",
        "body_measurements",
        "body_goals",
        "food_logs",
    ]

    profiles = router.dispatch_get("profiles")
    assert profiles["ok"] is True
    assert profiles["profiles"] == [
        {
            "profile_id": "profile-a",
            "display_name": "Alpha",
            "is_default": False,
            "sex": None,
            "activity_level": None,
            "height_cm": None,
            "weight_kg": None,
            "birth_date": None,
            "date_of_birth": None,
            "age_years": None,
        },
    ]


def test_join_request_schema_requires_matching_requesting_node_and_recipient() -> None:
    with pytest.raises(BridgeValidationError) as error:
        parse_join_request_create_request(
            _join_request_payload(
                request_id="join-schema-mismatch",
                requesting_node_id="node-app-a",
                recipient_node_id="node-app-b",
            )
        )

    assert error.value.field_errors == {
        "requesting_node_id": "must_match_recipient_node_id"
    }


def test_join_request_create_authorize_complete_round_trip() -> None:
    router, _key_hierarchy_repository = _join_router()

    created = asyncio.run(
        router.dispatch_post(
            "join_requests",
            _join_request_payload(
                request_id="join-request-round-trip",
                recipient_key_id="node-enroll-round-trip",
                public_key_b64=_fixed_base64url_bytes(b"t" * 32),
            ),
        )
    )
    listed_pending = router.dispatch_get("join_requests")
    approved = asyncio.run(
        router.dispatch_post(
            "join_authorize",
            _join_action_payload(
                request_id="join-request-round-trip",
                message_id="join-authorize-round-trip",
            ),
        )
    )
    listed_approved = router.dispatch_get("join_requests")
    approval = approved["join_request"]["approval"]
    completed = asyncio.run(
        router.dispatch_post(
            "join_complete",
            _join_action_payload(
                request_id="join-request-round-trip",
                message_id="join-complete-round-trip",
                approval_id=approval["approval_id"],
            ),
        )
    )

    assert created["join_request"]["status"] == "pending"
    assert listed_pending["join_requests"][0]["status"] == "pending"
    assert approved["join_request"]["status"] == "approved"
    assert approval["approval_id"]
    assert approval["profile_key_algorithm"] == "profile_key_random_256_v1"
    assert approval["wrapped_key_material"]
    assert (
        approval["envelope"]["metadata"]["join_request_id"]
        == "join-request-round-trip"
    )
    assert (
        approval["envelope"]["metadata"]["join_requesting_node_id"] == "node-app-b"
    )
    assert listed_approved["join_requests"][0]["approval"]["approval_id"] == approval[
        "approval_id"
    ]
    assert completed["join_request"]["status"] == "completed"
    assert completed["join_request"]["completed_at"].endswith("Z")
    assert completed["join_request"]["approval"] is None


def test_join_request_create_reuses_existing_active_request_for_same_target_node() -> None:
    router, _key_hierarchy_repository = _join_router()

    first = asyncio.run(
        router.dispatch_post(
            "join_requests",
            _join_request_payload(
                request_id="join-request-active-1",
                requesting_node_id="node-app-active",
                recipient_node_id="node-app-active",
                recipient_key_id="node-enroll-active",
                public_key_b64=_fixed_base64url_bytes(b"a" * 32),
            ),
        )
    )
    second = asyncio.run(
        router.dispatch_post(
            "join_requests",
            _join_request_payload(
                request_id="join-request-active-2",
                requesting_node_id="node-app-active",
                recipient_node_id="node-app-active",
                recipient_key_id="node-enroll-active",
                public_key_b64=_fixed_base64url_bytes(b"a" * 32),
            ),
        )
    )
    listed = router.dispatch_get("join_requests")

    assert first["join_request"]["request_id"] == "join-request-active-1"
    assert second["join_request"]["request_id"] == "join-request-active-1"
    assert len(listed["join_requests"]) == 1
    assert listed["join_requests"][0]["status"] == "pending"


def test_join_request_create_after_completion_creates_new_active_request_and_lists_it_first() -> None:
    router, _key_hierarchy_repository = _join_router()

    asyncio.run(
        router.dispatch_post(
            "join_requests",
            _join_request_payload(
                request_id="join-request-completed-old",
                requesting_node_id="node-app-join",
                recipient_node_id="node-app-join",
                recipient_key_id="node-enroll-join",
                public_key_b64=_fixed_base64url_bytes(b"j" * 32),
            ),
        )
    )
    approved = asyncio.run(
        router.dispatch_post(
            "join_authorize",
            _join_action_payload(
                request_id="join-request-completed-old",
                message_id="join-authorize-completed-old",
            ),
        )
    )
    asyncio.run(
        router.dispatch_post(
            "join_complete",
            _join_action_payload(
                request_id="join-request-completed-old",
                message_id="join-complete-completed-old",
                approval_id=approved["join_request"]["approval"]["approval_id"],
            ),
        )
    )

    created = asyncio.run(
        router.dispatch_post(
            "join_requests",
            _join_request_payload(
                request_id="join-request-pending-new",
                requesting_node_id="node-app-join",
                recipient_node_id="node-app-join",
                recipient_key_id="node-enroll-join",
                public_key_b64=_fixed_base64url_bytes(b"j" * 32),
            ),
        )
    )
    listed = router.dispatch_get("join_requests")

    assert created["join_request"]["request_id"] == "join-request-pending-new"
    assert created["join_request"]["status"] == "pending"
    assert [request["request_id"] for request in listed["join_requests"]] == [
        "join-request-pending-new",
        "join-request-completed-old",
    ]
    assert [request["status"] for request in listed["join_requests"]] == [
        "pending",
        "completed",
    ]


def test_join_authorize_rejects_expired_request() -> None:
    router, key_hierarchy_repository = _join_router()
    expired_request = JoinEnrollmentRequest(
        request_id="join-expired-1",
        profile_id="profile-a",
        requesting_node_id="node-app-expired",
        recipient=parse_join_request_create_request(
            _join_request_payload(
                request_id="join-expired-1",
                requesting_node_id="node-app-expired",
                recipient_node_id="node-app-expired",
                recipient_key_id="node-enroll-expired",
                public_key_b64=_fixed_base64url_bytes(b"e" * 32),
                requested_at="2026-04-20T10:10:00Z",
                expires_at="2026-04-20T10:20:00Z",
            )
        ).recipient,
        requested_at=datetime(2026, 4, 20, 10, 10, tzinfo=UTC),
        expires_at=datetime(2026, 4, 20, 10, 20, tzinfo=UTC),
        status="pending",
    )
    asyncio.run(key_hierarchy_repository.create_join_request(expired_request))

    with pytest.raises(BridgeDomainError) as error:
        asyncio.run(
            router.dispatch_post(
                "join_authorize",
                _join_action_payload(
                    request_id="join-expired-1",
                    message_id="join-authorize-expired",
                    sent_at="2026-04-20T10:30:00Z",
                ),
            )
        )

    assert error.value.error_code == ERROR_JOIN_REQUEST_EXPIRED
    assert error.value.status_code == 409


def test_join_requests_list_surfaces_expired_requests_as_terminal() -> None:
    router, key_hierarchy_repository = _join_router()
    expired_request = JoinEnrollmentRequest(
        request_id="join-expired-listed",
        profile_id="profile-a",
        requesting_node_id="node-app-expired-listed",
        recipient=parse_join_request_create_request(
            _join_request_payload(
                request_id="join-expired-listed",
                requesting_node_id="node-app-expired-listed",
                recipient_node_id="node-app-expired-listed",
                recipient_key_id="node-enroll-expired-listed",
                public_key_b64=_fixed_base64url_bytes(b"x" * 32),
                requested_at="2026-04-20T10:10:00Z",
                expires_at="2026-04-20T10:20:00Z",
            )
        ).recipient,
        requested_at=datetime(2026, 4, 20, 10, 10, tzinfo=UTC),
        expires_at=datetime(2026, 4, 20, 10, 20, tzinfo=UTC),
        status="pending",
    )
    asyncio.run(key_hierarchy_repository.create_join_request(expired_request))

    listed = router.dispatch_get("join_requests")

    assert listed["join_requests"][0]["request_id"] == "join-expired-listed"
    assert listed["join_requests"][0]["status"] == "expired"


def test_join_request_invalidate_blocks_later_authorize() -> None:
    router, _key_hierarchy_repository = _join_router()
    asyncio.run(
        router.dispatch_post(
            "join_requests",
            _join_request_payload(
                request_id="join-request-invalidated",
                recipient_key_id="node-enroll-invalidated",
                public_key_b64=_fixed_base64url_bytes(b"i" * 32),
            ),
        )
    )

    invalidated = asyncio.run(
        router.dispatch_post(
            "join_invalidate",
            _join_action_payload(
                request_id="join-request-invalidated",
                message_id="join-invalidate-invalidated",
                reason="manual_rejection",
            ),
        )
    )

    with pytest.raises(BridgeDomainError) as error:
        asyncio.run(
            router.dispatch_post(
                "join_authorize",
                _join_action_payload(
                    request_id="join-request-invalidated",
                    message_id="join-authorize-invalidated",
                ),
            )
        )

    assert invalidated["join_request"]["status"] == "invalidated"
    assert invalidated["join_request"]["invalidation_reason"] == "manual_rejection"
    assert error.value.error_code == ERROR_JOIN_REQUEST_STATE
    assert error.value.status_code == 409


def test_join_authorize_is_idempotent_for_already_approved_request() -> None:
    router, _key_hierarchy_repository = _join_router()
    asyncio.run(
        router.dispatch_post(
            "join_requests",
            _join_request_payload(
                request_id="join-request-approved-twice",
                recipient_key_id="node-enroll-approved-twice",
                public_key_b64=_fixed_base64url_bytes(b"p" * 32),
            ),
        )
    )

    first = asyncio.run(
        router.dispatch_post(
            "join_authorize",
            _join_action_payload(
                request_id="join-request-approved-twice",
                message_id="join-authorize-approved-twice-1",
            ),
        )
    )
    second = asyncio.run(
        router.dispatch_post(
            "join_authorize",
            _join_action_payload(
                request_id="join-request-approved-twice",
                message_id="join-authorize-approved-twice-2",
            ),
        )
    )

    assert first["join_request"]["status"] == "approved"
    assert second["join_request"]["status"] == "approved"
    assert (
        first["join_request"]["approval"]["approval_id"]
        == second["join_request"]["approval"]["approval_id"]
    )


def test_join_complete_rejects_wrong_approval_binding() -> None:
    router, _key_hierarchy_repository = _join_router()
    asyncio.run(
        router.dispatch_post(
            "join_requests",
            _join_request_payload(
                request_id="join-request-binding",
                recipient_key_id="node-enroll-binding",
                public_key_b64=_fixed_base64url_bytes(b"b" * 32),
            ),
        )
    )
    approved = asyncio.run(
        router.dispatch_post(
            "join_authorize",
            _join_action_payload(
                request_id="join-request-binding",
                message_id="join-authorize-binding",
            ),
        )
    )

    with pytest.raises(BridgeDomainError) as error:
        asyncio.run(
            router.dispatch_post(
                "join_complete",
                _join_action_payload(
                    request_id="join-request-binding",
                    message_id="join-complete-binding",
                    approval_id="wrong-approval-id",
                ),
            )
        )

    assert approved["join_request"]["approval"]["approval_id"]
    assert error.value.error_code == ERROR_JOIN_REQUEST_STATE
    assert error.value.field_errors == {"approval_id": "mismatch"}


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


def test_profile_context_sync_updates_body_context_and_returns_effective_profile() -> None:
    router, body_profile_repository = _profile_context_router()

    result = asyncio.run(
        router.dispatch_post(
            "profile_context",
            {
                "schema_version": "1.0",
                "message_id": "profile-context-1",
                "sent_at": "2026-04-20T10:10:00Z",
                "updated_at": "2026-04-20T10:10:00Z",
                "updated_by_node_id": "node-app-1",
                "profile_id": "profile-a",
                "payload": {
                    "display_name": "Alpha",
                    "birth_date": "1990-05-20",
                    "sex": "female",
                    "activity_level": "moderate",
                },
            },
        )
    )

    assert result["ok"] is True
    assert result["applied"] == {
        "display_name": False,
        "birth_date": True,
        "sex": True,
        "activity_level": False,
    }
    assert result["profile"]["profile_id"] == "profile-a"
    assert result["profile"]["display_name"] == "Alpha"
    assert result["profile"]["birth_date"] == "1990-05-20"
    assert result["profile"]["date_of_birth"] == "1990-05-20"
    assert result["profile"]["sex"] == "female"

    stored = body_profile_repository.get_by_profile_id("profile-a")
    assert stored is not None
    assert stored.birth_date == "1990-05-20"
    assert stored.sex == "female"


def test_profile_context_sync_rejects_foreign_profile_id() -> None:
    router, _body_profile_repository = _profile_context_router()

    with pytest.raises(BridgeDomainError) as error:
        asyncio.run(
            router.dispatch_post(
                "profile_context",
                {
                    "schema_version": "1.0",
                    "message_id": "profile-context-foreign",
                    "sent_at": "2026-04-20T10:10:00Z",
                    "updated_at": "2026-04-20T10:10:00Z",
                    "updated_by_node_id": "node-app-1",
                    "profile_id": "profile-b",
                    "payload": {
                        "display_name": "Beta",
                        "birth_date": "1990-05-20",
                        "sex": "female",
                        "activity_level": "moderate",
                    },
                },
            )
        )

    assert error.value.error_code == ERROR_PROFILE_ACCESS_DENIED
    assert error.value.status_code == 403


def test_sync_pull_returns_incremental_domain_deltas_from_cursors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router, _step_repository = _sync_router()
    monkeypatch.setattr(bridge_router, "async_dispatcher_send", lambda *args: None)

    asyncio.run(
        router.handle_steps_import(
            _v1_step_payload(
                message_id="step-record-1",
                record_id="steps:profile-a:node-123:raw:health_connect:1",
                updated_at="2026-04-18T10:10:00Z",
            )
        )
    )
    asyncio.run(
        router.handle_steps_import(
            _v1_step_payload(
                message_id="step-record-2",
                record_id="steps:profile-a:node-123:raw:health_connect:2",
                updated_at="2026-04-18T11:10:00Z",
            )
        )
    )
    asyncio.run(
        router.handle_body_measurement_peer_upsert(
            _body_measurement_payload(measurement_type="weight")
        )
    )
    asyncio.run(router.handle_body_goal_peer_upsert(_body_goal_payload()))
    asyncio.run(router.handle_food_log_peer_upsert(_food_log_payload()))

    first_pull = asyncio.run(
        router.dispatch_post(
            "sync_pull",
            {
                "schema_version": "1.0",
                "message_id": "sync-pull-1",
                "sent_at": "2026-04-20T10:10:00Z",
                "profile_id": "profile-a",
                "cursors": {
                    "steps": {"updated_after": None},
                    "body_measurements": {"updated_after": None},
                    "body_goals": {"updated_after": None},
                    "food_logs": {"updated_after": None},
                },
            },
        )
    )

    assert first_pull["ok"] is True
    assert len(first_pull["domains"]["steps"]["records"]) == 2
    assert len(first_pull["domains"]["body_measurements"]["records"]) == 1
    assert len(first_pull["domains"]["body_goals"]["records"]) == 1
    assert len(first_pull["domains"]["food_logs"]["records"]) == 1
    assert first_pull["domains"]["steps"]["cursor"] is not None
    assert first_pull["domains"]["body_measurements"]["cursor"] is not None
    assert first_pull["domains"]["body_goals"]["cursor"] is not None
    assert first_pull["domains"]["food_logs"]["cursor"] is not None

    second_pull = asyncio.run(
        router.dispatch_post(
            "sync_pull",
            {
                "schema_version": "1.0",
                "message_id": "sync-pull-2",
                "sent_at": "2026-04-20T10:12:00Z",
                "profile_id": "profile-a",
                "cursors": {
                    "steps": {
                        "cursor": first_pull["domains"]["steps"]["cursor"]
                    },
                    "body_measurements": {
                        "cursor": first_pull["domains"]["body_measurements"]["cursor"]
                    },
                    "body_goals": {
                        "cursor": first_pull["domains"]["body_goals"]["cursor"]
                    },
                    "food_logs": {
                        "cursor": first_pull["domains"]["food_logs"]["cursor"]
                    },
                },
            },
        )
    )

    assert second_pull["ok"] is True
    assert second_pull["domains"]["steps"]["records"] == []
    assert second_pull["domains"]["body_measurements"]["records"] == []
    assert second_pull["domains"]["body_goals"]["records"] == []
    assert second_pull["domains"]["food_logs"]["records"] == []


def test_sync_pull_filters_requesting_node_echo_from_journal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router, _step_repository = _sync_router()
    monkeypatch.setattr(bridge_router, "async_dispatcher_send", lambda *args: None)

    asyncio.run(
        router.handle_steps_import(
            _v1_step_payload(
                message_id="step-record-echo",
                record_id="steps:profile-a:node-app-1:raw:health_connect:echo",
                origin_node_id="node-app-1",
                updated_at="2026-04-18T10:10:00Z",
            )
        )
    )

    result = asyncio.run(
        router.dispatch_post(
            "sync_pull",
            {
                "schema_version": "1.0",
                "message_id": "sync-pull-echo",
                "sent_at": "2026-04-20T10:10:00Z",
                "profile_id": "profile-a",
                "requesting_node_id": "node-app-1",
                "cursors": {
                    "steps": {"updated_after": None},
                    "body_measurements": {"updated_after": None},
                    "body_goals": {"updated_after": None},
                    "food_logs": {"updated_after": None},
                },
            },
        )
    )

    assert result["ok"] is True
    assert result["domains"]["steps"]["records"] == []
    assert result["domains"]["steps"]["cursor"] is not None


def test_sync_pull_does_not_backfill_canonical_records_without_journal_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store_manager = FakeStoreManager()
    step_repository = HomeAssistantStepRepository(store_manager)
    body_profile_repository = HomeAssistantBodyProfileRepository(store_manager)
    body_goal_repository = HomeAssistantBodyGoalRepository(store_manager)
    body_measurement_repository = HomeAssistantBodyMeasurementRepository(store_manager)
    food_entry_repository = HomeAssistantFoodEntryRepository(store_manager)
    history_sync_journal_repository = HomeAssistantHistorySyncJournalRepository(
        store_manager
    )
    user_repository = FakeUserRepository(
        [FakeProfile(user_id="profile-a", display_name="Alpha", linked_ha_user_id="ha-user-a")]
    )
    router = BrizelAppBridgeRouter(
        FakeHass(
            user_repository=user_repository,
            step_repository=step_repository,
            body_profile_repository=body_profile_repository,
            body_goal_repository=body_goal_repository,
            body_measurement_repository=body_measurement_repository,
            food_entry_repository=food_entry_repository,
            history_sync_journal_repository=history_sync_journal_repository,
        ),
        ha_user_id="ha-user-a",
    )
    monkeypatch.setattr(bridge_router, "async_dispatcher_send", lambda *args: None)

    asyncio.run(
        router.handle_steps_import(
            _v1_step_payload(
                message_id="step-record-no-backfill",
                record_id="steps:profile-a:node-ha-1:raw:health_connect:no-backfill",
                origin_node_id="node-ha-1",
                updated_at="2026-04-18T10:10:00Z",
            )
        )
    )
    store_manager.data["sync"]["history_journal"] = {
        "next_sequence": 1,
        "entries": [],
        "fingerprints": {},
    }

    pull = asyncio.run(
        router.dispatch_post(
            "sync_pull",
            {
                "schema_version": "1.0",
                "message_id": "sync-pull-no-backfill",
                "sent_at": "2026-04-20T10:10:00Z",
                "profile_id": "profile-a",
                "cursors": {
                    "steps": {"updated_after": None},
                    "body_measurements": {"updated_after": None},
                    "body_goals": {"updated_after": None},
                    "food_logs": {"updated_after": None},
                },
            },
        )
    )

    assert pull["ok"] is True
    assert pull["domains"]["steps"]["records"] == []
    assert pull["domains"]["steps"]["cursor"] is None


def test_sync_pull_returns_empty_follow_up_after_processed_echo_cursor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router, _step_repository = _sync_router()
    monkeypatch.setattr(bridge_router, "async_dispatcher_send", lambda *args: None)

    asyncio.run(
        router.handle_steps_import(
            _v1_step_payload(
                message_id="step-record-echo-follow-up",
                record_id="steps:profile-a:node-app-1:raw:health_connect:follow-up",
                origin_node_id="node-app-1",
                updated_at="2026-04-18T10:10:00Z",
            )
        )
    )

    first_pull = asyncio.run(
        router.dispatch_post(
            "sync_pull",
            {
                "schema_version": "1.0",
                "message_id": "sync-pull-echo-follow-up-1",
                "sent_at": "2026-04-20T10:10:00Z",
                "profile_id": "profile-a",
                "requesting_node_id": "node-app-1",
                "cursors": {
                    "steps": {"updated_after": None},
                    "body_measurements": {"updated_after": None},
                    "body_goals": {"updated_after": None},
                    "food_logs": {"updated_after": None},
                },
            },
        )
    )

    second_pull = asyncio.run(
        router.dispatch_post(
            "sync_pull",
            {
                "schema_version": "1.0",
                "message_id": "sync-pull-echo-follow-up-2",
                "sent_at": "2026-04-20T10:12:00Z",
                "profile_id": "profile-a",
                "requesting_node_id": "node-app-1",
                "cursors": {
                    "steps": {"cursor": first_pull["domains"]["steps"]["cursor"]},
                    "body_measurements": {
                        "cursor": first_pull["domains"]["body_measurements"]["cursor"]
                    },
                    "body_goals": {
                        "cursor": first_pull["domains"]["body_goals"]["cursor"]
                    },
                    "food_logs": {
                        "cursor": first_pull["domains"]["food_logs"]["cursor"]
                    },
                },
            },
        )
    )

    assert first_pull["domains"]["steps"]["records"] == []
    assert first_pull["domains"]["steps"]["cursor"] is not None
    assert second_pull["ok"] is True
    assert second_pull["domains"]["steps"]["records"] == []
    assert second_pull["domains"]["steps"]["cursor"] == first_pull["domains"]["steps"]["cursor"]


def test_sync_pull_rejects_foreign_profile_id() -> None:
    router, _step_repository = _sync_router()

    with pytest.raises(BridgeDomainError) as error:
        asyncio.run(
            router.dispatch_post(
                "sync_pull",
                {
                    "schema_version": "1.0",
                    "message_id": "sync-pull-foreign",
                    "sent_at": "2026-04-20T10:10:00Z",
                    "profile_id": "profile-b",
                    "cursors": {
                        "steps": {"updated_after": None},
                        "body_measurements": {"updated_after": None},
                        "body_goals": {"updated_after": None},
                        "food_logs": {"updated_after": None},
                    },
                },
            )
        )

    assert error.value.error_code == ERROR_PROFILE_ACCESS_DENIED
    assert error.value.status_code == 403


def test_direct_step_write_journalizes_before_pull() -> None:
    store_manager = FakeStoreManager()
    step_repository = HomeAssistantStepRepository(store_manager)
    journal_repository = HomeAssistantHistorySyncJournalRepository(store_manager)

    result = asyncio.run(
        import_step_entry(
            repository=step_repository,
            external_record_id="steps-2026-04-18-0900-1000",
            profile_id="profile-a",
            message_id="message-local-step-1",
            device_id="node-ha-1",
            source="home_assistant",
            start="2026-04-18T09:00:00Z",
            end="2026-04-18T10:00:00Z",
            steps=1234,
            updated_at="2026-04-18T10:10:00Z",
            updated_by_node_id="node-ha-1",
            source_type="manual",
            source_detail="home_assistant",
            origin_node_id="node-ha-1",
            record_id="steps:profile-a:node-ha-1:manual:local-1",
        )
    )

    changes = journal_repository.list_changes(
        domain="steps",
        profile_id="profile-a",
    )

    assert result.imported == 1
    assert journal_repository.latest_cursor(domain="steps", profile_id="profile-a") == "1"
    assert len(changes) == 1
    assert changes[0].record["record_id"] == "steps:profile-a:node-ha-1:manual:local-1"


def test_direct_body_measurement_delete_journalizes_tombstone() -> None:
    store_manager = FakeStoreManager()
    repository = HomeAssistantBodyMeasurementRepository(store_manager)
    user_repository = FakeUserRepository(
        [FakeProfile(user_id="profile-a", display_name="Alpha")]
    )
    journal_repository = HomeAssistantHistorySyncJournalRepository(store_manager)

    created = asyncio.run(
        add_body_measurement(
            repository,
            user_repository,
            profile_id="profile-a",
            measurement_type="weight",
            value=72.5,
        )
    )
    asyncio.run(
        delete_body_measurement(
            repository,
            measurement_id=created.record_id,
        )
    )

    tombstones = journal_repository.list_changes(
        domain="body_measurements",
        profile_id="profile-a",
        after_cursor="1",
    )

    assert journal_repository.latest_cursor(
        domain="body_measurements",
        profile_id="profile-a",
    ) == "2"
    assert len(tombstones) == 1
    assert tombstones[0].record["record_id"] == created.record_id
    assert tombstones[0].record["deleted_at"] is not None


def test_direct_body_goal_updates_advance_journal_sequence() -> None:
    store_manager = FakeStoreManager()
    repository = HomeAssistantBodyGoalRepository(store_manager)
    user_repository = FakeUserRepository(
        [FakeProfile(user_id="profile-a", display_name="Alpha")]
    )
    journal_repository = HomeAssistantHistorySyncJournalRepository(store_manager)

    first = asyncio.run(
        set_body_goal(
            repository,
            user_repository,
            "profile-a",
            75,
        )
    )
    second = asyncio.run(
        set_body_goal(
            repository,
            user_repository,
            "profile-a",
            74,
        )
    )

    follow_up = journal_repository.list_changes(
        domain="body_goals",
        profile_id="profile-a",
        after_cursor="1",
    )

    assert first.target_value == 75.0
    assert second.target_value == 74.0
    assert journal_repository.latest_cursor(domain="body_goals", profile_id="profile-a") == "2"
    assert len(follow_up) == 1
    assert follow_up[0].record["record_id"] == "body_goal:profile-a:target_weight"
    assert follow_up[0].record["target_value"] == 74.0


def test_direct_food_log_delete_journalizes_tombstone() -> None:
    store_manager = FakeStoreManager()
    repository = HomeAssistantFoodEntryRepository(store_manager)
    journal_repository = HomeAssistantHistorySyncJournalRepository(store_manager)

    created = asyncio.run(
        repository.add(
            FoodEntry.from_dict(
                {
                    "record_id": "food_log:profile-a:node-ha-1:manual:apple-1",
                    "record_type": "food_log",
                    "profile_id": "profile-a",
                    "source_type": "manual",
                    "source_detail": "home_assistant",
                    "origin_node_id": "node-ha-1",
                    "created_at": "2026-04-18T10:10:00Z",
                    "updated_at": "2026-04-18T10:10:00Z",
                    "updated_by_node_id": "node-ha-1",
                    "revision": 1,
                    "payload_version": 1,
                    "deleted_at": None,
                    "food_id": "internal:apple",
                    "food_name": "Apple",
                    "food_brand": None,
                    "amount_grams": 150,
                    "grams": 150,
                    "meal_type": "snack",
                    "note": None,
                    "consumed_at": "2026-04-18T10:00:00Z",
                    "kcal": 78,
                    "protein": 0.3,
                    "carbs": 20.0,
                    "fat": 0.2,
                }
            )
        )
    )
    asyncio.run(repository.delete(created.record_id))

    follow_up = journal_repository.list_changes(
        domain="food_logs",
        profile_id="profile-a",
        after_cursor="1",
    )

    assert journal_repository.latest_cursor(domain="food_logs", profile_id="profile-a") == "2"
    assert len(follow_up) == 1
    assert follow_up[0].record["record_id"] == created.record_id
    assert follow_up[0].record["deleted_at"] is not None


def test_history_journal_compacts_superseded_revisions_but_keeps_latest_state() -> None:
    store_manager = FakeStoreManager()
    journal_repository = HomeAssistantHistorySyncJournalRepository(store_manager)
    base_timestamp = datetime(2026, 4, 18, 10, 0, tzinfo=UTC)

    for revision in range(1, 2201):
        updated_at = base_timestamp + timedelta(minutes=revision)
        asyncio.run(
            journal_repository.record_snapshot(
                domain="steps",
                profile_id="profile-a",
                records=[
                    {
                        "record_id": "steps:profile-a:node-ha-1:manual:local-1",
                        "updated_at": updated_at.isoformat().replace("+00:00", "Z"),
                        "updated_by_node_id": "node-ha-1",
                        "revision": revision,
                        "deleted_at": None,
                        "step_count": revision,
                    }
                ],
                serialize_record=lambda record: dict(record),
            )
        )

    changes = journal_repository.list_changes(
        domain="steps",
        profile_id="profile-a",
        after_cursor="1",
    )

    assert journal_repository.latest_cursor(domain="steps", profile_id="profile-a") == "2200"
    assert len(changes) < 1000
    assert changes[0].sequence > 1
    assert changes[-1].record["revision"] == 2200
    assert changes[-1].record["step_count"] == 2200


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


def test_profile_context_sync_schema_parses_stable_context_payload() -> None:
    request = parse_profile_context_sync_request(
        {
            "schema_version": "1.0",
            "message_id": "profile-context-schema-1",
            "sent_at": "2026-04-20T10:10:00Z",
            "updated_at": "2026-04-20T10:11:00Z",
            "updated_by_node_id": "node-app-1",
            "profile_id": "profile-a",
            "payload": {
                "display_name": "Alpha",
                "birth_date": "1990-05-20",
                "date_of_birth": "1990-05-20",
                "sex": "female",
                "activity_level": "moderate",
            },
        }
    )

    assert request.profile_id == "profile-a"
    assert request.display_name == "Alpha"
    assert request.birth_date == "1990-05-20"
    assert request.date_of_birth == "1990-05-20"
    assert request.sex == "female"
    assert request.activity_level == "moderate"


def test_profile_context_sync_schema_requires_payload_display_name() -> None:
    with pytest.raises(BridgeValidationError) as error:
        parse_profile_context_sync_request(
            {
                "schema_version": "1.0",
                "message_id": "profile-context-schema-2",
                "sent_at": "2026-04-20T10:10:00Z",
                "updated_at": "2026-04-20T10:11:00Z",
                "updated_by_node_id": "node-app-1",
                "profile_id": "profile-a",
                "payload": {
                    "birth_date": "1990-05-20",
                },
            }
        )

    assert error.value.field_errors == {"payload.display_name": "required"}


def test_sync_pull_schema_parses_domain_cursors() -> None:
    request = parse_sync_pull_request(
        {
            "schema_version": "1.0",
            "message_id": "sync-pull-schema-1",
            "sent_at": "2026-04-20T10:10:00Z",
                "profile_id": "profile-a",
                "requesting_node_id": "node-app-1",
                "cursors": {
                "steps": {
                    "updated_after": "2026-04-20T09:00:00Z",
                    "cursor": "42",
                },
                "body_measurements": {"updated_after": None},
                "body_goals": {"updated_after": "2026-04-20T09:30:00Z"},
                "food_logs": {"updated_after": None},
            },
        }
    )

    assert request.profile_id == "profile-a"
    assert request.requesting_node_id == "node-app-1"
    assert request.cursors["steps"] is not None
    assert request.journal_cursors["steps"] == "42"
    assert request.cursors["body_measurements"] is None
    assert request.cursors["body_goals"] is not None
    assert request.cursors["food_logs"] is None


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
