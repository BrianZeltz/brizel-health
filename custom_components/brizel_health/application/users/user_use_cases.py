"""User application use cases."""

from __future__ import annotations

from ...core.interfaces.user_repository import UserRepository
from ...core.users.brizel_user import BrizelUser, normalize_linked_ha_user_id
from ...core.users.errors import (
    BrizelUserAlreadyExistsError,
    BrizelUserNotFoundError,
    BrizelUserValidationError,
)

_UNSET = object()


def _find_user_by_linked_ha_user_id(
    repository: UserRepository,
    linked_ha_user_id: str,
) -> BrizelUser | None:
    """Return one linked profile if the HA user ID is already assigned."""
    normalized_linked_ha_user_id = normalize_linked_ha_user_id(linked_ha_user_id)
    if normalized_linked_ha_user_id is None:
        return None

    for user in get_all_users(repository):
        if user.linked_ha_user_id == normalized_linked_ha_user_id:
            return user

    return None


async def create_user(
    repository: UserRepository,
    display_name: str,
    linked_ha_user_id: str | None = None,
    preferred_language: str | None = None,
    preferred_region: str | None = None,
    preferred_units: str | None = None,
) -> BrizelUser:
    """Create a new central user."""
    user = BrizelUser.create(
        display_name=display_name,
        linked_ha_user_id=linked_ha_user_id,
        preferred_language=preferred_language,
        preferred_region=preferred_region,
        preferred_units=preferred_units,
    )

    if repository.display_name_exists(user.display_name):
        raise BrizelUserAlreadyExistsError(
            f"A profile named '{user.display_name}' already exists."
        )
    if (
        user.linked_ha_user_id is not None
        and _find_user_by_linked_ha_user_id(repository, user.linked_ha_user_id)
        is not None
    ):
        raise BrizelUserAlreadyExistsError(
            "The selected Home Assistant user is already linked to another profile."
        )

    return await repository.add(user)


def get_user(
    repository: UserRepository,
    user_id: str,
) -> BrizelUser:
    """Return a single user."""
    normalized_user_id = user_id.strip()
    if not normalized_user_id:
        raise BrizelUserValidationError("A profile ID is required.")
    return repository.get_by_id(normalized_user_id)


def get_all_users(repository: UserRepository) -> list[BrizelUser]:
    """Return all users."""
    return repository.get_all()


def get_user_by_linked_ha_user_id(
    repository: UserRepository,
    linked_ha_user_id: str,
) -> BrizelUser:
    """Return the profile linked to one Home Assistant user ID."""
    normalized_linked_ha_user_id = normalize_linked_ha_user_id(linked_ha_user_id)
    if normalized_linked_ha_user_id is None:
        raise BrizelUserValidationError("A linked Home Assistant user ID is required.")

    linked_user = _find_user_by_linked_ha_user_id(
        repository,
        normalized_linked_ha_user_id,
    )
    if linked_user is not None:
        return linked_user

    raise BrizelUserNotFoundError(
        "No Brizel Health profile is linked to the active Home Assistant user."
    )


def resolve_profile_id(
    repository: UserRepository,
    *,
    profile_id: str | None,
    linked_ha_user_id: str | None = None,
) -> str:
    """Resolve one profile ID from explicit input or a linked HA user."""
    normalized_profile_id = str(profile_id or "").strip()
    if normalized_profile_id:
        return get_user(repository, normalized_profile_id).user_id

    normalized_linked_ha_user_id = normalize_linked_ha_user_id(linked_ha_user_id)
    if normalized_linked_ha_user_id is None:
        raise BrizelUserValidationError(
            "profile_id is required when no linked Home Assistant user is available."
        )

    return get_user_by_linked_ha_user_id(
        repository,
        normalized_linked_ha_user_id,
    ).user_id


async def update_user_linked_ha_user_id(
    repository: UserRepository,
    user_id: str,
    linked_ha_user_id: str | None,
) -> BrizelUser:
    """Link or unlink one profile to one Home Assistant user."""
    user = get_user(repository, user_id)
    normalized_linked_ha_user_id = normalize_linked_ha_user_id(linked_ha_user_id)

    if normalized_linked_ha_user_id is not None:
        linked_user = _find_user_by_linked_ha_user_id(
            repository,
            normalized_linked_ha_user_id,
        )
        if linked_user is not None and linked_user.user_id != user.user_id:
            raise BrizelUserAlreadyExistsError(
                "The selected Home Assistant user is already linked to another profile."
            )

    user.set_linked_ha_user_id(normalized_linked_ha_user_id)
    return await repository.update(user)


async def update_user(
    repository: UserRepository,
    user_id: str,
    display_name: str,
    *,
    preferred_language: str | None | object = _UNSET,
    preferred_region: str | None | object = _UNSET,
    preferred_units: str | None | object = _UNSET,
) -> BrizelUser:
    """Rename a user."""
    user = get_user(repository, user_id)
    user.rename(display_name)

    if repository.display_name_exists(
        user.display_name,
        exclude_user_id=user.user_id,
    ):
        raise BrizelUserAlreadyExistsError(
            f"A profile named '{user.display_name}' already exists."
        )

    if (
        preferred_language is not _UNSET
        or preferred_region is not _UNSET
        or preferred_units is not _UNSET
    ):
        user.set_search_preferences(
            preferred_language=(
                user.preferred_language
                if preferred_language is _UNSET
                else preferred_language
            ),
            preferred_region=(
                user.preferred_region
                if preferred_region is _UNSET
                else preferred_region
            ),
            preferred_units=(
                user.preferred_units
                if preferred_units is _UNSET
                else preferred_units
            ),
        )

    return await repository.update(user)


async def delete_user(
    repository: UserRepository,
    user_id: str,
) -> BrizelUser:
    """Delete a user."""
    normalized_user_id = user_id.strip()
    if not normalized_user_id:
        raise BrizelUserValidationError("A profile ID is required.")
    return await repository.delete(normalized_user_id)
