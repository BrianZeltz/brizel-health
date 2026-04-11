"""Tests for the external food source registry and selection strategy."""

from __future__ import annotations

from custom_components.brizel_health.application.nutrition.import_selection import (
    select_import_sources,
)
from custom_components.brizel_health.application.nutrition.source_registry import (
    FoodSourceRegistry,
)
from custom_components.brizel_health.domains.nutrition.models.imported_food_data import (
    ImportedFoodData,
)


class StubExternalFoodSourceAdapter:
    """Minimal adapter stub for registry tests."""

    def __init__(self, source_name: str) -> None:
        self.source_name = source_name

    async def fetch_food_by_id(self, source_id: str) -> ImportedFoodData | None:
        return None

    async def search_foods(
        self,
        query: str,
        limit: int = 10,
    ) -> list[ImportedFoodData]:
        return []


def test_source_registry_registers_and_returns_sources_in_priority_order() -> None:
    """Registry should keep source definitions centrally available in priority order."""
    registry = FoodSourceRegistry()
    registry.register_source(
        "usda",
        StubExternalFoodSourceAdapter("usda"),
        priority=20,
    )
    registry.register_source(
        "open_food_facts",
        StubExternalFoodSourceAdapter("open_food_facts"),
        priority=10,
    )

    sources = registry.list_sources()

    assert [source.name for source in sources] == [
        "open_food_facts",
        "usda",
    ]
    assert registry.get_source("USDA") is not None
    assert registry.get_source("USDA").name == "usda"


def test_select_import_sources_uses_enabled_sources_only() -> None:
    """Selection should prepare later activation flags by skipping disabled sources."""
    registry = FoodSourceRegistry()
    registry.register_source(
        "open_food_facts",
        StubExternalFoodSourceAdapter("open_food_facts"),
        priority=10,
        enabled=True,
    )
    registry.register_source(
        "usda",
        StubExternalFoodSourceAdapter("usda"),
        priority=20,
        enabled=False,
    )

    all_selected = select_import_sources(registry)
    requested_selected = select_import_sources(
        registry,
        requested_source_names=["open_food_facts", "usda"],
    )

    assert [source.name for source in all_selected] == ["open_food_facts"]
    assert [source.name for source in requested_selected] == ["open_food_facts"]
