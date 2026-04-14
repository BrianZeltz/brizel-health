"""Tests for Home Assistant facing source configuration helpers."""

from __future__ import annotations

from custom_components.brizel_health.adapters.homeassistant.source_configuration import (
    SOURCE_OPTION_API_KEY,
    SOURCE_OPTIONS_KEY,
    create_food_source_registry,
    get_default_food_source_options,
)


def test_create_food_source_registry_uses_known_default_sources() -> None:
    """The HA runtime should expose the expected default source set."""
    registry = create_food_source_registry()

    enabled_sources = registry.get_enabled_sources()

    assert [source.name for source in enabled_sources] == ["bls", "open_food_facts"]
    assert registry.get_source("bls") is not None
    assert registry.get_source("usda") is not None
    assert registry.get_source("open_food_facts") is not None


def test_create_food_source_registry_reads_enabled_and_priority_from_options() -> None:
    """Config-entry options should shape the runtime source registry."""
    options = {
        SOURCE_OPTIONS_KEY: {
            "bls": {
                "enabled": True,
                "priority": 12,
            },
            "open_food_facts": {
                "enabled": False,
                "priority": 30,
            },
            "usda": {
                "enabled": True,
                "priority": 5,
                "api_key": "demo-key",
            },
        }
    }

    registry = create_food_source_registry(options)
    enabled_sources = registry.get_enabled_sources()
    defaults = get_default_food_source_options()

    assert [source.name for source in enabled_sources] == ["usda", "bls"]
    assert [source.priority for source in enabled_sources] == [5, 12]
    assert defaults["bls"]["enabled"] is True
    assert defaults["open_food_facts"]["enabled"] is True
    assert defaults["usda"]["priority"] == 10
    assert defaults["usda"][SOURCE_OPTION_API_KEY] == ""
