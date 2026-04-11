"""USDA FoodData Central adapter."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Protocol

from ...domains.nutrition.errors import BrizelImportedFoodValidationError
from ...domains.nutrition.models.external_food_search_result import (
    ExternalFoodSearchResult,
)
from ...domains.nutrition.models.imported_food_data import ImportedFoodData
from .usda_http_client import UsdaHttpClient

SOURCE_NAME = "usda"

DEFAULT_USDA_FIXTURES: dict[str, dict[str, Any]] = {
    "123456": {
        "fdcId": 123456,
        "description": "Apple, raw",
        "foodNutrients": [
            {"nutrientName": "Energy", "unitName": "KCAL", "value": 52},
            {"nutrientName": "Water", "unitName": "G", "value": 85.6},
        ],
        "publicationDate": "2020-01-01",
    }
}


class UsdaClientProtocol(Protocol):
    """Protocol for live USDA client implementations."""

    async def fetch_food_by_id(
        self,
        source_id: str,
        *,
        api_key: str,
    ) -> dict[str, Any] | None:
        """Fetch one USDA detail payload."""

    async def search_foods(
        self,
        query: str,
        *,
        api_key: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search USDA foods and return raw payloads."""


def _normalize_api_key(api_key: str | None) -> str:
    """Validate one optional USDA API key."""
    normalized = (api_key or "").strip()
    if not normalized:
        raise BrizelImportedFoodValidationError("A USDA API key is required.")
    return normalized


def _extract_usda_nutrient_value(
    food_nutrients: list[dict[str, Any]],
    nutrient_names: tuple[str, ...],
    unit_name: str,
) -> float | None:
    """Extract a nutrient value from a USDA style nutrient list."""
    normalized_names = {name.lower() for name in nutrient_names}
    normalized_unit_name = unit_name.lower()

    for nutrient in food_nutrients:
        nutrient_metadata = nutrient.get("nutrient")
        if isinstance(nutrient_metadata, Mapping):
            nutrient_name = str(nutrient_metadata.get("name", "")).strip().lower()
            nutrient_unit_name = str(
                nutrient_metadata.get("unitName", "")
            ).strip().lower()
        else:
            nutrient_name = str(
                nutrient.get("nutrientName") or nutrient.get("name") or ""
            ).strip().lower()
            nutrient_unit_name = str(nutrient.get("unitName", "")).strip().lower()

        if (
            nutrient_name in normalized_names
            and nutrient_unit_name == normalized_unit_name
        ):
            value = nutrient.get("amount")
            if value is None:
                value = nutrient.get("value")
            if value is None:
                return None
            return float(value)

    return None


def _normalize_timestamp(value: Any) -> str | None:
    """Normalize a timestamp/date value into ISO format when possible."""
    if value is None:
        return None

    normalized = str(value).strip()
    if not normalized:
        return None

    # USDA can return plain dates or date-like strings without a timezone.
    normalized_for_iso = normalized.replace("Z", "+00:00")

    try:
        parsed = datetime.fromisoformat(normalized_for_iso)
    except ValueError:
        parsed = None

    if parsed is None:
        for date_format in ("%m/%d/%Y", "%Y/%m/%d", "%m-%d-%Y"):
            try:
                parsed = datetime.strptime(normalized, date_format)
            except ValueError:
                continue
            break

    if parsed is None:
        raise BrizelImportedFoodValidationError(
            "USDA publicationDate could not be normalized into an ISO datetime."
        )

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC).isoformat()


def _extract_food_nutrients(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return USDA food nutrients as a typed list."""
    food_nutrients = payload.get("foodNutrients", [])
    if not isinstance(food_nutrients, list):
        return []

    return [nutrient for nutrient in food_nutrients if isinstance(nutrient, dict)]


def _extract_usda_nutrient_snapshot(
    payload: Mapping[str, Any],
) -> dict[str, float | None]:
    """Extract the Brizel-relevant USDA nutrient subset from one payload."""
    food_nutrients = _extract_food_nutrients(payload)
    return {
        "kcal_per_100g": _extract_usda_nutrient_value(
            food_nutrients,
            ("Energy", "Energy (kcal)"),
            "KCAL",
        ),
        "protein_per_100g": _extract_usda_nutrient_value(
            food_nutrients,
            ("Protein",),
            "G",
        ),
        "carbs_per_100g": _extract_usda_nutrient_value(
            food_nutrients,
            ("Carbohydrate, by difference",),
            "G",
        ),
        "fat_per_100g": _extract_usda_nutrient_value(
            food_nutrients,
            ("Total lipid (fat)",),
            "G",
        ),
        "hydration_ml_per_100g": _extract_usda_nutrient_value(
            food_nutrients,
            ("Water",),
            "G",
        ),
    }


class UsdaAdapter:
    """Map USDA source payloads into internal search and import models."""

    source_name = SOURCE_NAME

    def __init__(
        self,
        fixtures: dict[str, dict[str, Any]] | None = None,
        *,
        client: UsdaClientProtocol | None = None,
        api_key: str | None = None,
        fetched_at: str = "2026-04-05T10:00:00+00:00",
    ) -> None:
        """Initialize the adapter with fixtures or a live client."""
        self._fixtures = fixtures
        self._client = client or UsdaHttpClient()
        self._api_key = api_key
        self._fetched_at = fetched_at

    async def fetch_food_by_id(self, source_id: str) -> ImportedFoodData | None:
        """Return a single source food by source ID."""
        normalized_source_id = source_id.strip()
        if self._fixtures is not None:
            fixture = self._fixtures.get(normalized_source_id)
            if fixture is None:
                return None
            return self._map_payload_to_imported_food(fixture)

        payload = await self._client.fetch_food_by_id(
            normalized_source_id,
            api_key=_normalize_api_key(self._api_key),
        )
        if payload is None:
            return None
        return self._map_payload_to_imported_food(payload)

    async def search_foods(
        self,
        query: str,
        limit: int = 10,
    ) -> list[ExternalFoodSearchResult]:
        """Search USDA foods and return source-neutral search results."""
        normalized_query = query.strip()
        if not normalized_query or limit <= 0:
            return []

        if self._fixtures is not None:
            matches: list[ExternalFoodSearchResult] = []
            for fixture in self._fixtures.values():
                haystack = str(fixture.get("description", "")).lower()
                if normalized_query.lower() not in haystack:
                    continue

                matches.append(self._map_payload_to_search_result(fixture))
                if len(matches) >= limit:
                    break
            return matches

        payloads = await self._client.search_foods(
            normalized_query,
            api_key=_normalize_api_key(self._api_key),
            limit=limit,
        )
        return [self._map_payload_to_search_result(payload) for payload in payloads]

    def _map_payload_to_imported_food(
        self,
        payload: Mapping[str, Any],
    ) -> ImportedFoodData:
        """Map a USDA detail payload into ImportedFoodData."""
        nutrient_snapshot = _extract_usda_nutrient_snapshot(payload)
        required_macro_fields = (
            "kcal_per_100g",
            "protein_per_100g",
            "carbs_per_100g",
            "fat_per_100g",
        )
        missing_macro_fields = [
            field_name
            for field_name in required_macro_fields
            if nutrient_snapshot[field_name] is None
        ]
        if missing_macro_fields:
            raise BrizelImportedFoodValidationError(
                "USDA detail response did not provide complete kcal, protein, carbs and fat values per 100g."
            )

        return ImportedFoodData.create(
            source_name=self.source_name,
            source_id=str(payload.get("fdcId", "")),
            name=str(payload.get("description", "")),
            brand=payload.get("brandOwner"),
            barcode=payload.get("gtinUpc"),
            kcal_per_100g=nutrient_snapshot["kcal_per_100g"],
            protein_per_100g=nutrient_snapshot["protein_per_100g"],
            carbs_per_100g=nutrient_snapshot["carbs_per_100g"],
            fat_per_100g=nutrient_snapshot["fat_per_100g"],
            ingredients=None,
            ingredients_known=False,
            allergens=None,
            allergens_known=False,
            labels=None,
            labels_known=False,
            hydration_kind=None,
            hydration_ml_per_100g=nutrient_snapshot["hydration_ml_per_100g"],
            market_country_codes=["us"],
            market_region_codes=["na"],
            fetched_at=self._fetched_at,
            source_updated_at=_normalize_timestamp(payload.get("publicationDate")),
        )

    def _map_payload_to_search_result(
        self,
        payload: Mapping[str, Any],
    ) -> ExternalFoodSearchResult:
        """Map one USDA payload into a search result."""
        nutrient_snapshot = _extract_usda_nutrient_snapshot(payload)
        return ExternalFoodSearchResult.create(
            source_name=self.source_name,
            source_id=str(payload.get("fdcId", "")),
            name=str(payload.get("description", "")),
            brand=payload.get("brandOwner"),
            barcode=payload.get("gtinUpc"),
            kcal_per_100g=nutrient_snapshot["kcal_per_100g"],
            protein_per_100g=nutrient_snapshot["protein_per_100g"],
            carbs_per_100g=nutrient_snapshot["carbs_per_100g"],
            fat_per_100g=nutrient_snapshot["fat_per_100g"],
            hydration_ml_per_100g=nutrient_snapshot["hydration_ml_per_100g"],
        )
