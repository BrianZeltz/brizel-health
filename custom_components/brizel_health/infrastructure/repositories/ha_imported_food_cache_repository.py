"""Home Assistant backed repository for imported food cache entries."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...domains.nutrition.models.imported_food_cache_entry import (
    ImportedFoodCacheEntry,
)

if TYPE_CHECKING:
    from ..storage.store_manager import BrizelHealthStoreManager


class HomeAssistantImportedFoodCacheRepository:
    """Persist imported food cache data inside the integration store."""

    def __init__(self, store_manager: "BrizelHealthStoreManager") -> None:
        """Initialize the repository."""
        self._store_manager = store_manager

    def _cache(self) -> dict[str, dict[str, dict]]:
        """Return the mutable imported-food cache bucket."""
        nutrition = self._store_manager.data.setdefault("nutrition", {})
        return nutrition.setdefault("imported_food_cache", {})

    def get_by_source_ref(
        self,
        source_name: str,
        source_id: str,
    ) -> ImportedFoodCacheEntry | None:
        """Return a cached entry for the given source reference."""
        normalized_source_name = source_name.strip().lower()
        normalized_source_id = source_id.strip()
        if not normalized_source_name or not normalized_source_id:
            return None

        source_bucket = self._cache().get(normalized_source_name, {})
        entry = source_bucket.get(normalized_source_id)
        if entry is None:
            return None

        return ImportedFoodCacheEntry.from_dict(entry)

    async def upsert(
        self,
        cache_entry: ImportedFoodCacheEntry,
    ) -> ImportedFoodCacheEntry:
        """Create or replace a cached imported-food snapshot."""
        source_bucket = self._cache().setdefault(cache_entry.source_name, {})
        source_bucket[cache_entry.source_id] = cache_entry.to_dict()
        await self._store_manager.async_save()
        return cache_entry
