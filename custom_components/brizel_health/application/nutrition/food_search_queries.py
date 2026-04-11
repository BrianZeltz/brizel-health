"""Application queries for searching external food sources."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from ...domains.nutrition.models.external_food_search_result import (
    ExternalFoodSearchResult,
)
from .food_import_use_cases import search_external_foods
from .import_selection import select_import_sources
from .source_registry import FoodSourceRegistry

SEARCH_STATUS_SUCCESS = "success"
SEARCH_STATUS_FAILURE = "failure"


def _normalize_requested_source_names(
    source_names: Iterable[str] | None,
) -> list[str] | None:
    """Normalize requested source names for source selection."""
    if source_names is None:
        return None

    normalized = [str(source_name).strip().lower() for source_name in source_names]
    return [source_name for source_name in normalized if source_name]


@dataclass(slots=True)
class FoodSourceSearchResult:
    """Per-source result of an external food search."""

    source_name: str
    status: str
    results: list[ExternalFoodSearchResult]
    error: str | None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the search result for service responses."""
        return {
            "source_name": self.source_name,
            "status": self.status,
            "results": [result.to_dict() for result in self.results],
            "error": self.error,
        }


async def search_foods_from_sources(
    registry: FoodSourceRegistry,
    query: str,
    *,
    requested_source_names: Iterable[str] | None = None,
    limit_per_source: int = 10,
) -> list[FoodSourceSearchResult]:
    """Search one or more enabled food sources without importing results."""
    normalized_requested_names = _normalize_requested_source_names(
        requested_source_names
    )
    selected_sources = select_import_sources(
        registry,
        requested_source_names=normalized_requested_names,
    )
    selected_source_names = {source.name for source in selected_sources}

    results: list[FoodSourceSearchResult] = []

    if normalized_requested_names is not None:
        for source_name in normalized_requested_names:
            if source_name in selected_source_names:
                continue
            results.append(
                FoodSourceSearchResult(
                    source_name=source_name,
                    status=SEARCH_STATUS_FAILURE,
                    results=[],
                    error="Source is not registered or is disabled.",
                )
            )

    for source in selected_sources:
        try:
            search_results = await search_external_foods(
                source.adapter,
                query,
                limit=limit_per_source,
            )
        except Exception as err:
            results.append(
                FoodSourceSearchResult(
                    source_name=source.name,
                    status=SEARCH_STATUS_FAILURE,
                    results=[],
                    error=str(err),
                )
            )
            continue

        results.append(
            FoodSourceSearchResult(
                source_name=source.name,
                status=SEARCH_STATUS_SUCCESS,
                results=search_results,
                error=None,
            )
        )

    return results
