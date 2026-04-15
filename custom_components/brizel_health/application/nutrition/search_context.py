"""Locale- and profile-aware search context for external food search."""

from __future__ import annotations

from dataclasses import dataclass

from ...core.users.brizel_user import (
    BrizelUser,
    PREFERRED_LANGUAGE_DE,
    PREFERRED_REGION_EU,
    PREFERRED_REGION_GERMANY,
    PREFERRED_REGION_GLOBAL,
    PREFERRED_REGION_USA,
    PREFERRED_UNITS_IMPERIAL,
    PREFERRED_UNITS_METRIC,
    resolve_effective_language,
)
from ...domains.nutrition.models.food import Food
from .search_intelligence import casefold_search_query, tokenize_search_text

_COUNTRY_GERMANY = {"de", "deu", "germany", "deutschland"}
_COUNTRY_USA = {"us", "usa", "united states", "united states of america"}


@dataclass(frozen=True, slots=True)
class FoodSearchContext:
    """Context influencing locale-aware external food search quality."""

    profile_id: str | None
    preferred_language: str
    preferred_region: str
    preferred_units: str
    locale_hint: str | None
    time_zone_hint: str | None
    country_hint: str | None
    recent_food_names: tuple[str, ...]
    recent_food_brands: tuple[str, ...]


def _normalize_optional_hint(value: str | None) -> str | None:
    """Normalize one optional hint string."""
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _normalize_country_hint(country: str | None) -> str | None:
    """Normalize one optional Home Assistant country hint."""
    normalized = _normalize_optional_hint(country)
    return normalized.casefold() if normalized is not None else None


def _derive_region(
    *,
    country_hint: str | None,
    time_zone_hint: str | None,
    preferred_language: str,
) -> str:
    """Derive one conservative market region from Home Assistant hints."""
    if country_hint in _COUNTRY_GERMANY:
        return PREFERRED_REGION_GERMANY
    if country_hint in _COUNTRY_USA:
        return PREFERRED_REGION_USA

    normalized_time_zone = (_normalize_optional_hint(time_zone_hint) or "").casefold()
    if normalized_time_zone == "europe/berlin":
        return PREFERRED_REGION_GERMANY
    if normalized_time_zone.startswith("america/"):
        return PREFERRED_REGION_USA
    if normalized_time_zone.startswith("europe/"):
        return PREFERRED_REGION_EU
    if preferred_language == PREFERRED_LANGUAGE_DE:
        return PREFERRED_REGION_EU
    return PREFERRED_REGION_GLOBAL


def _derive_units(
    *,
    units_hint: str | None,
    preferred_region: str,
) -> str:
    """Derive one conservative preferred unit system."""
    normalized_units = (_normalize_optional_hint(units_hint) or "").casefold()
    if "imperial" in normalized_units:
        return PREFERRED_UNITS_IMPERIAL
    if "metric" in normalized_units:
        return PREFERRED_UNITS_METRIC
    if preferred_region == PREFERRED_REGION_USA:
        return PREFERRED_UNITS_IMPERIAL
    return PREFERRED_UNITS_METRIC


def _extract_recent_food_names(foods: list[Food] | None) -> tuple[str, ...]:
    """Extract recent food names for small local ranking boosts."""
    if not foods:
        return ()
    normalized: list[str] = []
    seen: set[str] = set()
    for food in foods:
        name = casefold_search_query(food.name)
        if not name or name in seen:
            continue
        seen.add(name)
        normalized.append(name)
    return tuple(normalized)


def _extract_recent_food_brands(foods: list[Food] | None) -> tuple[str, ...]:
    """Extract recent food brands for small local ranking boosts."""
    if not foods:
        return ()
    normalized: list[str] = []
    seen: set[str] = set()
    for food in foods:
        if food.brand is None:
            continue
        brand = casefold_search_query(food.brand)
        if not brand or brand in seen:
            continue
        seen.add(brand)
        normalized.append(brand)
    return tuple(normalized)


def build_food_search_context(
    *,
    profile_id: str | None,
    profile: BrizelUser | None,
    hass_language: str | None,
    hass_time_zone: str | None,
    hass_country: str | None,
    hass_units_hint: str | None,
    recent_foods: list[Food] | None = None,
) -> FoodSearchContext:
    """Build one locale- and profile-aware search context."""
    country_hint = _normalize_country_hint(hass_country)
    preferred_language = resolve_effective_language(
        profile.preferred_language if profile is not None else None,
        language_hint=hass_language,
    )
    preferred_region = (
        profile.preferred_region
        if profile is not None and profile.preferred_region is not None
        else _derive_region(
            country_hint=country_hint,
            time_zone_hint=hass_time_zone,
            preferred_language=preferred_language,
        )
    )
    preferred_units = (
        profile.preferred_units
        if profile is not None and profile.preferred_units is not None
        else _derive_units(
            units_hint=hass_units_hint,
            preferred_region=preferred_region,
        )
    )

    return FoodSearchContext(
        profile_id=profile_id,
        preferred_language=preferred_language,
        preferred_region=preferred_region,
        preferred_units=preferred_units,
        locale_hint=_normalize_optional_hint(hass_language),
        time_zone_hint=_normalize_optional_hint(hass_time_zone),
        country_hint=country_hint,
        recent_food_names=_extract_recent_food_names(recent_foods),
        recent_food_brands=_extract_recent_food_brands(recent_foods),
    )


def context_recent_token_overlap(
    context: FoodSearchContext,
    *,
    result_name: str,
    result_brand: str | None,
) -> int:
    """Return a small local-history score boost for one result."""
    score = 0
    normalized_name = casefold_search_query(result_name)
    normalized_brand = casefold_search_query(result_brand or "")
    result_name_tokens = set(tokenize_search_text(result_name))
    result_brand_tokens = set(tokenize_search_text(result_brand or ""))

    if normalized_name in context.recent_food_names:
        score += 90
    elif any(
        recent_name in normalized_name or normalized_name in recent_name
        for recent_name in context.recent_food_names
    ):
        score += 40

    if normalized_brand and normalized_brand in context.recent_food_brands:
        score += 35

    for recent_name in context.recent_food_names:
        recent_tokens = set(tokenize_search_text(recent_name))
        if recent_tokens and recent_tokens <= result_name_tokens:
            score += 20
            break

    for recent_brand in context.recent_food_brands:
        recent_brand_tokens = set(tokenize_search_text(recent_brand))
        if recent_brand_tokens and recent_brand_tokens <= result_brand_tokens:
            score += 10
            break

    return score
