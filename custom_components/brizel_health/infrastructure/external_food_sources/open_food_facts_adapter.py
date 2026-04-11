"""Open Food Facts adapter."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Protocol

from ...domains.nutrition.errors import BrizelImportedFoodValidationError
from ...domains.nutrition.models.external_food_search_result import (
    ExternalFoodSearchResult,
)
from ...domains.nutrition.models.imported_food_data import ImportedFoodData
from .open_food_facts_http_client import OpenFoodFactsHttpClient

SOURCE_NAME = "open_food_facts"

DEFAULT_OPEN_FOOD_FACTS_FIXTURES: dict[str, dict[str, Any]] = {
    "4311596470738": {
        "product": {
            "id": "4311596470738",
            "product_name": "Still Water",
            "brands": "Brizel",
            "ingredients_text": "Water",
            "ingredients": [
                {"text": "Water"},
            ],
            "allergens_tags": [],
            "labels_tags": ["en:vegan", "en:vegetarian"],
            "nutriments": {
                "energy-kcal_100g": 0,
                "proteins_100g": 0,
                "carbohydrates_100g": 0,
                "fat_100g": 0,
            },
            "last_modified_t": 1712317200,
            "countries_tags": ["en:germany"],
        }
    }
}


class OpenFoodFactsClientProtocol(Protocol):
    """Protocol for live Open Food Facts clients."""

    async def fetch_product_by_barcode(
        self,
        barcode: str,
    ) -> dict[str, Any] | None:
        """Fetch one OFF product by barcode."""


def _normalize_source_tags(
    values: list[str] | None,
    *,
    remove_language_prefix: bool,
) -> list[str]:
    """Normalize OFF tags conservatively for the internal import model."""
    if values is None:
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        raw_value = str(value).strip().lower()
        if remove_language_prefix and ":" in raw_value:
            _, raw_value = raw_value.split(":", 1)
        if not raw_value or raw_value in seen:
            continue
        seen.add(raw_value)
        normalized.append(raw_value)

    return normalized


def _extract_product_payload(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return the OFF product payload regardless of wrapper shape."""
    product = payload.get("product")
    if isinstance(product, Mapping):
        return product
    return payload


def _parse_ingredients(product: Mapping[str, Any]) -> tuple[list[str], bool]:
    """Parse OFF ingredients with ingredients[] before ingredients_text."""
    raw_ingredients = product.get("ingredients")
    if isinstance(raw_ingredients, list):
        parsed_ingredients: list[str] = []
        for item in raw_ingredients:
            if not isinstance(item, Mapping):
                continue
            text = str(item.get("text", "")).strip()
            if text:
                parsed_ingredients.append(text)
        return parsed_ingredients, True

    if "ingredients_text" in product:
        ingredients_text = str(product.get("ingredients_text") or "").strip()
        if not ingredients_text:
            return [], True
        return [
            ingredient.strip()
            for ingredient in ingredients_text.split(",")
            if ingredient.strip()
        ], True

    return [], False


def _parse_source_updated_at(value: Any) -> str | None:
    """Convert OFF last_modified_t seconds into ISO datetime."""
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), UTC).isoformat()

    normalized = str(value).strip()
    if not normalized:
        return None

    if normalized.isdigit():
        return datetime.fromtimestamp(float(normalized), UTC).isoformat()

    return normalized


class OpenFoodFactsAdapter:
    """Map Open Food Facts payloads into internal search and import models."""

    source_name = SOURCE_NAME

    def __init__(
        self,
        fixtures: dict[str, dict[str, Any]] | None = None,
        *,
        client: OpenFoodFactsClientProtocol | None = None,
        fetched_at: str = "2026-04-05T10:00:00+00:00",
    ) -> None:
        """Initialize the adapter with fixtures or a live client."""
        self._fixtures = fixtures
        self._client = client or OpenFoodFactsHttpClient()
        self._fetched_at = fetched_at

    async def fetch_food_by_id(self, source_id: str) -> ImportedFoodData | None:
        """Return a single source food by barcode/source ID."""
        normalized_source_id = source_id.strip()
        if not normalized_source_id:
            raise BrizelImportedFoodValidationError("A source_id is required.")

        if self._fixtures is not None:
            fixture = self._fixtures.get(normalized_source_id)
            if fixture is None:
                return None
            return self._map_payload_to_imported_food(fixture)

        payload = await self._client.fetch_product_by_barcode(normalized_source_id)
        if payload is None:
            return None
        return self._map_payload_to_imported_food(payload)

    async def search_foods(
        self,
        query: str,
        limit: int = 10,
    ) -> list[ExternalFoodSearchResult]:
        """Search OFF foods and return source-neutral search results."""
        normalized_query = query.strip().lower()
        if not normalized_query or limit <= 0:
            return []

        if self._fixtures is None:
            raise BrizelImportedFoodValidationError(
                "Open Food Facts search is not supported yet in the live adapter."
            )

        matches: list[ExternalFoodSearchResult] = []
        for fixture in self._fixtures.values():
            product = _extract_product_payload(fixture)
            haystacks = [
                str(product.get("product_name", "")).lower(),
                str(product.get("brands", "")).lower(),
            ]
            if not any(normalized_query in haystack for haystack in haystacks):
                continue

            matches.append(self._map_payload_to_search_result(fixture))
            if len(matches) >= limit:
                break

        return matches

    def _map_payload_to_imported_food(
        self,
        payload: Mapping[str, Any],
    ) -> ImportedFoodData:
        """Map one OFF payload into ImportedFoodData."""
        product = _extract_product_payload(payload)
        nutriments = product.get("nutriments", {})
        if not isinstance(nutriments, Mapping):
            nutriments = {}
        ingredients, ingredients_known = _parse_ingredients(product)
        source_id = str(product.get("id") or payload.get("code") or "").strip()

        return ImportedFoodData.create(
            source_name=self.source_name,
            source_id=source_id,
            name=str(product.get("product_name", "")),
            brand=product.get("brands"),
            barcode=None,
            kcal_per_100g=nutriments.get("energy-kcal_100g"),
            protein_per_100g=nutriments.get("proteins_100g"),
            carbs_per_100g=nutriments.get("carbohydrates_100g"),
            fat_per_100g=nutriments.get("fat_100g"),
            ingredients=ingredients,
            ingredients_known=ingredients_known,
            allergens=_normalize_source_tags(
                product.get("allergens_tags"),
                remove_language_prefix=True,
            ),
            allergens_known="allergens_tags" in product,
            labels=_normalize_source_tags(
                product.get("labels_tags"),
                remove_language_prefix=True,
            ),
            labels_known="labels_tags" in product,
            hydration_kind=None,
            hydration_ml_per_100g=None,
            market_country_codes=_normalize_source_tags(
                product.get("countries_tags"),
                remove_language_prefix=False,
            ),
            market_region_codes=None,
            fetched_at=self._fetched_at,
            source_updated_at=_parse_source_updated_at(
                product.get("last_modified_t")
            ),
        )

    def _map_payload_to_search_result(
        self,
        payload: Mapping[str, Any],
    ) -> ExternalFoodSearchResult:
        """Map one OFF payload into a search result."""
        imported_food = self._map_payload_to_imported_food(payload)
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
        )
