"""Tests for query normalization and expansion in external food search."""

from __future__ import annotations

from custom_components.brizel_health.application.nutrition.search_intelligence import (
    analyze_search_query,
    build_search_query_variants,
    casefold_search_query,
    expand_german_orthography,
    normalize_search_query,
    normalize_search_text_for_matching,
    strip_diacritics,
    tokenize_search_text,
)


def test_normalize_search_query_trims_and_collapses_whitespace() -> None:
    """Whitespace-heavy queries should be normalized conservatively."""
    assert normalize_search_query("  apple   juice  ") == "apple juice"


def test_casefold_search_query_is_case_insensitive() -> None:
    """Case handling should be stable for search comparisons."""
    assert casefold_search_query("  ApFeL  ") == "apfel"


def test_expand_german_orthography_handles_umlauts_and_sz() -> None:
    """German orthography expansion should cover the supported cases."""
    assert expand_german_orthography("Brötchen groß") == "broetchen gross"


def test_strip_diacritics_preserves_ascii_fallbacks() -> None:
    """Accent stripping should provide a safe ASCII-oriented fallback."""
    assert strip_diacritics("Brötchen Café") == "brotchen cafe"


def test_tokenize_search_text_normalizes_german_and_brand_punctuation() -> None:
    """Tokenization should stay stable across umlauts and brand punctuation."""
    assert tokenize_search_text("Gut & Günstig") == ("gut", "guenstig")


def test_normalize_search_text_for_matching_supports_german_ascii_matching() -> None:
    """Matching normalization should keep German ASCII fallbacks stable."""
    assert normalize_search_text_for_matching("Möhre") == "moehre"


def test_build_search_query_variants_for_broetchen_is_small_and_high_signal() -> None:
    """Broetchen should expand into a few useful German/English variants."""
    variants = build_search_query_variants("  Brötchen  ")

    assert [variant.text for variant in variants] == [
        "Brötchen",
        "broetchen",
        "brotchen",
        "bread roll",
    ]


def test_build_search_query_variants_for_gouda_prefers_cheese_fallback() -> None:
    """Gouda should gain one explicit cheese-oriented fallback."""
    variants = build_search_query_variants("Gouda")

    assert [variant.text for variant in variants] == [
        "Gouda",
        "gouda cheese",
    ]


def test_build_search_query_variants_for_apfel_adds_english_fallback() -> None:
    """Apfel should gain apple as a search fallback."""
    variants = build_search_query_variants("Apfel")

    assert [variant.text for variant in variants] == [
        "Apfel",
        "apple",
    ]


def test_build_search_query_variants_for_moehre_adds_carrot_fallback() -> None:
    """Moehre should gain localized and English fallback queries."""
    variants = build_search_query_variants("Möhre")

    assert [variant.text for variant in variants] == [
        "Möhre",
        "moehre",
        "mohre",
        "karotte",
        "carrot",
    ]


def test_build_search_query_variants_for_brand_product_queries_adds_brand_fallback() -> None:
    """Brand-plus-product queries should keep one small brand-only fallback."""
    variants = build_search_query_variants("Kinder Country")

    assert [variant.text for variant in variants] == [
        "Kinder Country",
        "kinder",
    ]


def test_analyze_search_query_detects_brand_and_product_tokens() -> None:
    """Known brand-first phrases should be split into brand and product tokens."""
    analysis = analyze_search_query("Kinder Country")

    assert analysis.brand_tokens == ("kinder",)
    assert analysis.product_tokens == ("country",)
    assert analysis.looks_generic_food is False
    assert analysis.looks_product_like is True


def test_analyze_search_query_detects_generic_german_food_queries() -> None:
    """Generic German food queries should remain generic, not brand-like."""
    analysis = analyze_search_query("Möhre")

    assert analysis.looks_german is True
    assert analysis.looks_generic_food is True
    assert analysis.looks_product_like is False
    assert analysis.brand_tokens == ()
