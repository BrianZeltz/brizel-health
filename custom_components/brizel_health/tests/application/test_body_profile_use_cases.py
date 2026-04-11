"""Tests for body profile use cases."""

from __future__ import annotations

import pytest

from custom_components.brizel_health.application.body.body_profile_use_cases import (
    get_body_profile,
    upsert_body_profile,
)
from custom_components.brizel_health.core.users.brizel_user import BrizelUser
from custom_components.brizel_health.core.users.errors import BrizelUserNotFoundError
from custom_components.brizel_health.domains.body.models.body_profile import (
    ACTIVITY_LEVEL_MODERATE,
    SEX_FEMALE,
    BodyProfile,
)


class InMemoryUserRepository:
    """Simple user repository for body profile tests."""

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


class InMemoryBodyProfileRepository:
    """Simple body profile repository for application tests."""

    def __init__(self, profiles: list[BodyProfile] | None = None) -> None:
        self._profiles = {
            profile.profile_id: profile for profile in profiles or []
        }

    async def upsert(self, body_profile: BodyProfile) -> BodyProfile:
        self._profiles[body_profile.profile_id] = body_profile
        return body_profile

    def get_by_profile_id(self, profile_id: str) -> BodyProfile | None:
        return self._profiles.get(profile_id)


def _user_repository() -> InMemoryUserRepository:
    return InMemoryUserRepository(
        [
            BrizelUser(
                user_id="profile-1",
                display_name="Alice",
                linked_ha_user_id=None,
                created_at="2026-04-08T08:00:00+00:00",
            )
        ]
    )


def test_get_body_profile_returns_empty_model_for_existing_profile_without_data() -> None:
    """Reading body data should return an empty body profile when nothing is stored."""
    profile = get_body_profile(
        repository=InMemoryBodyProfileRepository(),
        user_repository=_user_repository(),
        profile_id=" profile-1 ",
    )

    assert profile.profile_id == "profile-1"
    assert profile.is_empty() is True


@pytest.mark.asyncio
async def test_upsert_body_profile_persists_validated_profile_data() -> None:
    """Upsert should validate and persist the current body data state."""
    repository = InMemoryBodyProfileRepository()

    body_profile = await upsert_body_profile(
        repository=repository,
        user_repository=_user_repository(),
        profile_id="profile-1",
        age_years=34,
        sex=SEX_FEMALE,
        height_cm=170,
        weight_kg=65,
        activity_level=ACTIVITY_LEVEL_MODERATE,
    )

    assert body_profile.profile_id == "profile-1"
    assert body_profile.age_years == 34
    assert body_profile.sex == SEX_FEMALE
    assert body_profile.height_cm == 170.0
    assert body_profile.weight_kg == 65.0
    assert body_profile.activity_level == ACTIVITY_LEVEL_MODERATE
    assert repository.get_by_profile_id("profile-1") is body_profile


@pytest.mark.asyncio
async def test_upsert_body_profile_can_clear_existing_values() -> None:
    """Body profile upsert should replace fields so empty values can be stored intentionally."""
    repository = InMemoryBodyProfileRepository(
        [
            BodyProfile.create(
                profile_id="profile-1",
                age_years=34,
                sex=SEX_FEMALE,
                height_cm=170,
                weight_kg=65,
                activity_level=ACTIVITY_LEVEL_MODERATE,
            )
        ]
    )

    body_profile = await upsert_body_profile(
        repository=repository,
        user_repository=_user_repository(),
        profile_id="profile-1",
    )

    assert body_profile.profile_id == "profile-1"
    assert body_profile.is_empty() is True
