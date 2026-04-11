"""Queries for derived body targets."""

from __future__ import annotations

from ..users.user_use_cases import get_user
from ...core.interfaces.user_repository import UserRepository
from ...domains.body.interfaces.body_profile_repository import BodyProfileRepository
from ...domains.body.models.body_profile import BodyProfile
from ...domains.body.models.body_targets import BodyTargets
from ...domains.body.services.targets import calculate_body_targets


def get_body_targets(
    repository: BodyProfileRepository,
    user_repository: UserRepository,
    profile_id: str,
) -> BodyTargets:
    """Return derived targets for one profile."""
    user = get_user(user_repository, profile_id)
    body_profile = repository.get_by_profile_id(user.user_id) or BodyProfile.create(
        profile_id=user.user_id
    )
    return calculate_body_targets(body_profile)
