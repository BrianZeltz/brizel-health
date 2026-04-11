"""Repository contract for cached imported foods."""

from __future__ import annotations

from typing import Protocol

from ..models.imported_food_cache_entry import ImportedFoodCacheEntry


class ImportedFoodCacheRepository(Protocol):
    """Persistence contract for imported food cache entries."""

    def get_by_source_ref(
        self,
        source_name: str,
        source_id: str,
    ) -> ImportedFoodCacheEntry | None:
        """Return a cached imported food snapshot for the source reference."""

    async def upsert(
        self,
        cache_entry: ImportedFoodCacheEntry,
    ) -> ImportedFoodCacheEntry:
        """Create or replace a cached imported food snapshot."""
