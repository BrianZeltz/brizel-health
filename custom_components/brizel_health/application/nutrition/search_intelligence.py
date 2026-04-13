"""Conservative query normalization and expansion for external food search."""

from __future__ import annotations

from dataclasses import dataclass
import unicodedata

SUPPORTED_SEARCH_LANGUAGES = ("de", "en")
MAX_QUERY_VARIANTS = 4

_GERMAN_ORTHOGRAPHY_REPLACEMENTS = {
    "ä": "ae",
    "ö": "oe",
    "ü": "ue",
    "ß": "ss",
}

_FOOD_QUERY_FALLBACKS: dict[str, tuple[str, ...]] = {
    "apfel": ("apple",),
    "apple": ("apfel",),
    "broetchen": ("bread roll", "roll"),
    "brotchen": ("broetchen", "bread roll"),
    "brötchen": ("broetchen", "bread roll"),
    "gouda": ("gouda cheese",),
    "joghurt": ("yogurt", "yoghurt"),
    "käse": ("kaese", "cheese"),
    "kaese": ("cheese",),
    "kase": ("kaese", "cheese"),
    "milch": ("milk",),
    "milk": ("milch",),
    "yoghurt": ("yogurt",),
    "yogurt": ("yoghurt",),
}


@dataclass(frozen=True, slots=True)
class SearchQueryVariant:
    """One generated query variant used for controlled external search expansion."""

    text: str
    kind: str
    rank_bonus: int


def normalize_search_query(query: str) -> str:
    """Collapse whitespace without destroying the user's original wording."""
    return " ".join(str(query).split())


def casefold_search_query(query: str) -> str:
    """Return a stable lower-case comparison form."""
    return normalize_search_query(query).casefold()


def expand_german_orthography(query: str) -> str:
    """Expand German umlauts into common ASCII spellings."""
    normalized = casefold_search_query(query)
    for original, replacement in _GERMAN_ORTHOGRAPHY_REPLACEMENTS.items():
        normalized = normalized.replace(original, replacement)
    return normalized


def strip_diacritics(query: str) -> str:
    """Remove accents/diacritics conservatively for search fallback generation."""
    normalized = casefold_search_query(query)
    decomposed = unicodedata.normalize("NFKD", normalized)
    return "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )


def _lookup_keys(query: str) -> tuple[str, ...]:
    """Return stable lookup keys for fallback matching."""
    keys: list[str] = []
    seen: set[str] = set()
    for candidate in (
        casefold_search_query(query),
        expand_german_orthography(query),
        strip_diacritics(query),
    ):
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        keys.append(candidate)
    return tuple(keys)


def _resolve_fallback_queries(query: str) -> list[str]:
    """Return small, explicit food-specific fallback queries for phase 1."""
    fallbacks: list[str] = []
    seen: set[str] = set()
    for key in _lookup_keys(query):
        for fallback in _FOOD_QUERY_FALLBACKS.get(key, ()):
            normalized = normalize_search_query(fallback)
            dedupe_key = normalized.casefold()
            if not normalized or dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            fallbacks.append(normalized)
    return fallbacks


def build_search_query_variants(
    query: str,
    *,
    max_variants: int = MAX_QUERY_VARIANTS,
) -> list[SearchQueryVariant]:
    """Build a small, ordered list of high-signal search variants."""
    normalized_query = normalize_search_query(query)
    if not normalized_query:
        return []

    variants: list[SearchQueryVariant] = []
    seen: set[str] = set()

    def add_variant(text: str, *, kind: str, rank_bonus: int) -> None:
        if len(variants) >= max_variants:
            return

        normalized = normalize_search_query(text)
        dedupe_key = normalized.casefold()
        if not normalized or dedupe_key in seen:
            return

        seen.add(dedupe_key)
        variants.append(
            SearchQueryVariant(
                text=normalized,
                kind=kind,
                rank_bonus=rank_bonus,
            )
        )

    add_variant(normalized_query, kind="original", rank_bonus=400)
    add_variant(expand_german_orthography(normalized_query), kind="orthography", rank_bonus=280)
    add_variant(strip_diacritics(normalized_query), kind="diacritic", rank_bonus=240)

    for fallback in _resolve_fallback_queries(normalized_query):
        add_variant(fallback, kind="fallback", rank_bonus=190)

    return variants
