"""Application queries for searching external food sources."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from ...domains.nutrition.models.external_food_search_result import (
    ExternalFoodSearchResult,
)
from .food_import_use_cases import search_external_foods
from .import_selection import select_import_sources
from .search_intelligence import SearchQueryVariant, build_search_query_variants
from .source_registry import FoodSourceRegistry

SEARCH_STATUS_SUCCESS = "success"
SEARCH_STATUS_FAILURE = "failure"
SEARCH_STATUS_EMPTY = "empty"


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


@dataclass(slots=True)
class AggregatedFoodSearchResult:
    """Combined multi-source search response for UI-driven food lookups."""

    status: str
    results: list[ExternalFoodSearchResult]
    source_results: list[FoodSourceSearchResult]
    error: str | None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the aggregated result for service responses."""
        return {
            "status": self.status,
            "results": [result.to_dict() for result in self.results],
            "source_results": [
                source_result.to_dict() for source_result in self.source_results
            ],
            "error": self.error,
        }


@dataclass(slots=True)
class _CollectedSearchResult:
    """Internal aggregated search hit collected across variants and sources."""

    result: ExternalFoodSearchResult
    source_priority: int
    best_score: int
    matched_variants: set[str] = field(default_factory=set)


@dataclass(slots=True)
class _CollectedSourceBucket:
    """Internal per-source bucket collected across query variants."""

    source_name: str
    source_priority: int
    status: str = SEARCH_STATUS_FAILURE
    error: str | None = None
    results: dict[str, _CollectedSearchResult] = field(default_factory=dict)


def _tokenize_query(query: str) -> tuple[str, ...]:
    """Split one search query into stable lower-case tokens."""
    tokens = [token for token in query.strip().casefold().split() if token]
    return tuple(tokens)


def _score_search_result(
    query: str,
    result: ExternalFoodSearchResult,
    *,
    source_priority: int,
    rank_bonus: int = 0,
) -> int:
    """Score one source-neutral result for simple cross-source ranking."""
    normalized_query = query.strip().casefold()
    query_tokens = _tokenize_query(query)
    name = result.name.casefold()
    brand = (result.brand or "").casefold()
    score = 0

    if name == normalized_query:
        score += 1000
    if brand and brand == normalized_query:
        score += 240
    if name.startswith(normalized_query):
        score += 480
    if brand.startswith(normalized_query):
        score += 140
    if normalized_query and normalized_query in name:
        score += 220
    if normalized_query and brand and normalized_query in brand:
        score += 100

    if query_tokens:
        matched_name_tokens = sum(token in name for token in query_tokens)
        matched_brand_tokens = sum(token in brand for token in query_tokens)
        score += matched_name_tokens * 70
        score += matched_brand_tokens * 30
        if all(token in name for token in query_tokens):
            score += 180
        if brand and all(token in brand for token in query_tokens):
            score += 60

    if result.brand:
        score += 10
    if all(
        value is not None
        for value in (
            result.kcal_per_100g,
            result.protein_per_100g,
            result.carbs_per_100g,
            result.fat_per_100g,
        )
    ):
        score += 40

    score += rank_bonus
    score += max(0, 100 - int(source_priority))
    return score


def _combine_ranked_results(
    registry: FoodSourceRegistry,
    query: str,
    source_results: list[FoodSourceSearchResult],
) -> list[ExternalFoodSearchResult]:
    """Combine successful source buckets into one ranked result list."""
    source_priorities = {
        source.name: source.priority for source in registry.list_sources(enabled_only=False)
    }
    ranked_results: list[tuple[int, int, str, str, str, ExternalFoodSearchResult]] = []

    for source_result in source_results:
        if source_result.status != SEARCH_STATUS_SUCCESS:
            continue

        source_priority = source_priorities.get(source_result.source_name, 100)
        for index, result in enumerate(source_result.results):
            ranked_results.append(
                (
                    _score_search_result(
                        query,
                        result,
                        source_priority=source_priority,
                    ),
                    source_priority,
                    result.name.casefold(),
                    (result.brand or "").casefold(),
                    f"{source_result.source_name}:{result.source_id}:{index}",
                    result,
                )
            )

    ranked_results.sort(
        key=lambda item: (
            -item[0],
            item[1],
            item[2],
            item[3],
            item[4],
        )
    )
    return [item[-1] for item in ranked_results]


def aggregate_food_search_results(
    registry: FoodSourceRegistry,
    query: str,
    source_results: list[FoodSourceSearchResult],
) -> AggregatedFoodSearchResult:
    """Aggregate per-source buckets into one multi-source search response."""
    combined_results = _combine_ranked_results(registry, query, source_results)
    successful_sources = [
        source_result
        for source_result in source_results
        if source_result.status == SEARCH_STATUS_SUCCESS
    ]
    failed_sources = [
        source_result
        for source_result in source_results
        if source_result.status == SEARCH_STATUS_FAILURE
    ]

    if combined_results:
        status = SEARCH_STATUS_SUCCESS
        error = None
    elif successful_sources:
        status = SEARCH_STATUS_EMPTY
        error = None
    elif failed_sources:
        status = SEARCH_STATUS_FAILURE
        error = "All requested food sources failed."
    else:
        status = SEARCH_STATUS_FAILURE
        error = "No enabled food sources are available."

    return AggregatedFoodSearchResult(
        status=status,
        results=combined_results,
        source_results=source_results,
        error=error,
    )


async def search_foods_from_sources_aggregated(
    registry: FoodSourceRegistry,
    query: str,
    *,
    requested_source_names: Iterable[str] | None = None,
    limit_per_source: int = 10,
) -> AggregatedFoodSearchResult:
    """Search one or more sources using controlled query expansion."""
    variants = build_search_query_variants(query)
    if not variants:
        return AggregatedFoodSearchResult(
            status=SEARCH_STATUS_EMPTY,
            results=[],
            source_results=[],
            error=None,
        )

    normalized_requested_names = _normalize_requested_source_names(
        requested_source_names
    )
    source_priorities = {
        source.name: source.priority
        for source in registry.list_sources(enabled_only=False)
    }
    collected_results: dict[tuple[str, str], _CollectedSearchResult] = {}
    source_buckets: dict[str, _CollectedSourceBucket] = {}

    for variant in variants:
        variant_source_results = await search_foods_from_sources(
            registry,
            variant.text,
            requested_source_names=normalized_requested_names,
            limit_per_source=limit_per_source,
        )
        _merge_variant_source_results(
            collected_results=collected_results,
            source_buckets=source_buckets,
            source_priorities=source_priorities,
            variant=variant,
            source_results=variant_source_results,
        )

    finalized_source_results = _finalize_source_buckets(source_buckets)
    return _build_intelligent_aggregated_result(
        collected_results=collected_results,
        source_results=finalized_source_results,
    )


def _merge_variant_source_results(
    *,
    collected_results: dict[tuple[str, str], _CollectedSearchResult],
    source_buckets: dict[str, _CollectedSourceBucket],
    source_priorities: dict[str, int],
    variant: SearchQueryVariant,
    source_results: list[FoodSourceSearchResult],
) -> None:
    """Merge one variant search run into aggregated source/result buckets."""
    for source_result in source_results:
        source_priority = source_priorities.get(source_result.source_name, 100)
        bucket = source_buckets.setdefault(
            source_result.source_name,
            _CollectedSourceBucket(
                source_name=source_result.source_name,
                source_priority=source_priority,
            ),
        )

        if source_result.status != SEARCH_STATUS_SUCCESS:
            if bucket.status != SEARCH_STATUS_SUCCESS and bucket.error is None:
                bucket.error = source_result.error
            continue

        bucket.status = SEARCH_STATUS_SUCCESS
        bucket.error = None

        for result in source_result.results:
            result_key = (result.source_name, result.source_id)
            result_score = _score_search_result(
                variant.text,
                result,
                source_priority=source_priority,
                rank_bonus=variant.rank_bonus,
            )
            variant_key = variant.text.casefold()

            collected = collected_results.get(result_key)
            if collected is None:
                collected = _CollectedSearchResult(
                    result=result,
                    source_priority=source_priority,
                    best_score=result_score,
                    matched_variants={variant_key},
                )
                collected_results[result_key] = collected
            else:
                collected.best_score = max(collected.best_score, result_score)
                collected.matched_variants.add(variant_key)

            source_collected = bucket.results.get(result.source_id)
            if source_collected is None:
                bucket.results[result.source_id] = _CollectedSearchResult(
                    result=result,
                    source_priority=source_priority,
                    best_score=result_score,
                    matched_variants={variant_key},
                )
            else:
                source_collected.best_score = max(source_collected.best_score, result_score)
                source_collected.matched_variants.add(variant_key)


def _sort_collected_results(
    collected_results: list[_CollectedSearchResult],
) -> list[ExternalFoodSearchResult]:
    """Sort deduplicated results into one stable list."""
    ranked = sorted(
        collected_results,
        key=lambda collected: (
            -(
                collected.best_score
                + max(0, len(collected.matched_variants) - 1) * 25
            ),
            collected.source_priority,
            collected.result.name.casefold(),
            (collected.result.brand or "").casefold(),
            f"{collected.result.source_name}:{collected.result.source_id}",
        ),
    )
    return [collected.result for collected in ranked]


def _finalize_source_buckets(
    source_buckets: dict[str, _CollectedSourceBucket],
) -> list[FoodSourceSearchResult]:
    """Convert internal per-source buckets into API response buckets."""
    finalized: list[FoodSourceSearchResult] = []
    for bucket in sorted(
        source_buckets.values(),
        key=lambda item: (item.source_priority, item.source_name),
    ):
        finalized.append(
            FoodSourceSearchResult(
                source_name=bucket.source_name,
                status=bucket.status,
                results=_sort_collected_results(list(bucket.results.values())),
                error=bucket.error,
            )
        )
    return finalized


def _build_intelligent_aggregated_result(
    *,
    collected_results: dict[tuple[str, str], _CollectedSearchResult],
    source_results: list[FoodSourceSearchResult],
) -> AggregatedFoodSearchResult:
    """Build the final aggregated response for the intelligent search path."""
    combined_results = _sort_collected_results(list(collected_results.values()))
    successful_sources = [
        source_result
        for source_result in source_results
        if source_result.status == SEARCH_STATUS_SUCCESS
    ]
    failed_sources = [
        source_result
        for source_result in source_results
        if source_result.status == SEARCH_STATUS_FAILURE
    ]

    if combined_results:
        status = SEARCH_STATUS_SUCCESS
        error = None
    elif successful_sources:
        status = SEARCH_STATUS_EMPTY
        error = None
    elif failed_sources:
        status = SEARCH_STATUS_FAILURE
        error = "All requested food sources failed."
    else:
        status = SEARCH_STATUS_FAILURE
        error = "No enabled food sources are available."

    return AggregatedFoodSearchResult(
        status=status,
        results=combined_results,
        source_results=source_results,
        error=error,
    )


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
