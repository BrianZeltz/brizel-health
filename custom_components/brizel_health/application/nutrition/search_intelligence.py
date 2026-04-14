"""Conservative query normalization, expansion and intent hints for food search."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

SUPPORTED_SEARCH_LANGUAGES = ("de", "en")
MAX_QUERY_VARIANTS = 5

_GERMAN_ORTHOGRAPHY_REPLACEMENTS = {
    "\u00e4": "ae",
    "\u00f6": "oe",
    "\u00fc": "ue",
    "\u00df": "ss",
}
_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")

_FOOD_QUERY_FALLBACKS: dict[str, tuple[str, ...]] = {
    "apfel": ("apple",),
    "apfel granny smith": ("granny smith apple", "apple granny smith"),
    "apple": ("apfel",),
    "banane": ("banana",),
    "banana": ("banane",),
    "broetchen": ("bread roll",),
    "brotchen": ("broetchen", "bread roll"),
    "br\u00f6tchen": ("broetchen", "bread roll"),
    "carrot": ("karotte", "mohre"),
    "gouda": ("gouda cheese",),
    "gouda kaese": ("gouda cheese",),
    "gouda kase": ("gouda cheese",),
    "gouda k\u00e4se": ("gouda cheese",),
    "granny smith apfel": ("granny smith apple", "apple granny smith"),
    "joghurt": ("yogurt", "yoghurt"),
    "jogurt": ("yogurt", "yoghurt"),
    "karotte": ("carrot",),
    "k\u00e4se": ("kaese", "cheese"),
    "kaese": ("cheese",),
    "kase": ("kaese", "cheese"),
    "milch": ("milk",),
    "milch fettarm": ("low fat milk", "milk low fat"),
    "milk": ("milch",),
    "milk low fat": ("low fat milk",),
    "gut & guenstig": ("gut und guenstig", "gut guenstig"),
    "gut und guenstig": ("gut guenstig", "gut & guenstig"),
    "gut guenstig": ("gut und guenstig", "gut & guenstig"),
    "mac & cheese": ("mac and cheese", "mac cheese"),
    "mac and cheese": ("mac cheese", "mac & cheese"),
    "mac cheese": ("mac and cheese", "mac & cheese"),
    "mohre": ("moehre", "karotte", "carrot"),
    "moehre": ("karotte", "carrot"),
    "m\u00f6hre": ("moehre", "karotte", "carrot"),
    "nudeln": ("pasta", "noodles"),
    "pasta": ("nudeln",),
    "potato": ("kartoffel",),
    "reis": ("rice",),
    "reis gekocht": ("cooked rice", "rice cooked"),
    "rice": ("reis",),
    "rice cooked": ("cooked rice",),
    "yoghurt": ("yogurt",),
    "yogurt": ("yoghurt",),
}
_GENERIC_FOOD_BASE_TOKENS = {
    "apfel",
    "apple",
    "banane",
    "banana",
    "bratkartoffel",
    "bread",
    "broetchen",
    "brotchen",
    "br\u00f6tchen",
    "cappuccino",
    "carrot",
    "cheese",
    "gouda",
    "joghurt",
    "karotte",
    "kartoffel",
    "kaese",
    "kase",
    "kartoffeln",
    "milk",
    "milch",
    "mohre",
    "moehre",
    "noodles",
    "nudeln",
    "pasta",
    "potato",
    "reis",
    "rice",
    "roll",
    "yogurt",
    "yoghurt",
}
_GENERIC_FOOD_QUALIFIER_TOKENS = {
    "apple",
    "cooked",
    "fat",
    "fettarm",
    "gekocht",
    "granny",
    "jung",
    "low",
    "raw",
    "rice",
    "roh",
    "smith",
}
_KNOWN_BRAND_PHRASES: dict[str, tuple[str, ...]] = {
    "barilla": ("barilla",),
    "coca cola": ("coca", "cola"),
    "edeka": ("edeka",),
    "gut guenstig": ("gut", "guenstig"),
    "gut bio": ("gut", "bio"),
    "gut und guenstig": ("gut", "guenstig"),
    "ja": ("ja",),
    "kaufland": ("kaufland",),
    "k classic": ("k", "classic"),
    "kinder": ("kinder",),
    "lidl": ("lidl",),
    "milbona": ("milbona",),
    "nutella": ("nutella",),
    "rewe beste wahl": ("rewe", "beste", "wahl"),
    "rewe": ("rewe",),
}
_GERMAN_MARKET_BRAND_TOKENS = {
    "aldi",
    "barilla",
    "coca",
    "cola",
    "edeka",
    "ja",
    "gut",
    "guenstig",
    "kaufland",
    "k",
    "classic",
    "kinder",
    "lidl",
    "milbona",
    "netto",
    "penny",
    "rewe",
    "nutella",
}
_GERMAN_LANGUAGE_HINT_TOKENS = {
    "apfel",
    "broetchen",
    "kaese",
    "milch",
    "mohre",
    "moehre",
}
_ENGLISH_LANGUAGE_HINT_TOKENS = {
    "apple",
    "banana",
    "bread",
    "carrot",
    "cheese",
    "milk",
}
_OPTIONAL_CONNECTOR_TOKENS = {"und", "and"}


@dataclass(frozen=True, slots=True)
class SearchQueryVariant:
    """One generated query variant used for controlled external search expansion."""

    text: str
    kind: str
    rank_bonus: int


@dataclass(frozen=True, slots=True)
class SearchQueryAnalysis:
    """Small, explicit query-analysis payload for locale-aware ranking."""

    normalized_query: str
    matching_query: str
    tokens: tuple[str, ...]
    brand_tokens: tuple[str, ...]
    product_tokens: tuple[str, ...]
    likely_language: str | None
    looks_german: bool
    looks_generic_food: bool
    looks_product_like: bool


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


def normalize_search_text_for_matching(query: str) -> str:
    """Return one ASCII-friendly comparison form for ranking and tokenization."""
    expanded = expand_german_orthography(query)
    decomposed = unicodedata.normalize("NFKD", expanded)
    return "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )


def tokenize_search_text(query: str) -> tuple[str, ...]:
    """Split text into conservative lowercase ASCII-like tokens."""
    normalized = normalize_search_text_for_matching(query)
    tokens = [token for token in _TOKEN_SPLIT_RE.split(normalized) if token]
    return tuple(tokens)


def _lookup_keys(query: str) -> tuple[str, ...]:
    """Return stable lookup keys for fallback matching."""
    keys: list[str] = []
    seen: set[str] = set()
    for candidate in (
        casefold_search_query(query),
        expand_german_orthography(query),
        strip_diacritics(query),
        normalize_search_text_for_matching(query),
    ):
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        keys.append(candidate)
    return tuple(keys)


def _resolve_fallback_queries(query: str) -> list[str]:
    """Return small, explicit food-specific fallback queries for phase 1+2."""
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


def _resolve_connector_variants(query: str) -> list[str]:
    """Return a few connector-tolerant phrase variants for real brand spellings."""
    normalized_query = normalize_search_query(query)
    if not normalized_query:
        return []

    lowered = casefold_search_query(query)
    if "&" not in lowered and " und " not in f" {lowered} " and " and " not in f" {lowered} ":
        return []

    raw_parts = re.split(r"\s*(?:&|\bund\b|\band\b)\s*", normalized_query, flags=re.IGNORECASE)
    parts = [part.strip() for part in raw_parts if part.strip()]
    if len(parts) < 2:
        return []

    variants: list[str] = []
    seen: set[str] = set()
    for candidate in (
        " und ".join(parts),
        " & ".join(parts),
        " ".join(parts),
    ):
        dedupe_key = candidate.casefold()
        if dedupe_key == lowered or dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        variants.append(candidate)
    return variants


def _detect_likely_language(query: str, tokens: tuple[str, ...]) -> str | None:
    """Return one small language hint used for locale-aware ranking."""
    raw_query = normalize_search_query(query)
    if any(
        character in raw_query.casefold()
        for character in ("\u00e4", "\u00f6", "\u00fc", "\u00df")
    ):
        return "de"
    if any(token in _GERMAN_MARKET_BRAND_TOKENS for token in tokens):
        return "de"
    if any(token in _GERMAN_LANGUAGE_HINT_TOKENS for token in tokens):
        return "de"
    if any(token in _ENGLISH_LANGUAGE_HINT_TOKENS for token in tokens):
        return "en"
    return None


def _resolve_brand_and_product_tokens(
    tokens: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split a small set of known brand-first queries into brand and product tokens."""
    for brand_phrase, brand_tokens in sorted(
        _KNOWN_BRAND_PHRASES.items(),
        key=lambda item: len(tokenize_search_text(item[0])),
        reverse=True,
    ):
        brand_phrase_tokens = tokenize_search_text(brand_phrase)
        if not brand_phrase_tokens:
            continue
        if tokens[: len(brand_phrase_tokens)] == brand_phrase_tokens:
            product_tokens = tokens[len(brand_phrase_tokens) :]
            return tuple(brand_tokens), product_tokens

    if len(tokens) >= 2 and tokens[0] in _GERMAN_MARKET_BRAND_TOKENS:
        return (tokens[0],), tokens[1:]

    return (), tokens


def analyze_search_query(query: str) -> SearchQueryAnalysis:
    """Build one small, explicit query-analysis object for ranking decisions."""
    normalized_query = normalize_search_query(query)
    matching_query = normalize_search_text_for_matching(query)
    tokens = tokenize_search_text(query)
    brand_tokens, product_tokens = _resolve_brand_and_product_tokens(tokens)
    likely_language = _detect_likely_language(normalized_query, tokens)
    looks_german = likely_language == "de"
    token_set = set(tokens)
    has_generic_base_token = bool(token_set & _GENERIC_FOOD_BASE_TOKENS)
    looks_generic_food = (
        bool(tokens)
        and not brand_tokens
        and has_generic_base_token
        and all(
            token in _GENERIC_FOOD_BASE_TOKENS
            or token in _GENERIC_FOOD_QUALIFIER_TOKENS
            for token in tokens
        )
    )
    looks_product_like = bool(brand_tokens)

    return SearchQueryAnalysis(
        normalized_query=normalized_query,
        matching_query=matching_query,
        tokens=tokens,
        brand_tokens=brand_tokens,
        product_tokens=product_tokens,
        likely_language=likely_language,
        looks_german=looks_german,
        looks_generic_food=looks_generic_food,
        looks_product_like=looks_product_like,
    )


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
    analysis = analyze_search_query(normalized_query)

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
    add_variant(
        expand_german_orthography(normalized_query),
        kind="orthography",
        rank_bonus=280,
    )
    if not analysis.looks_product_like:
        add_variant(
            strip_diacritics(normalized_query),
            kind="diacritic",
            rank_bonus=240,
        )

    for connector_variant in _resolve_connector_variants(normalized_query):
        add_variant(
            connector_variant,
            kind="connector",
            rank_bonus=220,
        )

    if analysis.brand_tokens and analysis.product_tokens:
        add_variant(
            " ".join(analysis.brand_tokens),
            kind="brand",
            rank_bonus=170,
        )

    for fallback in _resolve_fallback_queries(normalized_query):
        add_variant(fallback, kind="fallback", rank_bonus=190)

    return variants
