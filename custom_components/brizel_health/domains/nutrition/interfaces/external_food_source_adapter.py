"""Contract for source-specific external food adapters."""

from __future__ import annotations

from typing import Protocol

from ..models.external_food_search_result import ExternalFoodSearchResult
from ..models.imported_food_data import ImportedFoodData


class ExternalFoodSourceAdapter(Protocol):
    """Adapter contract for fetching and searching imported foods."""

    source_name: str

    async def fetch_food_by_id(self, source_id: str) -> ImportedFoodData | None:
        """Return a source-neutral imported food payload by source ID."""

    async def search_foods(
        self,
        query: str,
        limit: int = 10,
    ) -> list[ExternalFoodSearchResult]:
        """Search source foods and return source-neutral search results."""
