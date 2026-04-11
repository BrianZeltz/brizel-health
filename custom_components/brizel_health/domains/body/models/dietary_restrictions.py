"""Body-owned user dietary restrictions for food compatibility checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

DIETARY_PATTERN_VEGAN = "vegan"
DIETARY_PATTERN_VEGETARIAN = "vegetarian"
ALLOWED_DIETARY_PATTERNS = {
    DIETARY_PATTERN_VEGAN,
    DIETARY_PATTERN_VEGETARIAN,
}


def _normalize_term(value: str) -> str:
    """Normalize a restriction term."""
    return value.strip().lower()


def _normalize_terms(values: Iterable[str] | None) -> tuple[str, ...]:
    """Normalize and deduplicate restriction terms while preserving order."""
    if values is None:
        return ()

    normalized_values: list[str] = []
    seen: set[str] = set()

    for value in values:
        normalized_value = _normalize_term(str(value))
        if not normalized_value or normalized_value in seen:
            continue
        seen.add(normalized_value)
        normalized_values.append(normalized_value)

    return tuple(normalized_values)


def validate_dietary_pattern(dietary_pattern: str | None) -> str | None:
    """Validate and normalize the optional dietary pattern."""
    if dietary_pattern is None:
        return None

    normalized_value = _normalize_term(dietary_pattern)
    if not normalized_value:
        return None

    if normalized_value not in ALLOWED_DIETARY_PATTERNS:
        raise ValueError(
            f"dietary_pattern must be one of {sorted(ALLOWED_DIETARY_PATTERNS)}."
        )

    return normalized_value


@dataclass(slots=True)
class DietaryRestrictions:
    """Body-owned user rules that can be used to evaluate foods."""

    dietary_pattern: str | None
    allergens: tuple[str, ...]
    intolerances: tuple[str, ...]

    @classmethod
    def create(
        cls,
        dietary_pattern: str | None = None,
        allergens: Iterable[str] | None = None,
        intolerances: Iterable[str] | None = None,
    ) -> "DietaryRestrictions":
        """Create a validated dietary restrictions model."""
        return cls(
            dietary_pattern=validate_dietary_pattern(dietary_pattern),
            allergens=_normalize_terms(allergens),
            intolerances=_normalize_terms(intolerances),
        )

    def has_any_restrictions(self) -> bool:
        """Return whether any restrictions are currently defined."""
        return (
            self.dietary_pattern is not None
            or bool(self.allergens)
            or bool(self.intolerances)
        )
