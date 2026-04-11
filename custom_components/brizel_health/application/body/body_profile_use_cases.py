"""Write and read use cases for body profiles."""

from __future__ import annotations

from ..users.user_use_cases import get_user
from ...core.interfaces.user_repository import UserRepository
from ...domains.body.interfaces.body_profile_repository import BodyProfileRepository
from ...domains.body.models.body_profile import BodyProfile


def get_body_profile(
    repository: BodyProfileRepository,
    user_repository: UserRepository,
    profile_id: str,
) -> BodyProfile:
    """Return body data for a profile or an empty profile-scoped model."""
    user = get_user(user_repository, profile_id)
    return repository.get_by_profile_id(user.user_id) or BodyProfile.create(
        profile_id=user.user_id
    )


async def upsert_body_profile(
    repository: BodyProfileRepository,
    user_repository: UserRepository,
    profile_id: str,
    age_years: int | None = None,
    sex: str | None = None,
    height_cm: float | int | None = None,
    weight_kg: float | int | None = None,
    activity_level: str | None = None,
) -> BodyProfile:
    """Create or replace body data for a profile."""
    user = get_user(user_repository, profile_id)
    body_profile = repository.get_by_profile_id(user.user_id) or BodyProfile.create(
        profile_id=user.user_id
    )
    body_profile.update(
        age_years=age_years,
        sex=sex,
        height_cm=height_cm,
        weight_kg=weight_kg,
        activity_level=activity_level,
    )
    return await repository.upsert(body_profile)
