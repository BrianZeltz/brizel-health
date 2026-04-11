"""Minimal live HTTP client for Open Food Facts product lookup."""

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
DEFAULT_PRODUCT_FIELDS = (
    "code",
    "product_name",
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
    """Small OFF client for barcode/product lookups."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_OPEN_FOOD_FACTS_BASE_URL,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        product_fields: tuple[str, ...] = DEFAULT_PRODUCT_FIELDS,
    ) -> None:
        """Initialize the Open Food Facts client."""
        self._base_url = base_url.rstrip("/")
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
