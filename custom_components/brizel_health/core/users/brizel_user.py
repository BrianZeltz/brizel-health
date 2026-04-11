"""Core user model for Brizel Health."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from .errors import BrizelUserValidationError


def generate_user_id() -> str:
    """Generate a stable unique user ID."""
    return uuid4().hex


def normalize_display_name(display_name: str) -> str:
    """Normalize a display name."""
    return display_name.strip()


def normalize_linked_ha_user_id(linked_ha_user_id: str | None) -> str | None:
    """Normalize an optional linked Home Assistant user ID."""
    if linked_ha_user_id is None:
        return None

    normalized = str(linked_ha_user_id).strip()
    return normalized or None


@dataclass(slots=True)
class BrizelUser:
    """Central user identity shared across modules."""

    user_id: str
    display_name: str
    linked_ha_user_id: str | None
    created_at: str

    @classmethod
    def create(
        cls,
        display_name: str,
        linked_ha_user_id: str | None = None,
    ) -> "BrizelUser":
        """Create a new validated user."""
        normalized_name = normalize_display_name(display_name)
        if not normalized_name:
            raise BrizelUserValidationError("A profile name is required.")

        return cls(
            user_id=generate_user_id(),
            display_name=normalized_name,
            linked_ha_user_id=normalize_linked_ha_user_id(linked_ha_user_id),
            created_at=datetime.now(UTC).isoformat(),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BrizelUser":
        """Create a user instance from persisted data."""
        user_id = str(data.get("profile_id", "")).strip()
        display_name = normalize_display_name(str(data.get("display_name", "")))
        linked_ha_user_id = normalize_linked_ha_user_id(data.get("linked_ha_user_id"))
        created_at = str(data.get("created_at", "")).strip()

        if not user_id:
            raise BrizelUserValidationError("A profile ID is required.")
        if not display_name:
            raise BrizelUserValidationError("A profile name is required.")
        if not created_at:
            raise BrizelUserValidationError("created_at is required.")

        return cls(
            user_id=user_id,
            display_name=display_name,
            linked_ha_user_id=linked_ha_user_id,
            created_at=created_at,
        )

    def rename(self, display_name: str) -> None:
        """Rename the user."""
        normalized_name = normalize_display_name(display_name)
        if not normalized_name:
            raise BrizelUserValidationError("A profile name is required.")
        self.display_name = normalized_name

    def set_linked_ha_user_id(self, linked_ha_user_id: str | None) -> None:
        """Set or clear the linked Home Assistant user."""
        self.linked_ha_user_id = normalize_linked_ha_user_id(linked_ha_user_id)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the user using the legacy storage shape."""
        return {
            "profile_id": self.user_id,
            "display_name": self.display_name,
            "linked_ha_user_id": self.linked_ha_user_id,
            "created_at": self.created_at,
        }
