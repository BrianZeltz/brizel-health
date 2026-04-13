"""Minimal live HTTP client for Open Food Facts search and product lookup."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ...domains.nutrition.errors import (
    BrizelImportedFoodSourceError,
    BrizelImportedFoodValidationError,
)

DEFAULT_TIMEOUT_SECONDS = 10
DEFAULT_OPEN_FOOD_FACTS_BASE_URL = "https://world.openfoodfacts.net/api/v2"
DEFAULT_OPEN_FOOD_FACTS_SEARCH_BASE_URL = "https://world.openfoodfacts.org"
DEFAULT_PRODUCT_FIELDS = (
    "code",
    "product_name",
    "product_name_en",
    "generic_name",
    "generic_name_en",
    "abbreviated_product_name",
    "brands",
    "ingredients_text",
    "ingredients",
    "allergens_tags",
    "labels_tags",
    "nutriments",
    "last_modified_t",
    "countries_tags",
)


def _perform_json_request(url: str, timeout_seconds: int) -> Mapping[str, Any]:
    """Run one blocking JSON request and return the parsed object."""
    request = Request(url, headers={"Accept": "application/json"})

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = response.read().decode("utf-8")
    except HTTPError as err:
        if err.code == 404:
            return {}
        raise BrizelImportedFoodSourceError(
            f"Open Food Facts request failed with HTTP {err.code}."
        ) from err
    except URLError as err:
        raise BrizelImportedFoodSourceError(
            "The Open Food Facts source is currently unavailable."
        ) from err

    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError as err:
        raise BrizelImportedFoodSourceError(
            "The Open Food Facts source returned invalid JSON."
        ) from err

    if not isinstance(decoded, Mapping):
        raise BrizelImportedFoodSourceError(
            "The Open Food Facts source returned an unexpected response shape."
        )

    return decoded


class OpenFoodFactsHttpClient:
    """Small OFF client for live search and barcode/product lookups."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_OPEN_FOOD_FACTS_BASE_URL,
        search_base_url: str = DEFAULT_OPEN_FOOD_FACTS_SEARCH_BASE_URL,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        product_fields: tuple[str, ...] = DEFAULT_PRODUCT_FIELDS,
    ) -> None:
        """Initialize the Open Food Facts client."""
        self._base_url = base_url.rstrip("/")
        self._search_base_url = search_base_url.rstrip("/")
        self._timeout_seconds = int(timeout_seconds)
        self._product_fields = tuple(product_fields)

    async def fetch_product_by_barcode(
        self,
        barcode: str,
    ) -> dict[str, Any] | None:
        """Fetch one product payload by barcode."""
        normalized_barcode = barcode.strip()
        if not normalized_barcode:
            raise BrizelImportedFoodValidationError("A source_id is required.")

        query = urlencode({"fields": ",".join(self._product_fields)})
        url = f"{self._base_url}/product/{normalized_barcode}?{query}"
        payload = await asyncio.to_thread(
            _perform_json_request,
            url,
            self._timeout_seconds,
        )
        status = payload.get("status")
        if status == 0:
            return None
        return dict(payload)

    async def search_foods(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search OFF products by free-text query via the documented V1 search API."""
        normalized_query = query.strip()
        if not normalized_query:
            raise BrizelImportedFoodValidationError("A search query is required.")
        if limit <= 0:
            raise BrizelImportedFoodValidationError("limit must be greater than 0.")

        query_string = urlencode(
            {
                "search_terms": normalized_query,
                "search_simple": 1,
                "action": "process",
                "json": 1,
                "page_size": int(limit),
                "fields": ",".join(self._product_fields),
            }
        )
        url = f"{self._search_base_url}/cgi/search.pl?{query_string}"
        payload = await asyncio.to_thread(
            _perform_json_request,
            url,
            self._timeout_seconds,
        )
        products = payload.get("products", [])
        if not isinstance(products, list):
            raise BrizelImportedFoodSourceError(
                "The Open Food Facts source returned an invalid search result."
            )

        return [dict(product) for product in products if isinstance(product, Mapping)]
