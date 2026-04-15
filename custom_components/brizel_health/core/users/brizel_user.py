"""Core user model for Brizel Health."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from .errors import BrizelUserValidationError

PREFERRED_LANGUAGE_AUTO = "auto"
PREFERRED_LANGUAGE_DE = "de"
PREFERRED_LANGUAGE_EN = "en"
SUPPORTED_PREFERRED_LANGUAGES = {
    PREFERRED_LANGUAGE_AUTO,
    PREFERRED_LANGUAGE_DE,
    PREFERRED_LANGUAGE_EN,
}

PREFERRED_REGION_GERMANY = "germany"
PREFERRED_REGION_EU = "eu"
PREFERRED_REGION_USA = "usa"
PREFERRED_REGION_GLOBAL = "global"
SUPPORTED_PREFERRED_REGIONS = {
    PREFERRED_REGION_GERMANY,
    PREFERRED_REGION_EU,
    PREFERRED_REGION_USA,
    PREFERRED_REGION_GLOBAL,
}

PREFERRED_UNITS_METRIC = "metric"
PREFERRED_UNITS_IMPERIAL = "imperial"
SUPPORTED_PREFERRED_UNITS = {
    PREFERRED_UNITS_METRIC,
    PREFERRED_UNITS_IMPERIAL,
}


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


def normalize_preferred_language(preferred_language: str | None) -> str | None:
    """Normalize one optional preferred language."""
    if preferred_language is None:
        return None

    normalized = str(preferred_language).strip().lower()
    if not normalized:
        return None
    if normalized == PREFERRED_LANGUAGE_AUTO:
        return PREFERRED_LANGUAGE_AUTO
    if normalized.startswith("de"):
        return PREFERRED_LANGUAGE_DE
    if normalized.startswith("en"):
        return PREFERRED_LANGUAGE_EN
    if normalized not in SUPPORTED_PREFERRED_LANGUAGES:
        raise BrizelUserValidationError("preferred_language is not supported.")
    return normalized


def normalize_language_hint(language_hint: str | None) -> str | None:
    """Normalize one Home Assistant language/locale hint to a supported UI language."""
    if language_hint is None:
        return None

    normalized = str(language_hint).strip().lower()
    if not normalized:
        return None
    if normalized.startswith("de"):
        return PREFERRED_LANGUAGE_DE
    if normalized.startswith("en"):
        return PREFERRED_LANGUAGE_EN
    return None


def resolve_effective_language(
    preferred_language: str | None,
    *,
    language_hint: str | None = None,
    default_language: str = PREFERRED_LANGUAGE_EN,
) -> str:
    """Resolve the effective Brizel UI/search language from profile choice plus HA hints."""
    normalized_preference = normalize_preferred_language(preferred_language)
    if normalized_preference in {
        PREFERRED_LANGUAGE_DE,
        PREFERRED_LANGUAGE_EN,
    }:
        return normalized_preference

    return normalize_language_hint(language_hint) or default_language


def normalize_preferred_region(preferred_region: str | None) -> str | None:
    """Normalize one optional preferred food market/region."""
    if preferred_region is None:
        return None

    normalized = str(preferred_region).strip().lower()
    if not normalized:
        return None
    if normalized not in SUPPORTED_PREFERRED_REGIONS:
        raise BrizelUserValidationError("preferred_region is not supported.")
    return normalized


def normalize_preferred_units(preferred_units: str | None) -> str | None:
    """Normalize one optional preferred unit system."""
    if preferred_units is None:
        return None

    normalized = str(preferred_units).strip().lower()
    if not normalized:
        return None
    if normalized not in SUPPORTED_PREFERRED_UNITS:
        raise BrizelUserValidationError("preferred_units are not supported.")
    return normalized


@dataclass(slots=True)
class BrizelUser:
    """Central user identity shared across modules."""

    user_id: str
    display_name: str
    linked_ha_user_id: str | None
    created_at: str
    preferred_language: str | None = None
    preferred_region: str | None = None
    preferred_units: str | None = None

    @classmethod
    def create(
        cls,
        display_name: str,
        linked_ha_user_id: str | None = None,
        preferred_language: str | None = None,
        preferred_region: str | None = None,
        preferred_units: str | None = None,
    ) -> "BrizelUser":
        """Create a new validated user."""
        normalized_name = normalize_display_name(display_name)
        if not normalized_name:
            raise BrizelUserValidationError("A profile name is required.")

        return cls(
            user_id=generate_user_id(),
            display_name=normalized_name,
            linked_ha_user_id=normalize_linked_ha_user_id(linked_ha_user_id),
            preferred_language=normalize_preferred_language(preferred_language),
            preferred_region=normalize_preferred_region(preferred_region),
            preferred_units=normalize_preferred_units(preferred_units),
            created_at=datetime.now(UTC).isoformat(),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BrizelUser":
        """Create a user instance from persisted data."""
        user_id = str(data.get("profile_id", "")).strip()
        display_name = normalize_display_name(str(data.get("display_name", "")))
        linked_ha_user_id = normalize_linked_ha_user_id(data.get("linked_ha_user_id"))
        preferred_language = normalize_preferred_language(
            data.get("preferred_language")
        )
        preferred_region = normalize_preferred_region(data.get("preferred_region"))
        preferred_units = normalize_preferred_units(data.get("preferred_units"))
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
            preferred_language=preferred_language,
            preferred_region=preferred_region,
            preferred_units=preferred_units,
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

    def set_search_preferences(
        self,
        *,
        preferred_language: str | None,
        preferred_region: str | None,
        preferred_units: str | None,
    ) -> None:
        """Set or clear search-related profile preferences."""
        self.preferred_language = normalize_preferred_language(preferred_language)
        self.preferred_region = normalize_preferred_region(preferred_region)
        self.preferred_units = normalize_preferred_units(preferred_units)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the user using the legacy storage shape."""
        return {
            "profile_id": self.user_id,
            "display_name": self.display_name,
            "linked_ha_user_id": self.linked_ha_user_id,
            "preferred_language": self.preferred_language,
            "preferred_region": self.preferred_region,
            "preferred_units": self.preferred_units,
            "created_at": self.created_at,
        }
