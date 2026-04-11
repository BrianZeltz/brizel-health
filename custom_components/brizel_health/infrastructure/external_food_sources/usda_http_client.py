"""Minimal live HTTP client for USDA FoodData Central."""

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
DEFAULT_USDA_BASE_URL = "https://api.nal.usda.gov/fdc/v1"


def _normalize_api_key(api_key: str) -> str:
    """Validate one API key string."""
    normalized = api_key.strip()
    if not normalized:
        raise BrizelImportedFoodValidationError("A USDA API key is required.")
    return normalized


def _normalize_mapping(data: Any) -> Mapping[str, Any]:
    """Ensure one decoded JSON response is an object."""
    if not isinstance(data, Mapping):
        raise BrizelImportedFoodSourceError(
            "The external food source returned an unexpected response shape."
        )
    return data


def _perform_json_request(url: str, timeout_seconds: int) -> Mapping[str, Any]:
    """Run one blocking JSON request and return the parsed object."""
    request = Request(url, headers={"Accept": "application/json"})

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = response.read().decode("utf-8")
    except HTTPError as err:
        if err.code == 404:
            return {}
        if err.code in (401, 403):
            raise BrizelImportedFoodValidationError(
                "The USDA API key is missing, invalid, or unauthorized."
            ) from err
        raise BrizelImportedFoodSourceError(
            f"USDA request failed with HTTP {err.code}."
        ) from err
    except URLError as err:
        raise BrizelImportedFoodSourceError(
            "The USDA source is currently unavailable."
        ) from err

    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError as err:
        raise BrizelImportedFoodSourceError(
            "The USDA source returned invalid JSON."
        ) from err

    return _normalize_mapping(decoded)


class UsdaHttpClient:
    """Small USDA client for search and detail lookups."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_USDA_BASE_URL,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        """Initialize the USDA client."""
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = int(timeout_seconds)

    async def fetch_food_by_id(
        self,
        source_id: str,
        *,
        api_key: str,
    ) -> dict[str, Any] | None:
        """Fetch one USDA food detail payload."""
        normalized_api_key = _normalize_api_key(api_key)
        normalized_source_id = source_id.strip()
        if not normalized_source_id:
            raise BrizelImportedFoodValidationError("A source_id is required.")

        query = urlencode({"api_key": normalized_api_key})
        url = f"{self._base_url}/food/{normalized_source_id}?{query}"
        payload = await asyncio.to_thread(
            _perform_json_request,
            url,
            self._timeout_seconds,
        )
        return None if not payload else dict(payload)

    async def search_foods(
        self,
        query: str,
        *,
        api_key: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search USDA foods by text query."""
        normalized_api_key = _normalize_api_key(api_key)
        normalized_query = query.strip()
        if not normalized_query:
            raise BrizelImportedFoodValidationError("A search query is required.")
        if limit <= 0:
            raise BrizelImportedFoodValidationError("limit must be greater than 0.")

        query_string = urlencode(
            {
                "api_key": normalized_api_key,
                "query": normalized_query,
                "pageSize": int(limit),
            }
        )
        url = f"{self._base_url}/foods/search?{query_string}"
        payload = await asyncio.to_thread(
            _perform_json_request,
            url,
            self._timeout_seconds,
        )
        foods = payload.get("foods", [])
        if not isinstance(foods, list):
            raise BrizelImportedFoodSourceError(
                "The USDA source returned an invalid search result."
            )

        return [food for food in foods if isinstance(food, Mapping)]
