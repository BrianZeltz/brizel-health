"""Repository contract for body profiles."""

from __future__ import annotations

from typing import Protocol

from ..models.body_profile import BodyProfile


class BodyProfileRepository(Protocol):
    """Persistence contract for per-profile body data."""

    async def upsert(self, body_profile: BodyProfile) -> BodyProfile:
        """Insert or replace one body profile."""

    def get_by_profile_id(self, profile_id: str) -> BodyProfile | None:
        """Return the body profile for a profile, if one exists."""
