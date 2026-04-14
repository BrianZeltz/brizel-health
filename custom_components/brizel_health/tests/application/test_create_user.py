"""Tests for user application use cases."""

from __future__ import annotations

import pytest

from custom_components.brizel_health.application.users.user_use_cases import (
    create_user,
    delete_user,
    get_all_users,
    get_user_by_linked_ha_user_id,
    get_user,
    resolve_profile_id,
    update_user,
    update_user_linked_ha_user_id,
)
from custom_components.brizel_health.core.users.brizel_user import BrizelUser
from custom_components.brizel_health.core.users.errors import (
    BrizelUserAlreadyExistsError,
    BrizelUserNotFoundError,
    BrizelUserValidationError,
)


class InMemoryUserRepository:
    """Simple in-memory repository for application tests."""

    def __init__(self) -> None:
        self.users = {}

    async def add(self, user):
        self.users[user.user_id] = user
        return user

    async def update(self, user):
        self.users[user.user_id] = user
        return user

    async def delete(self, user_id):
        return self.users.pop(user_id)

    def get_by_id(self, user_id):
        user = self.users.get(user_id)
        if user is None:
            raise BrizelUserNotFoundError(
                f"No profile found for profile_id '{user_id}'."
            )
        return user

    def get_all(self):
        return list(self.users.values())

    def display_name_exists(self, display_name, exclude_user_id=None):
        normalized = display_name.strip().casefold()
        for user_id, user in self.users.items():
            if exclude_user_id is not None and user_id == exclude_user_id:
                continue
            if user.display_name.strip().casefold() == normalized:
                return True
        return False


@pytest.mark.asyncio
async def test_create_get_update_delete_user_flow() -> None:
    """User use cases preserve legacy profile behavior."""
    repository = InMemoryUserRepository()

    created = await create_user(repository, "  Alice  ", linked_ha_user_id="ha-1")

    assert created.display_name == "Alice"
    assert created.linked_ha_user_id == "ha-1"
    assert get_user(repository, created.user_id).user_id == created.user_id
    assert len(get_all_users(repository)) == 1

    updated = await update_user(repository, created.user_id, "Alice Example")
    assert updated.display_name == "Alice Example"

    deleted = await delete_user(repository, created.user_id)
    assert deleted.user_id == created.user_id
    assert get_all_users(repository) == []


@pytest.mark.asyncio
async def test_create_and_update_user_can_store_search_preferences() -> None:
    """Profile search preferences should be persisted without breaking core user flows."""
    repository = InMemoryUserRepository()

    created = await create_user(
        repository,
        "Alice",
        preferred_language="de-DE",
        preferred_region="germany",
        preferred_units="metric",
    )

    assert created.preferred_language == "de"
    assert created.preferred_region == "germany"
    assert created.preferred_units == "metric"

    updated = await update_user(
        repository,
        created.user_id,
        "Alice Example",
        preferred_language="en",
        preferred_region="usa",
        preferred_units="imperial",
    )

    assert updated.display_name == "Alice Example"
    assert updated.preferred_language == "en"
    assert updated.preferred_region == "usa"
    assert updated.preferred_units == "imperial"


def test_brizel_user_from_dict_remains_backward_compatible_without_search_preferences() -> None:
    """Older stored profiles without the new search-preference fields should still load."""
    user = BrizelUser.from_dict(
        {
            "profile_id": "profile-1",
            "display_name": "Alice",
            "linked_ha_user_id": "ha-1",
            "created_at": "2026-04-13T09:00:00+00:00",
        }
    )

    assert user.user_id == "profile-1"
    assert user.display_name == "Alice"
    assert user.linked_ha_user_id == "ha-1"
    assert user.preferred_language is None
    assert user.preferred_region is None
    assert user.preferred_units is None


@pytest.mark.asyncio
async def test_create_user_rejects_duplicate_display_name() -> None:
    """Display names stay unique like in the legacy profile service."""
    repository = InMemoryUserRepository()

    await create_user(repository, "Alice")

    try:
        await create_user(repository, " alice ")
    except BrizelUserAlreadyExistsError:
        pass
    else:
        raise AssertionError("Expected duplicate display name to be rejected")


@pytest.mark.asyncio
async def test_create_user_rejects_duplicate_linked_ha_user_id() -> None:
    """One HA user link should not be reusable across multiple profiles."""
    repository = InMemoryUserRepository()

    await create_user(repository, "Alice", linked_ha_user_id="ha-1")

    with pytest.raises(BrizelUserAlreadyExistsError):
        await create_user(repository, "Bob", linked_ha_user_id="ha-1")


@pytest.mark.asyncio
async def test_update_user_linked_ha_user_id_links_and_unlinks_one_profile() -> None:
    """Profiles should be linkable to and unlinkable from one HA user ID."""
    repository = InMemoryUserRepository()
    created = await create_user(repository, "Alice")

    linked = await update_user_linked_ha_user_id(repository, created.user_id, "ha-123")
    assert linked.linked_ha_user_id == "ha-123"
    assert get_user_by_linked_ha_user_id(repository, "ha-123").user_id == created.user_id

    unlinked = await update_user_linked_ha_user_id(repository, created.user_id, "")
    assert unlinked.linked_ha_user_id is None


@pytest.mark.asyncio
async def test_update_user_linked_ha_user_id_rejects_duplicate_ha_user_links() -> None:
    """One HA user should not silently map to multiple Brizel profiles."""
    repository = InMemoryUserRepository()
    alice = await create_user(repository, "Alice", linked_ha_user_id="ha-1")
    bob = await create_user(repository, "Bob")

    with pytest.raises(BrizelUserAlreadyExistsError):
        await update_user_linked_ha_user_id(repository, bob.user_id, "ha-1")

    assert get_user(repository, alice.user_id).linked_ha_user_id == "ha-1"
    assert get_user(repository, bob.user_id).linked_ha_user_id is None


@pytest.mark.asyncio
async def test_resolve_profile_id_prefers_explicit_profile_and_can_fall_back_to_linked_ha_user() -> None:
    """Profile resolution should work for both explicit IDs and linked HA users."""
    repository = InMemoryUserRepository()
    alice = await create_user(repository, "Alice", linked_ha_user_id="ha-1")

    assert resolve_profile_id(repository, profile_id=f" {alice.user_id} ") == alice.user_id
    assert resolve_profile_id(
        repository,
        profile_id=None,
        linked_ha_user_id="ha-1",
    ) == alice.user_id


def test_resolve_profile_id_requires_explicit_or_linked_profile_context() -> None:
    """Profile resolution should fail clearly when neither profile nor HA user is known."""
    repository = InMemoryUserRepository()

    with pytest.raises(BrizelUserValidationError):
        resolve_profile_id(repository, profile_id=None, linked_ha_user_id=None)


def test_get_user_by_linked_ha_user_id_fails_cleanly_when_no_link_exists() -> None:
    """Unlinked Home Assistant users should not silently resolve to a profile."""
    repository = InMemoryUserRepository()

    with pytest.raises(BrizelUserNotFoundError):
        get_user_by_linked_ha_user_id(repository, "ha-missing")


def test_resolve_profile_id_fails_cleanly_for_unknown_explicit_profile() -> None:
    """Unknown explicit profile IDs should fail instead of falling back to another profile."""
    repository = InMemoryUserRepository()

    with pytest.raises(BrizelUserNotFoundError):
        resolve_profile_id(repository, profile_id="missing-profile", linked_ha_user_id="ha-1")
