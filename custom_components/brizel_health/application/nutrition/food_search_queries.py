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
from .search_context import FoodSearchContext, context_recent_token_overlap
from .search_intelligence import (
    SearchQueryAnalysis,
    SearchQueryVariant,
    analyze_search_query,
    build_search_query_variants,
    normalize_search_text_for_matching,
    tokenize_search_text,
)
from .source_registry import FoodSourceRegistry

SEARCH_STATUS_SUCCESS = "success"
SEARCH_STATUS_FAILURE = "failure"
SEARCH_STATUS_EMPTY = "empty"

_GERMANY_MARKET_TERMS = ("germany", "deutschland", "de")
_EU_MARKET_TERMS = ("eu", "europe", "european union")
_USA_MARKET_TERMS = ("us", "usa", "united states", "na", "north america")
_GERMAN_BRAND_TOKENS = {"ja", "gut", "guenstig", "k", "classic", "milbona", "kinder"}
_GERMAN_RETAILER_TOKENS = {
    "aldi",
    "edeka",
    "kaufland",
    "lidl",
    "netto",
    "penny",
    "rewe",
}
_GERMAN_LANGUAGE_CODES = {"de", "deu", "german", "deutsch"}
_ENGLISH_LANGUAGE_CODES = {"en", "eng", "english"}
_LEGACY_NEUTRAL_SOURCE_PRIORITIES = {
    "bls": 15,
    "open_food_facts": 20,
    "usda": 10,
}
_NEUTRAL_PRIORITY_SORT_VALUE = 100
_MAX_PRIORITY_OVERRIDE_BONUS = 60


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


@dataclass(frozen=True, slots=True)
class _SourcePriorityContext:
    """Resolved view of source priorities for one search run."""

    manual_override_active: bool
    bonus_by_source: dict[str, int]
    sort_value_by_source: dict[str, int]


def _tokenize_query(query: str) -> tuple[str, ...]:
    """Split one search query into stable tokens."""
    return tokenize_search_text(query)


def _market_tag_matches(values: Iterable[str], term: str) -> bool:
    """Return whether one normalized market tag collection contains a term."""
    term_tokens = set(tokenize_search_text(term))
    if not term_tokens:
        return False

    for value in values:
        value_tokens = set(tokenize_search_text(value))
        if term_tokens <= value_tokens:
            return True
    return False


def _token_set_from_terms(values: Iterable[str]) -> set[str]:
    """Return one flattened normalized token set from free-form search tags."""
    tokens: set[str] = set()
    for value in values:
        tokens.update(tokenize_search_text(value))
    return tokens


def _resolve_source_priority_context(
    source_priorities: dict[str, int],
) -> _SourcePriorityContext:
    """Resolve whether manual source priorities should influence ranking."""
    relevant_priorities = {
        source_name: int(priority)
        for source_name, priority in source_priorities.items()
    }
    if not relevant_priorities:
        return _SourcePriorityContext(
            manual_override_active=False,
            bonus_by_source={},
            sort_value_by_source={},
        )

    distinct_priorities = {priority for priority in relevant_priorities.values()}
    matches_legacy_neutral_defaults = all(
        _LEGACY_NEUTRAL_SOURCE_PRIORITIES.get(source_name) == priority
        for source_name, priority in relevant_priorities.items()
    )
    manual_override_active = (
        len(distinct_priorities) > 1 and not matches_legacy_neutral_defaults
    )

    if not manual_override_active:
        return _SourcePriorityContext(
            manual_override_active=False,
            bonus_by_source={source_name: 0 for source_name in relevant_priorities},
            sort_value_by_source={
                source_name: _NEUTRAL_PRIORITY_SORT_VALUE
                for source_name in relevant_priorities
            },
        )

    average_priority = sum(relevant_priorities.values()) / len(relevant_priorities)
    bonus_by_source: dict[str, int] = {}
    for source_name, priority in relevant_priorities.items():
        delta = average_priority - priority
        bonus_by_source[source_name] = max(
            -_MAX_PRIORITY_OVERRIDE_BONUS,
            min(_MAX_PRIORITY_OVERRIDE_BONUS, int(round(delta * 6))),
        )

    return _SourcePriorityContext(
        manual_override_active=True,
        bonus_by_source=bonus_by_source,
        sort_value_by_source=relevant_priorities,
    )


def _is_germany_context(
    search_context: FoodSearchContext | None,
    query_analysis: SearchQueryAnalysis,
) -> bool:
    """Return whether Germany/de-DE style ranking should be active."""
    if search_context is None:
        return query_analysis.looks_german
    return (
        search_context.preferred_region == "germany"
        or (
            search_context.preferred_region == "eu"
            and search_context.preferred_language == "de"
        )
        or search_context.preferred_language == "de"
        or query_analysis.looks_german
    )


def _is_usa_context(search_context: FoodSearchContext | None) -> bool:
    """Return whether USA/imperial style ranking should be active."""
    if search_context is None:
        return False
    return search_context.preferred_region == "usa"


def _score_brand_and_product_match(
    query_analysis: SearchQueryAnalysis,
    *,
    normalized_name: str,
    normalized_brand: str,
    name_tokens: set[str],
    brand_tokens: set[str],
) -> int:
    """Return one explicit brand/product decomposition score."""
    score = 0

    if query_analysis.matching_query:
        if query_analysis.matching_query in normalized_name:
            score += 240
        if normalized_brand and query_analysis.matching_query in normalized_brand:
            score += 160

    brand_query_tokens = set(query_analysis.brand_tokens)
    product_query_tokens = set(query_analysis.product_tokens)

    if brand_query_tokens:
        matched_brand_tokens = sum(token in brand_tokens for token in brand_query_tokens)
        matched_name_tokens = sum(token in name_tokens for token in brand_query_tokens)
        score += matched_brand_tokens * 120
        score += matched_name_tokens * 35
        if brand_query_tokens <= brand_tokens:
            score += 170
        elif brand_query_tokens <= name_tokens:
            score += 70

    if product_query_tokens:
        matched_name_tokens = sum(token in name_tokens for token in product_query_tokens)
        matched_brand_tokens = sum(token in brand_tokens for token in product_query_tokens)
        score += matched_name_tokens * 80
        score += matched_brand_tokens * 20
        if product_query_tokens <= name_tokens:
            score += 110

    if brand_query_tokens and product_query_tokens:
        brand_match = brand_query_tokens <= brand_tokens or brand_query_tokens <= name_tokens
        product_match = (
            product_query_tokens <= name_tokens or product_query_tokens <= brand_tokens
        )
        if brand_match and product_match:
            score += 180

    return score


def _score_generic_food_match(
    query_analysis: SearchQueryAnalysis,
    result: ExternalFoodSearchResult,
    *,
    name_tokens: set[str],
) -> int:
    """Return a small bias toward generic foods for generic food queries."""
    if not query_analysis.looks_generic_food:
        return 0

    score = 0
    query_tokens = set(query_analysis.tokens)
    if query_tokens and query_tokens <= name_tokens:
        score += 130
    if not result.brand:
        score += 60
    else:
        score -= 80
    if result.source_name == "bls":
        score += 55
    if len(name_tokens) <= len(query_tokens) + 2:
        score += 25
    return score


def _score_off_locale_signals(
    result: ExternalFoodSearchResult,
    *,
    search_context: FoodSearchContext | None,
    query_analysis: SearchQueryAnalysis,
) -> int:
    """Return OFF-specific locale and retail relevance signals."""
    if result.source_name != "open_food_facts":
        return 0

    language_codes = set(result.language_codes)
    store_tokens = _token_set_from_terms(result.store_tags)
    category_tokens = _token_set_from_terms(result.category_tags)
    query_tokens = set(query_analysis.tokens)
    score = 0

    if _is_germany_context(search_context, query_analysis):
        german_store_hits = len(store_tokens & _GERMAN_RETAILER_TOKENS)
        if query_analysis.looks_product_like:
            if language_codes & _GERMAN_LANGUAGE_CODES:
                score += 95
            elif language_codes and not (language_codes & _ENGLISH_LANGUAGE_CODES):
                score -= 15
            score += min(2, german_store_hits) * 70
            if german_store_hits:
                score += 55
        else:
            if language_codes & _GERMAN_LANGUAGE_CODES:
                score += 15
            score += min(2, german_store_hits) * 5

        if query_analysis.looks_generic_food:
            if not result.brand:
                score += 10
            else:
                score -= 40
            if query_tokens & category_tokens:
                score += 15

        if not result.market_country_codes and not result.market_region_codes:
            score -= 10

    elif _is_usa_context(search_context):
        if language_codes & _GERMAN_LANGUAGE_CODES:
            score -= 10

    return score


def _score_source_strategy(
    result: ExternalFoodSearchResult,
    *,
    search_context: FoodSearchContext | None,
    query_analysis: SearchQueryAnalysis,
) -> int:
    """Return one conservative source-strategy score contribution."""
    score = 0
    source_name = result.source_name
    germany_context = _is_germany_context(search_context, query_analysis)
    usa_context = _is_usa_context(search_context)
    eu_context = search_context is not None and search_context.preferred_region == "eu"

    if query_analysis.looks_product_like:
        if source_name == "open_food_facts":
            score += 210 if germany_context else 170
        elif source_name == "bls":
            score -= 45 if germany_context else -35
        elif source_name == "usda":
            score += 40 if usa_context else -90 if germany_context else -35
        return score

    if query_analysis.looks_generic_food:
        if germany_context:
            if source_name == "bls":
                score += 620
            elif source_name == "open_food_facts":
                score += 25
            elif source_name == "usda":
                score -= 145
            return score

        if usa_context:
            if source_name == "usda":
                score += 185
            elif source_name == "open_food_facts":
                score += 20
            elif source_name == "bls":
                score -= 90
            return score

        if eu_context:
            if source_name == "bls":
                score += 125
            elif source_name == "open_food_facts":
                score += 40
            elif source_name == "usda":
                score -= 45
            return score

        if source_name == "open_food_facts":
            score += 20
        elif source_name == "usda":
            score += 10
        elif source_name == "bls":
            score += 35
        return score

    if germany_context:
        if source_name == "open_food_facts":
            score += 60
        elif source_name == "bls":
            score += 35
        elif source_name == "usda":
            score -= 45
    elif usa_context:
        if source_name == "open_food_facts":
            score += 30
        elif source_name == "usda":
            score += 35
        elif source_name == "bls":
            score -= 25
    elif eu_context:
        if source_name == "open_food_facts":
            score += 20
        elif source_name == "bls":
            score += 15

    return score


def _score_market_preference(
    result: ExternalFoodSearchResult,
    *,
    search_context: FoodSearchContext | None,
    query_analysis: SearchQueryAnalysis,
    brand_tokens: set[str],
) -> int:
    """Return one conservative locale/market score contribution."""
    country_codes = result.market_country_codes
    region_codes = result.market_region_codes

    has_germany_market = any(
        _market_tag_matches(country_codes, term) for term in _GERMANY_MARKET_TERMS
    )
    has_eu_market = (
        has_germany_market
        or any(_market_tag_matches(region_codes, term) for term in _EU_MARKET_TERMS)
    )
    has_usa_market = any(
        _market_tag_matches(country_codes, term) or _market_tag_matches(region_codes, term)
        for term in _USA_MARKET_TERMS
    )

    score = 0
    if _is_germany_context(search_context, query_analysis):
        if has_germany_market:
            score += 210
        elif has_eu_market:
            score += 110
        elif has_usa_market:
            score -= 105

        if result.source_name == "open_food_facts":
            score += 40
        if result.source_name == "usda":
            score -= 40

        if query_analysis.looks_german:
            if result.source_name == "open_food_facts":
                score += 65
            if result.source_name == "usda":
                score -= 80

        if set(query_analysis.brand_tokens) & _GERMAN_BRAND_TOKENS:
            if brand_tokens & _GERMAN_BRAND_TOKENS:
                score += 120
            if result.source_name == "open_food_facts":
                score += 55

        if query_analysis.looks_generic_food and result.source_name == "usda":
            score -= 45

    elif search_context is not None and search_context.preferred_region == "eu":
        if has_germany_market:
            score += 90
        elif has_eu_market:
            score += 50
        elif has_usa_market:
            score -= 25

    if _is_usa_context(search_context):
        if has_usa_market:
            score += 90
        if result.source_name == "usda":
            score += 30

    score += _score_off_locale_signals(
        result,
        search_context=search_context,
        query_analysis=query_analysis,
    )

    score += _score_source_strategy(
        result,
        search_context=search_context,
        query_analysis=query_analysis,
    )

    return score


def _score_search_result(
    query: str,
    result: ExternalFoodSearchResult,
    *,
    priority_bonus: int = 0,
    rank_bonus: int = 0,
    search_context: FoodSearchContext | None = None,
    original_query_analysis: SearchQueryAnalysis | None = None,
) -> int:
    """Score one source-neutral result for locale-aware cross-source ranking."""
    normalized_query = normalize_search_text_for_matching(query)
    query_tokens = _tokenize_query(query)
    query_token_set = set(query_tokens)
    name = normalize_search_text_for_matching(result.name)
    brand = normalize_search_text_for_matching(result.brand or "")
    name_tokens = set(tokenize_search_text(result.name))
    brand_tokens = set(tokenize_search_text(result.brand or ""))
    score = 0

    if name == normalized_query:
        score += 1000
    elif normalized_query and name.startswith(normalized_query):
        score += 480
    elif normalized_query and normalized_query in name:
        score += 220

    if brand and brand == normalized_query:
        score += 260
    elif normalized_query and brand.startswith(normalized_query):
        score += 140
    elif normalized_query and brand and normalized_query in brand:
        score += 100

    if query_tokens:
        matched_name_tokens = sum(token in name_tokens for token in query_tokens)
        matched_brand_tokens = sum(token in brand_tokens for token in query_tokens)
        score += matched_name_tokens * 70
        score += matched_brand_tokens * 30
        if query_token_set and query_token_set <= name_tokens:
            score += 180
        if brand and query_token_set and query_token_set <= brand_tokens:
            score += 60

    effective_query_analysis = original_query_analysis or analyze_search_query(query)
    score += _score_brand_and_product_match(
        effective_query_analysis,
        normalized_name=name,
        normalized_brand=brand,
        name_tokens=name_tokens,
        brand_tokens=brand_tokens,
    )
    score += _score_generic_food_match(
        effective_query_analysis,
        result,
        name_tokens=name_tokens,
    )
    score += _score_market_preference(
        result,
        search_context=search_context,
        query_analysis=effective_query_analysis,
        brand_tokens=brand_tokens,
    )

    if search_context is not None:
        score += context_recent_token_overlap(
            search_context,
            result_name=result.name,
            result_brand=result.brand,
        )

    if result.brand:
        score += 10
    if result.market_country_codes or result.market_region_codes:
        score += 8
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
    score += priority_bonus
    return score


def _has_meaningful_text_match(
    query: str,
    result: ExternalFoodSearchResult,
) -> bool:
    """Return whether a result has at least one meaningful textual relation to a query."""
    normalized_query = normalize_search_text_for_matching(query)
    if not normalized_query:
        return False

    normalized_name = normalize_search_text_for_matching(result.name)
    normalized_brand = normalize_search_text_for_matching(result.brand or "")
    if (
        normalized_name == normalized_query
        or normalized_brand == normalized_query
        or normalized_name.startswith(normalized_query)
        or (normalized_brand and normalized_brand.startswith(normalized_query))
        or normalized_query in normalized_name
        or (normalized_brand and normalized_query in normalized_brand)
    ):
        return True

    query_tokens = set(_tokenize_query(query))
    if not query_tokens:
        return False

    name_tokens = set(tokenize_search_text(result.name))
    brand_tokens = set(tokenize_search_text(result.brand or ""))
    if (
        query_tokens <= name_tokens
        or (brand_tokens and query_tokens <= brand_tokens)
        or query_tokens & name_tokens
        or query_tokens & brand_tokens
    ):
        return True

    if len(query_tokens) == 1:
        query_token = next(iter(query_tokens))
        if len(query_token) >= 4:
            for candidate_token in name_tokens | brand_tokens:
                if (
                    len(candidate_token) >= 4
                    and (
                        candidate_token.startswith(query_token)
                        or query_token.startswith(candidate_token)
                    )
                ):
                    return True

    return False


def _is_plausible_search_result(
    result: ExternalFoodSearchResult,
    *,
    query_texts: tuple[str, ...],
) -> bool:
    """Return whether a search result is good enough to surface as an actual hit."""
    return any(
        _has_meaningful_text_match(query_text, result) for query_text in query_texts
    )


def _combine_ranked_results(
    registry: FoodSourceRegistry,
    query: str,
    source_results: list[FoodSourceSearchResult],
    *,
    search_context: FoodSearchContext | None = None,
) -> list[ExternalFoodSearchResult]:
    """Combine successful source buckets into one ranked result list."""
    source_priorities = {
        source.name: source.priority for source in registry.list_sources(enabled_only=False)
    }
    priority_context = _resolve_source_priority_context(
        {
            source_result.source_name: source_priorities.get(source_result.source_name, 100)
            for source_result in source_results
        }
    )
    query_analysis = analyze_search_query(query)
    ranked_results: list[tuple[int, int, str, str, str, ExternalFoodSearchResult]] = []

    for source_result in source_results:
        if source_result.status != SEARCH_STATUS_SUCCESS:
            continue

        source_priority = source_priorities.get(source_result.source_name, 100)
        for index, result in enumerate(source_result.results):
            if not _is_plausible_search_result(result, query_texts=(query,)):
                continue
            ranked_results.append(
                (
                    _score_search_result(
                        query,
                        result,
                        priority_bonus=priority_context.bonus_by_source.get(
                            source_result.source_name,
                            0,
                        ),
                        search_context=search_context,
                        original_query_analysis=query_analysis,
                    ),
                    priority_context.sort_value_by_source.get(
                        source_result.source_name,
                        _NEUTRAL_PRIORITY_SORT_VALUE,
                    ),
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
    *,
    search_context: FoodSearchContext | None = None,
) -> AggregatedFoodSearchResult:
    """Aggregate per-source buckets into one multi-source search response."""
    combined_results = _combine_ranked_results(
        registry,
        query,
        source_results,
        search_context=search_context,
    )
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
    search_context: FoodSearchContext | None = None,
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
    priority_context = _resolve_source_priority_context(
        {
            source_name: priority
            for source_name, priority in source_priorities.items()
            if normalized_requested_names is None
            or source_name in normalized_requested_names
        }
    )
    original_query_analysis = analyze_search_query(query)
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
            priority_context=priority_context,
            variant=variant,
            source_results=variant_source_results,
            search_context=search_context,
            original_query_analysis=original_query_analysis,
        )

    finalized_source_results = _finalize_source_buckets(
        source_buckets,
        priority_context=priority_context,
    )
    return _build_intelligent_aggregated_result(
        collected_results=collected_results,
        priority_context=priority_context,
        source_results=finalized_source_results,
    )


def _merge_variant_source_results(
    *,
    collected_results: dict[tuple[str, str], _CollectedSearchResult],
    source_buckets: dict[str, _CollectedSourceBucket],
    source_priorities: dict[str, int],
    priority_context: _SourcePriorityContext,
    variant: SearchQueryVariant,
    source_results: list[FoodSourceSearchResult],
    search_context: FoodSearchContext | None,
    original_query_analysis: SearchQueryAnalysis,
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
            if not _is_plausible_search_result(
                result,
                query_texts=(original_query_analysis.normalized_query, variant.text),
            ):
                continue
            result_key = (result.source_name, result.source_id)
            result_score = _score_search_result(
                variant.text,
                result,
                priority_bonus=priority_context.bonus_by_source.get(
                    source_result.source_name,
                    0,
                ),
                rank_bonus=variant.rank_bonus,
                search_context=search_context,
                original_query_analysis=original_query_analysis,
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
    *,
    priority_context: _SourcePriorityContext,
) -> list[ExternalFoodSearchResult]:
    """Sort deduplicated results into one stable list."""
    ranked = sorted(
        collected_results,
        key=lambda collected: (
            -(
                collected.best_score
                + max(0, len(collected.matched_variants) - 1) * 25
            ),
            priority_context.sort_value_by_source.get(
                collected.result.source_name,
                _NEUTRAL_PRIORITY_SORT_VALUE,
            ),
            collected.result.name.casefold(),
            (collected.result.brand or "").casefold(),
            f"{collected.result.source_name}:{collected.result.source_id}",
        ),
    )
    return [collected.result for collected in ranked]


def _finalize_source_buckets(
    source_buckets: dict[str, _CollectedSourceBucket],
    *,
    priority_context: _SourcePriorityContext,
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
                results=_sort_collected_results(
                    list(bucket.results.values()),
                    priority_context=priority_context,
                ),
                error=bucket.error,
            )
        )
    return finalized


def _build_intelligent_aggregated_result(
    *,
    collected_results: dict[tuple[str, str], _CollectedSearchResult],
    priority_context: _SourcePriorityContext,
    source_results: list[FoodSourceSearchResult],
) -> AggregatedFoodSearchResult:
    """Build the final aggregated response for the intelligent search path."""
    combined_results = _sort_collected_results(
        list(collected_results.values()),
        priority_context=priority_context,
    )
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
