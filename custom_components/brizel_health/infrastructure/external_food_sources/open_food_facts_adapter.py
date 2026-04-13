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

    async def search_foods(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search OFF products by free-text query."""


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


def _extract_source_id(
    payload: Mapping[str, Any],
    product: Mapping[str, Any],
) -> str:
    """Return the canonical OFF source ID / barcode for one payload."""
    return str(
        product.get("code")
        or payload.get("code")
        or product.get("id")
        or payload.get("id")
        or ""
    ).strip()


def _extract_product_name(product: Mapping[str, Any]) -> str:
    """Return the best available OFF display name without inventing one."""
    for field_name in (
        "product_name",
        "product_name_en",
        "generic_name",
        "generic_name_en",
        "abbreviated_product_name",
    ):
        normalized = str(product.get(field_name) or "").strip()
        if normalized:
            return normalized
    return ""


def _extract_nutriments(product: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return OFF nutriments as one mapping."""
    nutriments = product.get("nutriments", {})
    if isinstance(nutriments, Mapping):
        return nutriments
    return {}


def _extract_optional_nutriment_value(
    nutriments: Mapping[str, Any],
    *field_names: str,
) -> float | None:
    """Resolve one OFF nutriment field conservatively."""
    for field_name in field_names:
        value = nutriments.get(field_name)
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return None


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
            if len(normalized_query) < 3:
                return []

            payloads = await self._client.search_foods(
                normalized_query,
                limit=limit,
            )
            matches: list[ExternalFoodSearchResult] = []
            for payload in payloads:
                mapped = self._try_map_payload_to_search_result(payload)
                if mapped is None:
                    continue
                matches.append(mapped)
                if len(matches) >= limit:
                    break
            return matches

        matches: list[ExternalFoodSearchResult] = []
        for fixture in self._fixtures.values():
            product = _extract_product_payload(fixture)
            haystacks = [
                _extract_product_name(product).lower(),
                str(product.get("brands", "")).lower(),
            ]
            if not any(normalized_query in haystack for haystack in haystacks):
                continue

            mapped = self._try_map_payload_to_search_result(fixture)
            if mapped is None:
                continue
            matches.append(mapped)
            if len(matches) >= limit:
                break

        return matches

    def _map_payload_to_imported_food(
        self,
        payload: Mapping[str, Any],
    ) -> ImportedFoodData:
        """Map one OFF payload into ImportedFoodData."""
        product = _extract_product_payload(payload)
        nutriments = _extract_nutriments(product)
        ingredients, ingredients_known = _parse_ingredients(product)
        source_id = _extract_source_id(payload, product)
        product_name = _extract_product_name(product)

        return ImportedFoodData.create(
            source_name=self.source_name,
            source_id=source_id,
            name=product_name,
            brand=product.get("brands"),
            barcode=source_id or None,
            kcal_per_100g=_extract_optional_nutriment_value(
                nutriments,
                "energy-kcal_100g",
                "energy-kcal",
                "energy-kcal_value",
            ),
            protein_per_100g=_extract_optional_nutriment_value(
                nutriments,
                "proteins_100g",
                "proteins",
                "proteins_value",
            ),
            carbs_per_100g=_extract_optional_nutriment_value(
                nutriments,
                "carbohydrates_100g",
                "carbohydrates",
                "carbohydrates_value",
            ),
            fat_per_100g=_extract_optional_nutriment_value(
                nutriments,
                "fat_100g",
                "fat",
                "fat_value",
            ),
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
                product.get("last_modified_datetime")
                or product.get("last_modified_t")
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

    def _try_map_payload_to_search_result(
        self,
        payload: Mapping[str, Any],
    ) -> ExternalFoodSearchResult | None:
        """Map one OFF search payload, skipping malformed rows conservatively."""
        try:
            return self._map_payload_to_search_result(payload)
        except BrizelImportedFoodValidationError:
            return None
