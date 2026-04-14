"""Source-neutral search result for external food lookups."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from typing import Any

from ..common import normalize_optional_text
from ..errors import BrizelImportedFoodValidationError
from .food import normalize_food_name, validate_macro_value


def _normalize_required_text(value: str, field_name: str) -> str:
    """Normalize one required text field."""
    normalized = value.strip()
    if not normalized:
        raise BrizelImportedFoodValidationError(f"{field_name} is required.")
    return normalized


def _normalize_optional_non_negative_number(
    field_name: str,
    value: float | int | None,
) -> float | None:
    """Validate one optional numeric field."""
    if value is None:
        return None
    return validate_macro_value(field_name, value)


def _normalize_market_terms(values: Iterable[str] | None) -> tuple[str, ...]:
    """Normalize optional market tags for ranking/context use."""
    if values is None:
        return ()

    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        candidate = normalize_optional_text(value)
        if candidate is None:
            continue
        lowered = candidate.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(lowered)
    return tuple(normalized)


@dataclass(slots=True)
class ExternalFoodSearchResult:
    """Source-neutral search result used before explicit import."""

    source_name: str
    source_id: str
    name: str
    brand: str | None
    barcode: str | None
    kcal_per_100g: float | None
    protein_per_100g: float | None
    carbs_per_100g: float | None
    fat_per_100g: float | None
    hydration_ml_per_100g: float | None
    market_country_codes: tuple[str, ...]
    market_region_codes: tuple[str, ...]
    language_codes: tuple[str, ...]
    store_tags: tuple[str, ...]
    category_tags: tuple[str, ...]

    @classmethod
    def create(
        cls,
        *,
        source_name: str,
        source_id: str,
        name: str,
        brand: str | None = None,
        barcode: str | None = None,
        kcal_per_100g: float | int | None = None,
        protein_per_100g: float | int | None = None,
        carbs_per_100g: float | int | None = None,
        fat_per_100g: float | int | None = None,
        hydration_ml_per_100g: float | int | None = None,
        market_country_codes: Iterable[str] | None = None,
        market_region_codes: Iterable[str] | None = None,
        language_codes: Iterable[str] | None = None,
        store_tags: Iterable[str] | None = None,
        category_tags: Iterable[str] | None = None,
    ) -> "ExternalFoodSearchResult":
        """Create a validated search result."""
        return cls(
            source_name=_normalize_required_text(source_name, "source_name").lower(),
            source_id=_normalize_required_text(source_id, "source_id"),
            name=normalize_food_name(_normalize_required_text(name, "name")),
            brand=normalize_optional_text(brand),
            barcode=normalize_optional_text(barcode),
            kcal_per_100g=_normalize_optional_non_negative_number(
                "kcal_per_100g",
                kcal_per_100g,
            ),
            protein_per_100g=_normalize_optional_non_negative_number(
                "protein_per_100g",
                protein_per_100g,
            ),
            carbs_per_100g=_normalize_optional_non_negative_number(
                "carbs_per_100g",
                carbs_per_100g,
            ),
            fat_per_100g=_normalize_optional_non_negative_number(
                "fat_per_100g",
                fat_per_100g,
            ),
            hydration_ml_per_100g=_normalize_optional_non_negative_number(
                "hydration_ml_per_100g",
                hydration_ml_per_100g,
            ),
            market_country_codes=_normalize_market_terms(market_country_codes),
            market_region_codes=_normalize_market_terms(market_region_codes),
            language_codes=_normalize_market_terms(language_codes),
            store_tags=_normalize_market_terms(store_tags),
            category_tags=_normalize_market_terms(category_tags),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the search result for service responses."""
        return {
            "source_name": self.source_name,
            "source_id": self.source_id,
            "name": self.name,
            "brand": self.brand,
            "barcode": self.barcode,
            "kcal_per_100g": self.kcal_per_100g,
            "protein_per_100g": self.protein_per_100g,
            "carbs_per_100g": self.carbs_per_100g,
            "fat_per_100g": self.fat_per_100g,
            "hydration_ml_per_100g": self.hydration_ml_per_100g,
            "market_country_codes": list(self.market_country_codes),
            "market_region_codes": list(self.market_region_codes),
            "language_codes": list(self.language_codes),
            "store_tags": list(self.store_tags),
            "category_tags": list(self.category_tags),
        }
