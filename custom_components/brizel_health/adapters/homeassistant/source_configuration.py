"""Home Assistant facing source-registry configuration helpers."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from ...application.nutrition.source_registry import FoodSourceRegistry
from ...infrastructure.external_food_sources.bls_adapter import BlsAdapter
from ...infrastructure.external_food_sources.open_food_facts_adapter import (
    OpenFoodFactsAdapter,
)
from ...infrastructure.external_food_sources.usda_adapter import UsdaAdapter

SOURCE_OPTIONS_KEY = "food_sources"
SOURCE_OPTION_ENABLED = "enabled"
SOURCE_OPTION_PRIORITY = "priority"
SOURCE_OPTION_API_KEY = "api_key"

DEFAULT_FOOD_SOURCE_OPTIONS: dict[str, dict[str, int | bool | str]] = {
    "bls": {
        SOURCE_OPTION_ENABLED: True,
        SOURCE_OPTION_PRIORITY: 20,
    },
    "open_food_facts": {
        SOURCE_OPTION_ENABLED: True,
        SOURCE_OPTION_PRIORITY: 20,
    },
    "usda": {
        SOURCE_OPTION_ENABLED: False,
        SOURCE_OPTION_PRIORITY: 20,
        SOURCE_OPTION_API_KEY: "",
    },
}


def get_default_food_source_options() -> dict[str, dict[str, int | bool | str]]:
    """Return a deep copy of the default per-source HA option structure."""
    return deepcopy(DEFAULT_FOOD_SOURCE_OPTIONS)


def _normalize_source_option_mapping(
    options: Mapping[str, Any] | None,
) -> Mapping[str, Any]:
    """Return the configured source option mapping or an empty mapping."""
    if options is None:
        return {}

    raw_sources = options.get(SOURCE_OPTIONS_KEY)
    if isinstance(raw_sources, Mapping):
        return raw_sources

    return {}


def _resolve_source_enabled(
    source_options: Mapping[str, Any],
    default_enabled: bool,
) -> bool:
    """Resolve one source enabled flag conservatively."""
    raw_value = source_options.get(SOURCE_OPTION_ENABLED, default_enabled)
    return bool(raw_value)


def _resolve_source_priority(
    source_options: Mapping[str, Any],
    default_priority: int,
) -> int:
    """Resolve one source priority conservatively."""
    raw_value = source_options.get(SOURCE_OPTION_PRIORITY, default_priority)
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return default_priority


def _resolve_source_api_key(
    source_options: Mapping[str, Any],
    default_api_key: str,
) -> str:
    """Resolve one source API key conservatively."""
    raw_value = source_options.get(SOURCE_OPTION_API_KEY, default_api_key)
    return str(raw_value).strip()


def create_food_source_registry(
    options: Mapping[str, Any] | None = None,
) -> FoodSourceRegistry:
    """Create a runtime source registry from HA config-entry options."""
    registry = FoodSourceRegistry()
    configured_sources = _normalize_source_option_mapping(options)

    for source_name, defaults in DEFAULT_FOOD_SOURCE_OPTIONS.items():
        source_options = configured_sources.get(source_name, {})
        if not isinstance(source_options, Mapping):
            source_options = {}

        if source_name == "bls":
            adapter = BlsAdapter()
        elif source_name == "open_food_facts":
            adapter = OpenFoodFactsAdapter()
        elif source_name == "usda":
            adapter = UsdaAdapter(
                api_key=_resolve_source_api_key(
                    source_options,
                    str(defaults.get(SOURCE_OPTION_API_KEY, "")),
                ),
            )
        else:
            continue

        registry.register_source(
            source_name,
            adapter,
            enabled=_resolve_source_enabled(
                source_options,
                bool(defaults[SOURCE_OPTION_ENABLED]),
            ),
            priority=_resolve_source_priority(
                source_options,
                int(defaults[SOURCE_OPTION_PRIORITY]),
            ),
        )

    return registry
