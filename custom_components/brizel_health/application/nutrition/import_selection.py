"""Selection strategy for choosing food sources to import from."""

from __future__ import annotations

from collections.abc import Iterable

from .source_registry import FoodSourceDefinition, FoodSourceRegistry


def _normalize_requested_source_names(
    source_names: Iterable[str],
) -> set[str]:
    """Normalize requested source names for comparison."""
    normalized_names: set[str] = set()
    for source_name in source_names:
        normalized_name = source_name.strip().lower()
        if normalized_name:
            normalized_names.add(normalized_name)
    return normalized_names


def select_import_sources(
    registry: FoodSourceRegistry,
    requested_source_names: Iterable[str] | None = None,
) -> list[FoodSourceDefinition]:
    """Select which enabled sources should be used for an import run."""
    enabled_sources = registry.get_enabled_sources()
    if requested_source_names is None:
        return enabled_sources

    normalized_requested_names = _normalize_requested_source_names(
        requested_source_names
    )
    if not normalized_requested_names:
        return []

    return [
        source
        for source in enabled_sources
        if source.name in normalized_requested_names
    ]
