"""Conservative parsing helpers for source-provided portion metadata."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

_GRAMS_RE = re.compile(r"(?P<grams>\d+(?:[.,]\d+)?)\s*g\b", re.IGNORECASE)
_ML_RE = re.compile(r"(?P<ml>\d+(?:[.,]\d+)?)\s*ml\b", re.IGNORECASE)
_LEADING_AMOUNT_RE = re.compile(
    r"^\s*(?P<amount>\d+(?:[.,]\d+)?)\s*(?P<label>[a-zA-ZäöüÄÖÜß.\-]+)",
    re.IGNORECASE,
)

_UNIT_ALIASES = {
    "piece": {
        "piece",
        "pieces",
        "pc",
        "pcs",
        "stuck",
        "stück",
        "stueck",
        "stk",
    },
    "slice": {"slice", "slices", "scheibe", "scheiben"},
    "serving": {"serving", "servings", "portion", "portionen"},
}


@dataclass(frozen=True, slots=True)
class PortionMetadata:
    """One safe user-facing portion option with a gram conversion."""

    unit: str
    amount: float
    grams: float
    label: str | None = None


def _normalize_search_text(value: str) -> str:
    normalized = value.strip().casefold()
    normalized = unicodedata.normalize("NFKD", normalized)
    return "".join(
        character for character in normalized if not unicodedata.combining(character)
    )


def _parse_number(value: str | float | int | None) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None


def _normalize_portion_unit(label: str | None) -> str | None:
    normalized = _normalize_search_text(label or "")
    if not normalized:
        return None

    for unit, aliases in _UNIT_ALIASES.items():
        if normalized in aliases:
            return unit

    return None


def build_generic_serving(
    grams: float | int | None,
    *,
    label: str | None = None,
) -> PortionMetadata | None:
    """Build one generic serving option when only a gram weight is known."""
    normalized_grams = _parse_number(grams)
    if normalized_grams is None or normalized_grams <= 0:
        return None

    resolved_label = (label or "").strip() or f"1 serving ({normalized_grams:g} g)"
    return PortionMetadata(
        unit="serving",
        amount=1.0,
        grams=normalized_grams,
        label=resolved_label,
    )


def parse_portion_metadata(
    raw_label: str | None,
    *,
    grams_hint: float | int | None = None,
) -> PortionMetadata | None:
    """Parse one source-provided portion label conservatively.

    Supported examples:
    - ``1 slice (30 g)``
    - ``2 pieces (40 g)``
    - ``30 g`` -> generic serving
    - ``250 ml (255 g)``
    """
    normalized_label = (raw_label or "").strip()
    if not normalized_label:
        return build_generic_serving(grams_hint)

    normalized_grams_hint = _parse_number(grams_hint)
    grams_match = _GRAMS_RE.search(normalized_label)
    ml_match = _ML_RE.search(normalized_label)

    grams_value = (
        _parse_number(grams_match.group("grams"))
        if grams_match is not None
        else normalized_grams_hint
    )

    leading_match = _LEADING_AMOUNT_RE.match(normalized_label)
    if leading_match is not None:
        unit = _normalize_portion_unit(leading_match.group("label"))
        amount = _parse_number(leading_match.group("amount"))
        if (
            unit in {"piece", "slice", "serving"}
            and amount is not None
            and amount > 0
            and grams_value is not None
            and grams_value > 0
        ):
            return PortionMetadata(
                unit=unit,
                amount=amount,
                grams=grams_value,
                label=normalized_label,
            )

    if (
        ml_match is not None
        and grams_value is not None
        and grams_value > 0
    ):
        ml_amount = _parse_number(ml_match.group("ml"))
        if ml_amount is not None and ml_amount > 0:
            return PortionMetadata(
                unit="ml",
                amount=ml_amount,
                grams=grams_value,
                label=normalized_label,
            )

    return build_generic_serving(grams_value, label=normalized_label)
