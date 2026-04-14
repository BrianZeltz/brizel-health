"""Tests for locale- and profile-aware external food search context."""

from __future__ import annotations

from custom_components.brizel_health.application.nutrition.search_context import (
    build_food_search_context,
    context_recent_token_overlap,
)
from custom_components.brizel_health.core.users.brizel_user import BrizelUser
from custom_components.brizel_health.domains.nutrition.models.food import Food


def test_build_food_search_context_uses_conservative_germany_defaults() -> None:
    """de-DE plus Europe/Berlin should resolve to a Germany/metric search context."""
    context = build_food_search_context(
        profile_id=None,
        profile=None,
        hass_language="de-DE",
        hass_time_zone="Europe/Berlin",
        hass_country="DE",
        hass_units_hint="metric",
        recent_foods=None,
    )

    assert context.profile_id is None
    assert context.preferred_language == "de"
    assert context.preferred_region == "germany"
    assert context.preferred_units == "metric"


def test_build_food_search_context_uses_conservative_usa_defaults() -> None:
    """en-US plus an America timezone should resolve to a USA/imperial search context."""
    context = build_food_search_context(
        profile_id=None,
        profile=None,
        hass_language="en-US",
        hass_time_zone="America/New_York",
        hass_country="US",
        hass_units_hint=None,
        recent_foods=None,
    )

    assert context.preferred_language == "en"
    assert context.preferred_region == "usa"
    assert context.preferred_units == "imperial"


def test_build_food_search_context_prefers_profile_settings_over_ha_hints() -> None:
    """Explicit profile preferences should win over Home Assistant fallback hints."""
    profile = BrizelUser.create(
        display_name="Alice",
        preferred_language="en",
        preferred_region="global",
        preferred_units="imperial",
    )

    context = build_food_search_context(
        profile_id=profile.user_id,
        profile=profile,
        hass_language="de-DE",
        hass_time_zone="Europe/Berlin",
        hass_country="DE",
        hass_units_hint="metric",
        recent_foods=None,
    )

    assert context.profile_id == profile.user_id
    assert context.preferred_language == "en"
    assert context.preferred_region == "global"
    assert context.preferred_units == "imperial"


def test_context_recent_token_overlap_adds_small_local_history_boost() -> None:
    """Recent foods should add only a moderate local ranking boost."""
    recent_food = Food.create(
        name="Gouda jung",
        brand="Milbona",
        kcal_per_100g=356,
        protein_per_100g=24.0,
        carbs_per_100g=0.1,
        fat_per_100g=28.0,
    )
    context = build_food_search_context(
        profile_id="profile-1",
        profile=None,
        hass_language="de-DE",
        hass_time_zone="Europe/Berlin",
        hass_country="DE",
        hass_units_hint="metric",
        recent_foods=[recent_food],
    )

    assert (
        context_recent_token_overlap(
            context,
            result_name="Gouda jung in Scheiben",
            result_brand="Milbona",
        )
        > 0
    )
