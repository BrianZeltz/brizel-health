"""Tests for the Home Assistant body profile repository."""

from __future__ import annotations

import pytest

from custom_components.brizel_health.domains.body.models.body_profile import (
    ACTIVITY_LEVEL_LIGHT,
    SEX_FEMALE,
    BodyProfile,
)
from custom_components.brizel_health.infrastructure.repositories.ha_body_profile_repository import (
    HomeAssistantBodyProfileRepository,
)


class FakeStoreManager:
    """Minimal store manager stub for body profile repository tests."""

    def __init__(self, data: dict) -> None:
        self.data = data
        self.save_calls = 0

    async def async_save(self) -> None:
        self.save_calls += 1


@pytest.mark.asyncio
async def test_repository_upsert_persists_body_profile_under_profile_id() -> None:
    """Body profile repository should persist profile-scoped body data."""
    store_manager = FakeStoreManager({})
    repository = HomeAssistantBodyProfileRepository(store_manager)
    body_profile = BodyProfile.create(
        profile_id="profile-1",
        age_years=31,
        sex=SEX_FEMALE,
        height_cm=168,
        weight_kg=62,
        activity_level=ACTIVITY_LEVEL_LIGHT,
    )

    stored = await repository.upsert(body_profile)

    assert stored.profile_id == "profile-1"
    assert (
        "weight_kg" not in store_manager.data["body"]["profiles"]["profile-1"]
    )
    assert (
        "height_cm" not in store_manager.data["body"]["profiles"]["profile-1"]
    )
    assert store_manager.save_calls >= 1


def test_repository_get_by_profile_id_returns_none_when_missing() -> None:
    """Reading a missing body profile should return None instead of failing."""
    repository = HomeAssistantBodyProfileRepository(FakeStoreManager({}))

    assert repository.get_by_profile_id("profile-1") is None


def test_repository_get_by_profile_id_parses_persisted_body_profile() -> None:
    """Stored body profile data should be parsed back into the domain model."""
    repository = HomeAssistantBodyProfileRepository(
        FakeStoreManager(
            {
                "body": {
                    "profiles": {
                        "profile-1": {
                            "profile_id": "profile-1",
                            "age_years": 31,
                            "sex": "female",
                            "height_cm": 168,
                            "weight_kg": 62,
                            "activity_level": "light",
                        }
                    }
                }
            }
        )
    )

    body_profile = repository.get_by_profile_id("profile-1")

    assert body_profile is not None
    assert body_profile.profile_id == "profile-1"
    assert body_profile.height_cm == 168.0
