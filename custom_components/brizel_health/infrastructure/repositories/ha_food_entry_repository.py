"""Home Assistant backed food entry repository."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...adapters.homeassistant.bridge_schemas import serialize_food_log_peer_record
from ...domains.nutrition.errors import BrizelFoodEntryNotFoundError
from ...domains.nutrition.models.food_entry import FoodEntry
from ...domains.security.models.key_hierarchy import (
    EncryptedPayloadEnvelope,
    PROTECTED_DATA_CLASS_HISTORY_PAYLOADS,
)
from .ha_history_sync_journal_repository import (
    HomeAssistantHistorySyncJournalRepository,
)
from .ha_key_hierarchy_repository import HomeAssistantKeyHierarchyRepository
from ..security.ha_local_crypto_service import HomeAssistantLocalCryptoService

if TYPE_CHECKING:
    from ..storage.store_manager import BrizelHealthStoreManager


class HomeAssistantFoodEntryRepository:
    """Persist food entries inside the integration store."""

    def __init__(self, store_manager: "BrizelHealthStoreManager") -> None:
        """Initialize the repository."""
        self._store_manager = store_manager
        self._history_journal = HomeAssistantHistorySyncJournalRepository(
            store_manager
        )
        self._key_hierarchy_repository = HomeAssistantKeyHierarchyRepository(
            store_manager
        )
        self._crypto_service = HomeAssistantLocalCryptoService(
            self._key_hierarchy_repository
        )

    def _food_entries(self) -> dict[str, dict]:
        """Return the mutable food entry bucket."""
        nutrition = self._store_manager.data.setdefault("nutrition", {})
        return nutrition.setdefault("food_entries", {})

    async def add(self, food_entry: FoodEntry) -> FoodEntry:
        """Persist a new food entry."""
        self._food_entries()[food_entry.record_id] = await self._serialize_food_entry(
            food_entry
        )
        await self._store_manager.async_save()
        await self._history_journal.record_snapshot(
            domain="food_logs",
            profile_id=food_entry.profile_id,
            records=(food_entry,),
            serialize_record=serialize_food_log_peer_record,
        )
        return food_entry

    async def update(self, food_entry: FoodEntry) -> FoodEntry:
        """Persist an updated food entry."""
        self.get_food_entry_by_id(food_entry.record_id)
        self._food_entries()[food_entry.record_id] = await self._serialize_food_entry(
            food_entry
        )
        await self._store_manager.async_save()
        await self._history_journal.record_snapshot(
            domain="food_logs",
            profile_id=food_entry.profile_id,
            records=(food_entry,),
            serialize_record=serialize_food_log_peer_record,
        )
        return food_entry

    async def delete(self, food_entry_id: str) -> FoodEntry:
        """Tombstone a food entry and return the updated entity."""
        deleted_food_entry = self.get_food_entry_by_id(food_entry_id)
        deleted_food_entry.mark_deleted()
        self._food_entries()[deleted_food_entry.record_id] = (
            await self._serialize_food_entry(deleted_food_entry)
        )
        await self._store_manager.async_save()
        await self._history_journal.record_snapshot(
            domain="food_logs",
            profile_id=deleted_food_entry.profile_id,
            records=(deleted_food_entry,),
            serialize_record=serialize_food_log_peer_record,
        )
        return deleted_food_entry

    def get_food_entry_by_id(self, food_entry_id: str) -> FoodEntry:
        """Load a food entry by ID."""
        normalized_id = str(food_entry_id).strip()
        food_entry_data = self._food_entries().get(normalized_id)
        if food_entry_data is None:
            food_entry_data = next(
                (
                    data
                    for data in self._food_entries().values()
                    if str(data.get("record_id") or data.get("food_entry_id") or "").strip()
                    == normalized_id
                ),
                None,
            )
        if food_entry_data is None:
            raise BrizelFoodEntryNotFoundError(
                f"No food entry found for food_entry_id '{food_entry_id}'."
            )

        return self._deserialize_food_entry(food_entry_data)

    def get_all_food_entries(
        self,
        *,
        include_deleted: bool = False,
    ) -> list[FoodEntry]:
        """Load all food entries."""
        entries = [
            self._deserialize_food_entry(data)
            for data in self._food_entries().values()
        ]
        if include_deleted:
            return entries
        return [entry for entry in entries if not entry.is_deleted]

    async def migrate_legacy_plaintext_food_entries(self) -> int:
        """Re-write legacy plaintext food entries into encrypted payload form."""
        food_entries = self._food_entries()
        migrated = 0
        updated_entries = dict(food_entries)

        for key, data in food_entries.items():
            if not isinstance(data, dict):
                continue
            if isinstance(data.get("encrypted_payload"), dict):
                continue
            food_entry = self._deserialize_food_entry(data)
            serialized = await self._serialize_food_entry(food_entry)
            updated_entries[food_entry.record_id] = serialized
            if key != food_entry.record_id:
                updated_entries.pop(key, None)
            migrated += 1

        if migrated:
            self._store_manager.data.setdefault("nutrition", {})[
                "food_entries"
            ] = updated_entries
            await self._store_manager.async_save()
        return migrated

    async def _serialize_food_entry(
        self,
        food_entry: FoodEntry,
    ) -> dict[str, object]:
        envelope = await self._crypto_service.encrypt_profile_payload(
            profile_id=food_entry.profile_id,
            data_class_id=PROTECTED_DATA_CLASS_HISTORY_PAYLOADS,
            payload={
                "food_id": food_entry.food_id,
                "food_name": food_entry.food_name,
                "food_brand": food_entry.food_brand,
                "amount_grams": food_entry.amount_grams,
                "meal_type": food_entry.meal_type,
                "note": food_entry.note,
                "consumed_at": food_entry.consumed_at,
                "kcal": food_entry.kcal,
                "protein": food_entry.protein,
                "carbs": food_entry.carbs,
                "fat": food_entry.fat,
            },
            aad_context=_food_log_payload_aad_context(
                record_id=food_entry.record_id,
                profile_id=food_entry.profile_id,
                revision=food_entry.revision,
                updated_at=food_entry.updated_at,
            ),
        )
        return {
            "record_id": food_entry.record_id,
            "record_type": food_entry.record_type,
            "profile_id": food_entry.profile_id,
            "source_type": food_entry.source_type,
            "source_detail": food_entry.source_detail,
            "origin_node_id": food_entry.origin_node_id,
            "created_at": food_entry.created_at,
            "updated_at": food_entry.updated_at,
            "updated_by_node_id": food_entry.updated_by_node_id,
            "revision": food_entry.revision,
            "payload_version": food_entry.payload_version,
            "deleted_at": food_entry.deleted_at,
            "encrypted_payload": envelope.to_dict(),
        }

    def _deserialize_food_entry(
        self,
        data: dict[str, object],
    ) -> FoodEntry:
        encrypted_payload = data.get("encrypted_payload")
        if not isinstance(encrypted_payload, dict):
            return FoodEntry.from_dict(data)
        payload = self._crypto_service.decrypt_profile_payload_sync(
            profile_id=str(data.get("profile_id") or "").strip(),
            envelope=EncryptedPayloadEnvelope.from_dict(encrypted_payload),
            expected_aad_context=_food_log_payload_aad_context(
                record_id=str(data.get("record_id") or "").strip(),
                profile_id=str(data.get("profile_id") or "").strip(),
                revision=int(data.get("revision") or 0),
                updated_at=str(data.get("updated_at") or ""),
            ),
        )
        merged = dict(data)
        merged.update(payload)
        return FoodEntry.from_dict(merged)


def _food_log_payload_aad_context(
    *,
    record_id: str,
    profile_id: str,
    revision: int,
    updated_at: str,
) -> dict[str, object]:
    return {
        "data_class_id": PROTECTED_DATA_CLASS_HISTORY_PAYLOADS,
        "storage": "nutrition.food_entries",
        "record_type": "food_log",
        "record_id": record_id,
        "profile_id": profile_id,
        "revision": revision,
        "updated_at": updated_at,
    }
