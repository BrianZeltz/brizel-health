"""Tests for body target queries."""

from __future__ import annotations

import pytest

from custom_components.brizel_health.application.body.body_target_queries import (
    get_body_targets,
)
from custom_components.brizel_health.core.users.brizel_user import BrizelUser
from custom_components.brizel_health.core.users.errors import BrizelUserNotFoundError
from custom_components.brizel_health.domains.body.models.body_profile import (
    ACTIVITY_LEVEL_ACTIVE,
    ACTIVITY_LEVEL_LIGHT,
    ACTIVITY_LEVEL_MODERATE,
    ACTIVITY_LEVEL_SEDENTARY,
    ACTIVITY_LEVEL_VERY_ACTIVE,
    SEX_MALE,
    BodyProfile,
)


class InMemoryUserRepository:
    """Simple user repository for body target tests."""

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
    """Simple body profile repository for target tests."""

    def __init__(self, body_profile: BodyProfile | None = None) -> None:
        self._body_profile = body_profile

    async def upsert(self, body_profile: BodyProfile) -> BodyProfile:
        self._body_profile = body_profile
        return body_profile

    def get_by_profile_id(self, profile_id: str) -> BodyProfile | None:
        if self._body_profile is None:
            return None
        if self._body_profile.profile_id != profile_id:
            return None
        return self._body_profile


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


def test_get_body_targets_returns_missing_state_for_empty_body_profile() -> None:
    """Target query should stay honest when required body data is missing."""
    targets = get_body_targets(
        repository=InMemoryBodyProfileRepository(),
        user_repository=_user_repository(),
        profile_id="profile-1",
    )

    assert targets.target_daily_kcal is None
    assert targets.target_daily_protein is None
    assert targets.target_daily_fat is None
    assert targets.missing_fields == (
        "activity_level",
        "age_years",
        "height_cm",
        "sex",
        "weight_kg",
    )
    assert targets.unsupported_reasons == ()
    assert targets.target_ranges["target_daily_kcal"].to_dict()["missing_fields"] == [
        "age_years",
        "sex",
        "height_cm",
        "weight_kg",
        "activity_level",
    ]
    assert targets.target_ranges["target_daily_protein"].to_dict()["missing_fields"] == [
        "weight_kg",
        "activity_level",
    ]
    assert targets.target_ranges["target_daily_fat"].to_dict()["missing_fields"] == [
        "weight_kg"
    ]


def test_get_body_targets_returns_conservative_targets_for_complete_adult_profile() -> None:
    """Target query should calculate adult maintenance and macro targets when inputs are complete."""
    targets = get_body_targets(
        repository=InMemoryBodyProfileRepository(
            BodyProfile.create(
                profile_id="profile-1",
                age_years=35,
                sex=SEX_MALE,
                height_cm=180,
                weight_kg=80,
                activity_level=ACTIVITY_LEVEL_MODERATE,
            )
        ),
        user_repository=_user_repository(),
        profile_id="profile-1",
    )

    assert targets.target_daily_kcal == 2720
    assert targets.target_daily_protein == 120.0
    assert targets.target_daily_fat == 72.0
    assert targets.missing_fields == ()
    assert targets.unsupported_reasons == ()
    assert targets.target_ranges["target_daily_kcal"].to_dict()["minimum"] == 2584
    assert targets.target_ranges["target_daily_kcal"].to_dict()["recommended"] == 2720
    assert targets.target_ranges["target_daily_kcal"].to_dict()["maximum"] == 2856
    assert targets.target_ranges["target_daily_kcal"].to_dict()["inputs"] == {
        "age_years": 35,
        "sex": "male",
        "height_cm": 180.0,
        "weight_kg": 80.0,
        "activity_level": "moderate",
        "sex_adjustment": 5,
        "activity_multiplier": 1.55,
        "bmr_kcal": 1755.0,
        "range_ratio": 0.05,
        "maintenance_center_kcal": 2720.25,
    }
    assert targets.target_ranges["target_daily_protein"].to_dict()["minimum"] == 112.0
    assert targets.target_ranges["target_daily_protein"].to_dict()["recommended"] == 120.0
    assert targets.target_ranges["target_daily_protein"].to_dict()["maximum"] == 128.0
    assert targets.target_ranges["target_daily_protein"].to_dict()["inputs"] == {
        "weight_kg": 80.0,
        "activity_level": "moderate",
        "protein_factors_g_per_kg": [1.4, 1.5, 1.6],
    }
    assert targets.target_ranges["target_daily_fat"].to_dict()["minimum"] == 64.0
    assert targets.target_ranges["target_daily_fat"].to_dict()["recommended"] == 72.0
    assert targets.target_ranges["target_daily_fat"].to_dict()["maximum"] == 80.0
    assert targets.target_ranges["target_daily_fat"].to_dict()["inputs"] == {
        "weight_kg": 80.0,
        "fat_factors_g_per_kg": [0.8, 0.9, 1.0],
    }


def test_get_body_targets_marks_kcal_as_unsupported_for_minors() -> None:
    """The current calorie estimate should stay adult-only instead of guessing for minors."""
    targets = get_body_targets(
        repository=InMemoryBodyProfileRepository(
            BodyProfile.create(
                profile_id="profile-1",
                age_years=16,
                sex=SEX_MALE,
                height_cm=170,
                weight_kg=60,
                activity_level=ACTIVITY_LEVEL_MODERATE,
            )
        ),
        user_repository=_user_repository(),
        profile_id="profile-1",
    )

    assert targets.target_daily_kcal is None
    assert targets.target_daily_protein == 90.0
    assert targets.target_daily_fat == 54.0
    assert targets.unsupported_reasons == ("adult_only_kcal_estimate",)
    assert targets.target_ranges["target_daily_kcal"].to_dict()["unsupported_reasons"] == [
        "adult_only_kcal_estimate"
    ]


def test_get_body_targets_keeps_protein_and_fat_available_when_only_kcal_inputs_are_missing() -> None:
    """Each target should stay independent instead of all becoming unknown together."""
    targets = get_body_targets(
        repository=InMemoryBodyProfileRepository(
            BodyProfile.create(
                profile_id="profile-1",
                weight_kg=70,
                activity_level=ACTIVITY_LEVEL_MODERATE,
            )
        ),
        user_repository=_user_repository(),
        profile_id="profile-1",
    )

    assert targets.target_daily_kcal is None
    assert targets.target_daily_protein == 105.0
    assert targets.target_daily_fat == 63.0
    assert targets.target_ranges["target_daily_kcal"].to_dict()["missing_fields"] == [
        "age_years",
        "sex",
        "height_cm",
    ]
    assert targets.target_ranges["target_daily_protein"].to_dict()["missing_fields"] == []
    assert targets.target_ranges["target_daily_fat"].to_dict()["missing_fields"] == []


@pytest.mark.parametrize(
    ("activity_level", "expected_range"),
    [
        (ACTIVITY_LEVEL_SEDENTARY, (70.0, 77.0, 84.0)),
        (ACTIVITY_LEVEL_LIGHT, (84.0, 91.0, 98.0)),
        (ACTIVITY_LEVEL_MODERATE, (98.0, 105.0, 112.0)),
        (ACTIVITY_LEVEL_ACTIVE, (112.0, 122.5, 133.0)),
        (ACTIVITY_LEVEL_VERY_ACTIVE, (126.0, 140.0, 154.0)),
    ],
)
def test_get_body_targets_uses_expected_protein_range_per_activity_level(
    activity_level: str,
    expected_range: tuple[float, float, float],
) -> None:
    """Protein target ranges should stay stable for each activity level."""
    targets = get_body_targets(
        repository=InMemoryBodyProfileRepository(
            BodyProfile.create(
                profile_id="profile-1",
                weight_kg=70,
                activity_level=activity_level,
            )
        ),
        user_repository=_user_repository(),
        profile_id="profile-1",
    )

    protein_range = targets.target_ranges["target_daily_protein"].to_dict()

    assert (
        protein_range["minimum"],
        protein_range["recommended"],
        protein_range["maximum"],
    ) == expected_range
