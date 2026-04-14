"""Application queries for the Food Logging UI flow."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re

from ...domains.nutrition.errors import BrizelImportedFoodValidationError
from ...domains.nutrition.models.external_food_search_result import (
    ExternalFoodSearchResult,
)
from ...domains.nutrition.models.imported_food_data import ImportedFoodData
from .food_import_use_cases import fetch_imported_food
from .food_search_queries import (
    AggregatedFoodSearchResult,
    FoodSourceSearchResult,
    SEARCH_STATUS_EMPTY,
    SEARCH_STATUS_FAILURE,
    SEARCH_STATUS_SUCCESS,
)
from .source_registry import FoodSourceRegistry

_GRAM_BASIS_AMOUNT = 100.0
_GRAM_BASIS_UNIT = "g"
_BARCODE_RE = re.compile(r"^\d{8,14}$")


@dataclass(frozen=True, slots=True)
class LoggingUnitOption:
    """One user-selectable logging unit with a safe gram conversion."""

    unit: str
    label: str
    default_amount: float
    grams_per_unit: float
    description: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Serialize one logging option for UI responses."""
        return asdict(self)


def _get_enabled_source(registry: FoodSourceRegistry, source_name: str):
    """Return one enabled source definition or raise a clear validation error."""
    source = registry.get_source(source_name)
    if source is None or not source.enabled:
        raise BrizelImportedFoodValidationError(
            "Source is not registered or is disabled."
        )
    return source


async def get_external_food_detail_from_registry(
    registry: FoodSourceRegistry,
    *,
    source_name: str,
    source_id: str,
) -> ImportedFoodData:
    """Fetch one external food detail payload from an enabled source."""
    source = _get_enabled_source(registry, source_name)
    return await fetch_imported_food(source.adapter, source_id)


async def lookup_external_food_by_barcode_from_registry(
    registry: FoodSourceRegistry,
    *,
    barcode: str,
    requested_source_names: list[str] | None = None,
) -> AggregatedFoodSearchResult:
    """Lookup one food by barcode across barcode-capable enabled sources."""
    normalized_barcode = _normalize_barcode(barcode)
    requested_names = {
        name.strip().lower()
        for name in (requested_source_names or [])
        if str(name).strip()
    }

    source_results: list[FoodSourceSearchResult] = []
    matching_results: list[ExternalFoodSearchResult] = []
    selected_sources = registry.get_enabled_sources()
    if requested_names:
        selected_sources = [
            source for source in selected_sources if source.name in requested_names
        ]

    if not selected_sources:
        return AggregatedFoodSearchResult(
            status=SEARCH_STATUS_FAILURE,
            results=[],
            source_results=[],
            error="No enabled food sources are available.",
        )

    for source in selected_sources:
        if not bool(getattr(source.adapter, "supports_barcode_lookup", False)):
            source_results.append(
                FoodSourceSearchResult(
                    source_name=source.name,
                    status=SEARCH_STATUS_EMPTY,
                    results=[],
                    error=None,
                )
            )
            continue

        try:
            imported_food = await source.adapter.fetch_food_by_id(normalized_barcode)
        except Exception as err:
            source_results.append(
                FoodSourceSearchResult(
                    source_name=source.name,
                    status=SEARCH_STATUS_FAILURE,
                    results=[],
                    error=str(err),
                )
            )
            continue

        if imported_food is None:
            source_results.append(
                FoodSourceSearchResult(
                    source_name=source.name,
                    status=SEARCH_STATUS_EMPTY,
                    results=[],
                    error=None,
                )
            )
            continue

        result = _imported_food_to_search_result(imported_food)
        matching_results.append(result)
        source_results.append(
            FoodSourceSearchResult(
                source_name=source.name,
                status=SEARCH_STATUS_SUCCESS,
                results=[result],
                error=None,
            )
        )

    if matching_results:
        return AggregatedFoodSearchResult(
            status=SEARCH_STATUS_SUCCESS,
            results=matching_results,
            source_results=source_results,
            error=None,
        )

    had_empty = any(
        source_result.status == SEARCH_STATUS_EMPTY for source_result in source_results
    )
    if had_empty:
        return AggregatedFoodSearchResult(
            status=SEARCH_STATUS_EMPTY,
            results=[],
            source_results=source_results,
            error=None,
        )

    return AggregatedFoodSearchResult(
        status=SEARCH_STATUS_FAILURE,
        results=[],
        source_results=source_results,
        error="No barcode-capable food sources are available.",
    )


def get_supported_logging_units(
    imported_food: ImportedFoodData,
) -> tuple[str, ...]:
    """Return the currently safe logging units for one imported food."""
    return tuple(option.unit for option in get_logging_unit_options(imported_food))


def get_default_logging_unit(
    imported_food: ImportedFoodData,
) -> str:
    """Return the default unit for one imported food detail payload."""
    return get_logging_unit_options(imported_food)[0].unit


def get_default_logging_amount(
    imported_food: ImportedFoodData,
) -> float:
    """Return the most useful initial amount for one imported food detail payload."""
    return get_logging_unit_options(imported_food)[0].default_amount


def get_logging_unit_option(
    imported_food: ImportedFoodData,
    unit: str | None,
) -> LoggingUnitOption | None:
    """Return one supported logging option for the requested unit."""
    normalized_unit = (unit or "").strip().lower()
    if not normalized_unit:
        normalized_unit = get_default_logging_unit(imported_food)

    for option in get_logging_unit_options(imported_food):
        if option.unit == normalized_unit:
            return option

    return None


def get_logging_unit_options(
    imported_food: ImportedFoodData,
) -> tuple[LoggingUnitOption, ...]:
    """Return all currently safe logging unit options for one imported food.

    The current Brizel catalog still stores nutrition canonically as gram-based
    entries, so we only expose units that can be converted into grams without
    guessing.
    """
    options: list[LoggingUnitOption] = []
    seen_units: set[str] = set()

    if (
        imported_food.portion_unit is not None
        and imported_food.portion_amount is not None
        and imported_food.portion_grams is not None
        and imported_food.portion_amount > 0
        and imported_food.portion_grams > 0
    ):
        grams_per_unit = imported_food.portion_grams / imported_food.portion_amount
        if grams_per_unit > 0:
            unit = imported_food.portion_unit
            default_amount = (
                imported_food.portion_amount if unit == "ml" else 1.0
            )
            description = imported_food.portion_label or _build_unit_description(
                amount=imported_food.portion_amount,
                unit=imported_food.portion_unit,
                grams=imported_food.portion_grams,
            )
            options.append(
                LoggingUnitOption(
                    unit=unit,
                    label=unit,
                    default_amount=default_amount,
                    grams_per_unit=grams_per_unit,
                    description=description,
                )
            )
            seen_units.add(unit)

    if _GRAM_BASIS_UNIT not in seen_units:
        options.append(
            LoggingUnitOption(
                unit=_GRAM_BASIS_UNIT,
                label=_GRAM_BASIS_UNIT,
                default_amount=_GRAM_BASIS_AMOUNT,
                grams_per_unit=1.0,
                description=None,
            )
        )

    return tuple(options)


def _normalize_barcode(barcode: str) -> str:
    normalized = re.sub(r"[\s-]+", "", str(barcode or "").strip())
    if not _BARCODE_RE.fullmatch(normalized):
        raise BrizelImportedFoodValidationError(
            "Please enter a valid barcode with 8 to 14 digits."
        )
    return normalized


def _imported_food_to_search_result(
    imported_food: ImportedFoodData,
) -> ExternalFoodSearchResult:
    """Map one imported-food payload into the shared pre-import search shape."""
    return ExternalFoodSearchResult.create(
        source_name=imported_food.source_name,
        source_id=imported_food.source_id,
        name=imported_food.name,
        brand=imported_food.brand,
        barcode=imported_food.barcode,
        kcal_per_100g=imported_food.kcal_per_100g,
        protein_per_100g=imported_food.protein_per_100g,
        carbs_per_100g=imported_food.carbs_per_100g,
        fat_per_100g=imported_food.fat_per_100g,
        hydration_ml_per_100g=imported_food.hydration_ml_per_100g,
        market_country_codes=imported_food.market_country_codes,
        market_region_codes=imported_food.market_region_codes,
    )


def _build_unit_description(
    *,
    amount: float,
    unit: str,
    grams: float,
) -> str:
    formatted_amount = _format_amount(amount)
    formatted_grams = _format_amount(grams)
    return f"{formatted_amount} {unit} = {formatted_grams} g"


def _format_amount(value: float) -> str:
    rounded = round(float(value), 4)
    if abs(rounded - round(rounded)) < 0.0001:
        return str(int(round(rounded)))
    if abs((rounded * 10) - round(rounded * 10)) < 0.0001:
        return f"{rounded:.1f}"
    return f"{rounded:.2f}"
