"""Central orchestration for importing foods from multiple sources."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ...domains.nutrition.interfaces.food_repository import FoodRepository
from ...domains.nutrition.interfaces.imported_food_cache_repository import (
    ImportedFoodCacheRepository,
)
from .food_import_use_cases import import_food_from_source
from .import_selection import select_import_sources
from .source_registry import FoodSourceRegistry

IMPORT_STATUS_SUCCESS = "success"
IMPORT_STATUS_FAILURE = "failure"


def _normalize_required_text(value: str, field_name: str) -> str:
    """Normalize a required text field."""
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} is required.")
    return normalized


@dataclass(slots=True)
class FoodSourceImportRequest:
    """Source-specific input for a multi-source import run."""

    source_name: str
    source_id: str

    @classmethod
    def create(
        cls,
        source_name: str,
        source_id: str,
    ) -> "FoodSourceImportRequest":
        """Create a validated import request."""
        return cls(
            source_name=_normalize_required_text(
                source_name,
                "source_name",
            ).lower(),
            source_id=_normalize_required_text(source_id, "source_id"),
        )


@dataclass(slots=True)
class FoodSourceImportResult:
    """Per-source result of a multi-source import run."""

    source_name: str
    source_id: str
    status: str
    food_id: str | None
    error: str | None


async def import_food_from_sources(
    registry: FoodSourceRegistry,
    food_repository: FoodRepository,
    cache_repository: ImportedFoodCacheRepository,
    source_requests: Iterable[FoodSourceImportRequest],
) -> list[FoodSourceImportResult]:
    """Run food imports across multiple selected sources."""
    normalized_requests = [
        FoodSourceImportRequest.create(
            source_name=request.source_name,
            source_id=request.source_id,
        )
        for request in source_requests
    ]
    request_by_source_name = {
        request.source_name: request for request in normalized_requests
    }

    selected_sources = select_import_sources(
        registry,
        requested_source_names=request_by_source_name.keys(),
    )
    selected_source_names = {source.name for source in selected_sources}

    results: list[FoodSourceImportResult] = []

    for request in normalized_requests:
        if request.source_name in selected_source_names:
            continue

        results.append(
            FoodSourceImportResult(
                source_name=request.source_name,
                source_id=request.source_id,
                status=IMPORT_STATUS_FAILURE,
                food_id=None,
                error="Source is not registered or is disabled.",
            )
        )

    for source in selected_sources:
        request = request_by_source_name[source.name]
        try:
            food = await import_food_from_source(
                food_repository=food_repository,
                cache_repository=cache_repository,
                adapter=source.adapter,
                source_id=request.source_id,
            )
        except Exception as err:
            results.append(
                FoodSourceImportResult(
                    source_name=source.name,
                    source_id=request.source_id,
                    status=IMPORT_STATUS_FAILURE,
                    food_id=None,
                    error=str(err),
                )
            )
            continue

        results.append(
            FoodSourceImportResult(
                source_name=source.name,
                source_id=request.source_id,
                status=IMPORT_STATUS_SUCCESS,
                food_id=food.food_id,
                error=None,
            )
        )

    return results
