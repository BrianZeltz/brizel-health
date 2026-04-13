"""Tests for query normalization and expansion in external food search."""

from __future__ import annotations

from custom_components.brizel_health.application.nutrition.search_intelligence import (
    build_search_query_variants,
    casefold_search_query,
    expand_german_orthography,
    normalize_search_query,
    strip_diacritics,
)


def test_normalize_search_query_trims_and_collapses_whitespace() -> None:
    """Whitespace-heavy queries should be normalized conservatively."""
    assert normalize_search_query("  apple   juice  ") == "apple juice"


def test_casefold_search_query_is_case_insensitive() -> None:
    """Case handling should be stable for search comparisons."""
    assert casefold_search_query("  ApFeL  ") == "apfel"


def test_expand_german_orthography_handles_umlauts_and_sz() -> None:
    """German orthography expansion should cover the supported phase-1 cases."""
    assert expand_german_orthography("Brötchen groß") == "broetchen gross"


def test_strip_diacritics_preserves_ascii_fallbacks() -> None:
    """Accent stripping should provide a safe ASCII-oriented fallback."""
    assert strip_diacritics("Brötchen Café") == "brotchen cafe"


def test_build_search_query_variants_for_broetchen_is_small_and_high_signal() -> None:
    """Brötchen should expand into a few useful German/English variants."""
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
