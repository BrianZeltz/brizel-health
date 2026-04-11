"""Registry for available external food sources."""

from __future__ import annotations

from dataclasses import dataclass

from ...domains.nutrition.interfaces.external_food_source_adapter import (
    ExternalFoodSourceAdapter,
)


def _normalize_source_name(source_name: str) -> str:
    """Normalize a source name."""
    return source_name.strip().lower()


@dataclass(slots=True)
class FoodSourceDefinition:
    """Application-level definition of an available food source."""

    name: str
    adapter: ExternalFoodSourceAdapter
    priority: int = 100
    enabled: bool = True

    def __post_init__(self) -> None:
        """Normalize and validate source definition data."""
        normalized_name = _normalize_source_name(self.name)
        if not normalized_name:
            raise ValueError("Food source name is required.")

        self.name = normalized_name
        self.priority = int(self.priority)
        self.enabled = bool(self.enabled)


class FoodSourceRegistry:
    """Central registry of available external food sources."""

    def __init__(
        self,
        sources: list[FoodSourceDefinition] | None = None,
    ) -> None:
        """Initialize the registry."""
        self._sources: dict[str, FoodSourceDefinition] = {}

        for source in sources or []:
            self.register(source)

    def register(self, source: FoodSourceDefinition) -> FoodSourceDefinition:
        """Register or replace a food source definition."""
        self._sources[source.name] = source
        return source

    def register_source(
        self,
        name: str,
        adapter: ExternalFoodSourceAdapter,
        *,
        priority: int = 100,
        enabled: bool = True,
    ) -> FoodSourceDefinition:
        """Create and register a food source definition."""
        return self.register(
            FoodSourceDefinition(
                name=name,
                adapter=adapter,
                priority=priority,
                enabled=enabled,
            )
        )

    def get_source(self, name: str) -> FoodSourceDefinition | None:
        """Return a source definition by name."""
        normalized_name = _normalize_source_name(name)
        if not normalized_name:
            return None

        return self._sources.get(normalized_name)

    def list_sources(
        self,
        *,
        enabled_only: bool = False,
    ) -> list[FoodSourceDefinition]:
        """Return all registered sources in priority order."""
        sources = list(self._sources.values())
        if enabled_only:
            sources = [source for source in sources if source.enabled]

        return sorted(
            sources,
            key=lambda source: (source.priority, source.name),
        )

    def get_enabled_sources(self) -> list[FoodSourceDefinition]:
        """Return all enabled sources in priority order."""
        return self.list_sources(enabled_only=True)
