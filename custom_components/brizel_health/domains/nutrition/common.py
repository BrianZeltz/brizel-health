"""Small shared helpers for the nutrition domain."""

from __future__ import annotations


def normalize_optional_text(value: str | None) -> str | None:
    """Normalize optional text values."""
    if value is None:
        return None

    normalized = value.strip()
    return normalized or None
