"""User repository contract."""

from __future__ import annotations

from typing import Protocol

from ..users.brizel_user import BrizelUser


class UserRepository(Protocol):
    """Persistence contract for central Brizel users."""

    async def add(self, user: BrizelUser) -> BrizelUser:
        """Persist a new user."""

    async def update(self, user: BrizelUser) -> BrizelUser:
        """Persist an existing user."""

    async def delete(self, user_id: str) -> BrizelUser:
        """Delete a user and return the removed entity."""

    def get_by_id(self, user_id: str) -> BrizelUser:
        """Load a user by ID."""

    def get_all(self) -> list[BrizelUser]:
        """Load all users."""

    def display_name_exists(
        self,
        display_name: str,
        exclude_user_id: str | None = None,
    ) -> bool:
        """Return whether a display name already exists."""
