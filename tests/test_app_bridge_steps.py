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
    ERROR_CONFLICTING_RECORD,
    ERROR_PROFILE_ACCESS_DENIED,
    ERROR_PROFILE_LINK_AMBIGUOUS,
    ERROR_PROFILE_NOT_LINKED,
)
from custom_components.brizel_health.const import DATA_BRIZEL
from custom_components.brizel_health.application.fit.step_queries import (
    get_last_successful_steps_sync,
    get_today_steps,
)
from custom_components.brizel_health.infrastructure.repositories.ha_step_repository import (
    HomeAssistantStepRepository,
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
            "fit": {
                "steps_by_profile": {},
                "steps_import_state_by_profile": {},
            }
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
    ) -> None:
        self.data = {
            DATA_BRIZEL: {
                "user_repository": user_repository,
                "step_repository": step_repository,
            }
        }


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


def _router(
    *,
    ha_user_id: str | None = "ha-user-a",
    profiles: list[FakeProfile] | None = None,
) -> tuple[BrizelAppBridgeRouter, HomeAssistantStepRepository]:
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
    return BrizelAppBridgeRouter(
        FakeHass(
            user_repository=user_repository,
            step_repository=step_repository,
        ),
        ha_user_id=ha_user_id,
    ), step_repository


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
    assert (
        get_today_steps(
            repository=step_repository,
            profile_id="profile-a",
            today=date(2026, 4, 18),
            time_zone=UTC,
        )
        == 1240
    )
    assert (
        get_last_successful_steps_sync(
            repository=step_repository,
            profile_id="profile-a",
        )
        is not None
    )


def test_conflicting_duplicate_is_not_overwritten(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router, step_repository = _router()
    monkeypatch.setattr(bridge_router, "async_dispatcher_send", lambda *args: None)
    asyncio.run(router.handle_steps_import(_step_payload()))

    with pytest.raises(BridgeDomainError) as error:
        asyncio.run(
            router.handle_steps_import(
                _step_payload(
                    message_id="message-2",
                    steps=999,
                )
            )
        )

    assert error.value.error_code == ERROR_CONFLICTING_RECORD
    assert step_repository.list_step_entries("profile-a")[0].steps == 1240


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
