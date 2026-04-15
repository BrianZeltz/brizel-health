"""Queries for derived body targets."""

from __future__ import annotations

from ...domains.body.interfaces.body_measurement_repository import (
    BodyMeasurementRepository,
)
from ..users.user_use_cases import get_user
from ...core.interfaces.user_repository import UserRepository
from ...domains.body.interfaces.body_profile_repository import BodyProfileRepository
from ...domains.body.models.body_profile import BodyProfile
from ...domains.body.models.body_targets import BodyTargets
from ...domains.body.services.targets import calculate_body_targets
from .body_measurement_queries import get_latest_measurement


def get_body_targets(
    repository: BodyProfileRepository,
    user_repository: UserRepository,
    profile_id: str,
    measurement_repository: BodyMeasurementRepository | None = None,
) -> BodyTargets:
    """Return derived targets for one profile."""
    user = get_user(user_repository, profile_id)
    body_profile = repository.get_by_profile_id(user.user_id) or BodyProfile.create(
        profile_id=user.user_id
    )
    latest_weight = (
        get_latest_measurement(
            measurement_repository,
            user_repository,
            profile_id=user.user_id,
            measurement_type="weight",
        )
        if measurement_repository is not None
        else None
    )
    if latest_weight is not None:
        body_profile = BodyProfile.create(
            profile_id=body_profile.profile_id,
            age_years=body_profile.age_years,
            sex=body_profile.sex,
            height_cm=body_profile.height_cm,
            weight_kg=latest_weight.canonical_value,
            activity_level=body_profile.activity_level,
        )
    return calculate_body_targets(body_profile)
