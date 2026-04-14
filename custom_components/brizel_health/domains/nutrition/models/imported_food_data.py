"""Source-neutral imported food data passed from adapters into Brizel."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterable

from ..common import normalize_optional_text
from ..errors import BrizelImportedFoodValidationError
from .food import (
    validate_hydration_kind,
    validate_hydration_ml_per_100g,
    validate_macro_value,
)


def _normalize_required_text(value: str, field_name: str) -> str:
    """Normalize a required text field."""
    normalized = value.strip()
    if not normalized:
        raise BrizelImportedFoodValidationError(f"{field_name} is required.")
    return normalized


def _normalize_terms(values: Iterable[str] | None) -> tuple[str, ...]:
    """Normalize and deduplicate optional lower-case metadata terms."""
    if values is None:
        return ()

    normalized_values: list[str] = []
    seen: set[str] = set()

    for value in values:
        normalized_value = str(value).strip().lower()
        if not normalized_value or normalized_value in seen:
            continue
        seen.add(normalized_value)
        normalized_values.append(normalized_value)

    return tuple(normalized_values)


def _normalize_market_terms(values: Iterable[str] | None) -> tuple[str, ...]:
    """Normalize and deduplicate optional market terms conservatively."""
    if values is None:
        return ()

    normalized_values: list[str] = []
    seen: set[str] = set()

    for value in values:
        normalized_value = str(value).strip().lower()
        if not normalized_value or normalized_value in seen:
            continue
        seen.add(normalized_value)
        normalized_values.append(normalized_value)

    return tuple(normalized_values)


def _normalize_optional_non_negative_number(
    field_name: str,
    value: float | int | None,
) -> float | None:
    """Validate and normalize an optional numeric field."""
    if value is None:
        return None
    return validate_macro_value(field_name, value)


def _normalize_optional_positive_number(
    field_name: str,
    value: float | int | None,
) -> float | None:
    """Validate and normalize an optional positive numeric field."""
    if value is None:
        return None

    normalized_value = float(value)
    if normalized_value <= 0:
        raise BrizelImportedFoodValidationError(
            f"{field_name} must be greater than 0."
        )

    return normalized_value


def _normalize_optional_logging_unit(value: str | None) -> str | None:
    """Normalize one optional imported portion unit."""
    if value is None:
        return None

    normalized = value.strip().lower()
    if not normalized:
        return None

    allowed_units = {"ml", "piece", "slice", "serving"}
    if normalized not in allowed_units:
        raise BrizelImportedFoodValidationError(
            f"portion_unit must be one of {sorted(allowed_units)}."
        )

    return normalized


def _normalize_imported_hydration(
    hydration_kind: str | None,
    hydration_ml_per_100g: float | int | None,
) -> tuple[str | None, float | None]:
    """Normalize imported hydration signals without forcing full certainty."""
    normalized_kind = validate_hydration_kind(hydration_kind)
    normalized_hydration = validate_hydration_ml_per_100g(hydration_ml_per_100g)

    if normalized_kind is not None and normalized_hydration is None:
        raise BrizelImportedFoodValidationError(
            "hydration_kind requires hydration_ml_per_100g."
        )

    return normalized_kind, normalized_hydration


def _normalize_required_timestamp(value: str) -> str:
    """Validate and normalize a required ISO timestamp."""
    normalized = value.strip()
    if not normalized:
        raise BrizelImportedFoodValidationError("fetched_at is required.")

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as err:
        raise BrizelImportedFoodValidationError(
            "fetched_at must be a valid ISO datetime string."
        ) from err

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC).isoformat()


def _normalize_optional_timestamp(
    value: str | None,
    field_name: str,
) -> str | None:
    """Validate and normalize an optional ISO timestamp."""
    if value is None:
        return None

    normalized = value.strip()
    if not normalized:
        return None

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as err:
        raise BrizelImportedFoodValidationError(
            f"{field_name} must be a valid ISO datetime string."
        ) from err

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC).isoformat()


@dataclass(slots=True)
class ImportedFoodData:
    """Source-neutral imported food payload."""

    source_name: str
    source_id: str
    name: str
    brand: str | None
    barcode: str | None
    kcal_per_100g: float | None
    protein_per_100g: float | None
    carbs_per_100g: float | None
    fat_per_100g: float | None
    ingredients: tuple[str, ...]
    ingredients_known: bool
    allergens: tuple[str, ...]
    allergens_known: bool
    labels: tuple[str, ...]
    labels_known: bool
    hydration_kind: str | None
    hydration_ml_per_100g: float | None
    market_country_codes: tuple[str, ...]
    market_region_codes: tuple[str, ...]
    fetched_at: str
    source_updated_at: str | None = None
    portion_amount: float | None = None
    portion_unit: str | None = None
    portion_grams: float | None = None
    portion_label: str | None = None

    @classmethod
    def create(
        cls,
        source_name: str,
        source_id: str,
        name: str,
        kcal_per_100g: float | int | None,
        protein_per_100g: float | int | None,
        carbs_per_100g: float | int | None,
        fat_per_100g: float | int | None,
        brand: str | None = None,
        barcode: str | None = None,
        ingredients: Iterable[str] | None = None,
        ingredients_known: bool = False,
        allergens: Iterable[str] | None = None,
        allergens_known: bool = False,
        labels: Iterable[str] | None = None,
        labels_known: bool = False,
        hydration_kind: str | None = None,
        hydration_ml_per_100g: float | int | None = None,
        market_country_codes: Iterable[str] | None = None,
        market_region_codes: Iterable[str] | None = None,
        fetched_at: str | None = None,
        source_updated_at: str | None = None,
        portion_amount: float | int | None = None,
        portion_unit: str | None = None,
        portion_grams: float | int | None = None,
        portion_label: str | None = None,
    ) -> "ImportedFoodData":
        """Create validated imported food data."""
        normalized_ingredients = _normalize_terms(ingredients)
        normalized_allergens = _normalize_terms(allergens)
        normalized_labels = _normalize_terms(labels)

        if normalized_ingredients and not ingredients_known:
            raise BrizelImportedFoodValidationError(
                "ingredients_known must be true when ingredients are provided."
            )
        if normalized_allergens and not allergens_known:
            raise BrizelImportedFoodValidationError(
                "allergens_known must be true when allergens are provided."
            )
        if normalized_labels and not labels_known:
            raise BrizelImportedFoodValidationError(
                "labels_known must be true when labels are provided."
            )

        normalized_hydration_kind, normalized_hydration_ml = (
            _normalize_imported_hydration(
                hydration_kind=hydration_kind,
                hydration_ml_per_100g=hydration_ml_per_100g,
            )
        )

        resolved_fetched_at = (
            datetime.now(UTC).isoformat() if fetched_at is None else fetched_at
        )
        normalized_portion_amount = _normalize_optional_positive_number(
            "portion_amount",
            portion_amount,
        )
        normalized_portion_unit = _normalize_optional_logging_unit(portion_unit)
        normalized_portion_grams = _normalize_optional_positive_number(
            "portion_grams",
            portion_grams,
        )
        normalized_portion_label = normalize_optional_text(portion_label)

        has_any_portion_metadata = any(
            value is not None
            for value in (
                normalized_portion_amount,
                normalized_portion_unit,
                normalized_portion_grams,
                normalized_portion_label,
            )
        )
        has_complete_portion_conversion = (
            normalized_portion_amount is not None
            and normalized_portion_unit is not None
            and normalized_portion_grams is not None
        )
        if has_any_portion_metadata and not has_complete_portion_conversion:
            raise BrizelImportedFoodValidationError(
                "portion_amount, portion_unit and portion_grams must be provided together when imported portion metadata is used."
            )

        return cls(
            source_name=_normalize_required_text(source_name, "source_name").lower(),
            source_id=_normalize_required_text(source_id, "source_id"),
            name=_normalize_required_text(name, "name"),
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
            ingredients=normalized_ingredients,
            ingredients_known=bool(ingredients_known),
            allergens=normalized_allergens,
            allergens_known=bool(allergens_known),
            labels=normalized_labels,
            labels_known=bool(labels_known),
            hydration_kind=normalized_hydration_kind,
            hydration_ml_per_100g=normalized_hydration_ml,
            market_country_codes=_normalize_market_terms(market_country_codes),
            market_region_codes=_normalize_market_terms(market_region_codes),
            fetched_at=_normalize_required_timestamp(resolved_fetched_at),
            source_updated_at=_normalize_optional_timestamp(
                source_updated_at,
                "source_updated_at",
            ),
            portion_amount=normalized_portion_amount,
            portion_unit=normalized_portion_unit,
            portion_grams=normalized_portion_grams,
            portion_label=normalized_portion_label,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImportedFoodData":
        """Create imported food data from stored cache data."""
        return cls.create(
            source_name=str(data.get("source_name", "")),
            source_id=str(data.get("source_id", "")),
            name=str(data.get("name", "")),
            brand=data.get("brand"),
            barcode=data.get("barcode"),
            kcal_per_100g=data.get("kcal_per_100g"),
            protein_per_100g=data.get("protein_per_100g"),
            carbs_per_100g=data.get("carbs_per_100g"),
            fat_per_100g=data.get("fat_per_100g"),
            ingredients=data.get("ingredients"),
            ingredients_known=bool(data.get("ingredients_known", False)),
            allergens=data.get("allergens"),
            allergens_known=bool(data.get("allergens_known", False)),
            labels=data.get("labels"),
            labels_known=bool(data.get("labels_known", False)),
            hydration_kind=data.get("hydration_kind"),
            hydration_ml_per_100g=data.get("hydration_ml_per_100g"),
            market_country_codes=data.get("market_country_codes"),
            market_region_codes=data.get("market_region_codes"),
            fetched_at=str(data.get("fetched_at", "")),
            source_updated_at=data.get("source_updated_at"),
            portion_amount=data.get("portion_amount"),
            portion_unit=data.get("portion_unit"),
            portion_grams=data.get("portion_grams"),
            portion_label=data.get("portion_label"),
        )

    def has_complete_nutrition(self) -> bool:
        """Return whether the data can be mapped into the current food catalog."""
        return all(
            value is not None
            for value in (
                self.kcal_per_100g,
                self.protein_per_100g,
                self.carbs_per_100g,
                self.fat_per_100g,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize imported food data for cache storage."""
        data: dict[str, Any] = {
            "source_name": self.source_name,
            "source_id": self.source_id,
            "name": self.name,
            "brand": self.brand,
            "barcode": self.barcode,
            "kcal_per_100g": self.kcal_per_100g,
            "protein_per_100g": self.protein_per_100g,
            "carbs_per_100g": self.carbs_per_100g,
            "fat_per_100g": self.fat_per_100g,
            "ingredients_known": self.ingredients_known,
            "allergens_known": self.allergens_known,
            "labels_known": self.labels_known,
            "market_country_codes": list(self.market_country_codes),
            "market_region_codes": list(self.market_region_codes),
            "fetched_at": self.fetched_at,
        }

        if self.ingredients_known:
            data["ingredients"] = list(self.ingredients)
        if self.allergens_known:
            data["allergens"] = list(self.allergens)
        if self.labels_known:
            data["labels"] = list(self.labels)
        if self.hydration_kind is not None:
            data["hydration_kind"] = self.hydration_kind
        if self.hydration_ml_per_100g is not None:
            data["hydration_ml_per_100g"] = self.hydration_ml_per_100g
        if self.source_updated_at is not None:
            data["source_updated_at"] = self.source_updated_at
        if self.portion_amount is not None:
            data["portion_amount"] = self.portion_amount
        if self.portion_unit is not None:
            data["portion_unit"] = self.portion_unit
        if self.portion_grams is not None:
            data["portion_grams"] = self.portion_grams
        if self.portion_label is not None:
            data["portion_label"] = self.portion_label

        return data
