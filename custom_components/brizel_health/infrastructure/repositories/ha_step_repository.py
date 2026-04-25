"""Home Assistant backed Fit step repository."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from ...adapters.homeassistant.bridge_schemas import serialize_step_peer_record
from ...domains.fit.models.step_entry import StepEntry
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


class HomeAssistantStepRepository:
    """Persist Fit step entries inside the integration store."""

    def __init__(self, store_manager: "BrizelHealthStoreManager") -> None:
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

    @staticmethod
    def _normalize_required_text(value: object, field_name: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError(f"{field_name} is required.")
        return normalized

    def _steps_by_profile(self) -> dict[str, dict[str, dict]]:
        fit = self._store_manager.data.setdefault("fit", {})
        return fit.setdefault("steps_by_profile", {})

    def _profile_steps(self, profile_id: str) -> dict[str, dict]:
        normalized_profile_id = self._normalize_required_text(profile_id, "profile_id")
        return self._steps_by_profile().setdefault(normalized_profile_id, {})

    def _import_state_by_profile(self) -> dict[str, dict[str, object]]:
        fit = self._store_manager.data.setdefault("fit", {})
        return fit.setdefault("steps_import_state_by_profile", {})

    def _profile_import_state(self, profile_id: str) -> dict[str, object]:
        normalized_profile_id = self._normalize_required_text(profile_id, "profile_id")
        return self._import_state_by_profile().setdefault(normalized_profile_id, {})

    def _source_priority_by_profile(self) -> dict[str, list[str]]:
        fit = self._store_manager.data.setdefault("fit", {})
        return fit.setdefault("step_source_priority_by_profile", {})

    @staticmethod
    def _normalize_datetime(value: datetime | str | None) -> datetime | None:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str) and value.strip():
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        else:
            return None

        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed

    def get_by_external_record_id(
        self,
        profile_id: str,
        external_record_id: str,
    ) -> StepEntry | None:
        """Load one step entry by external record ID."""
        data = self._profile_steps(profile_id).get(str(external_record_id).strip())
        if data is None:
            return None
        return self._deserialize_step_entry(data)

    def get_by_message_id(self, message_id: str) -> StepEntry | None:
        """Load one step entry by app bridge message ID."""
        normalized_message_id = str(message_id).strip()
        for steps in self._steps_by_profile().values():
            for data in steps.values():
                if str(data.get("message_id", "")).strip() == normalized_message_id:
                    return StepEntry.from_dict(data)
        return None

    def exists_external_record_id(
        self,
        profile_id: str,
        external_record_id: str,
    ) -> bool:
        """Return whether an external record ID already exists."""
        return str(external_record_id).strip() in self._profile_steps(profile_id)

    def exists_message_id(self, message_id: str) -> bool:
        """Return whether a bridge message ID already exists."""
        return self.get_by_message_id(message_id) is not None

    def list_step_entries(self, profile_id: str) -> tuple[StepEntry, ...]:
        """Load stored step entries for one profile."""
        return tuple(
            self._deserialize_step_entry(data)
            for data in self._profile_steps(profile_id).values()
        )

    async def migrate_legacy_plaintext_step_entries(self) -> int:
        """Re-write legacy plaintext step entries into encrypted payload form."""
        migrated = 0
        steps_by_profile = self._steps_by_profile()

        for profile_id, profile_steps in steps_by_profile.items():
            if not isinstance(profile_steps, dict):
                continue
            updated_steps = dict(profile_steps)
            profile_changed = False
            for key, data in profile_steps.items():
                if not isinstance(data, dict):
                    continue
                if isinstance(data.get("encrypted_payload"), dict):
                    continue
                entry = self._deserialize_step_entry(data)
                updated_steps[key] = await self._serialize_step_entry(entry)
                profile_changed = True
                migrated += 1
            if profile_changed:
                steps_by_profile[profile_id] = updated_steps

        if migrated:
            await self._store_manager.async_save()
        return migrated

    def get_last_successful_steps_sync(self, profile_id: str) -> datetime | None:
        """Return one profile's latest successfully processed step import time."""
        state = self._profile_import_state(profile_id)
        last_sync = self._normalize_datetime(state.get("last_successful_sync"))
        if last_sync is not None:
            return last_sync

        entries = self.list_step_entries(profile_id)
        if not entries:
            return None
        return max(entry.received_at for entry in entries)

    def get_last_steps_import_status(self, profile_id: str) -> str | None:
        """Return one profile's latest successfully processed step import status."""
        status = str(self._profile_import_state(profile_id).get("last_status") or "")
        return status.strip() or None

    def get_step_source_priority(self, profile_id: str) -> tuple[str, ...]:
        """Return profile-specific source priority override hints."""
        normalized_profile_id = self._normalize_required_text(profile_id, "profile_id")
        priority = self._source_priority_by_profile().get(normalized_profile_id, [])
        if not isinstance(priority, list):
            return ()
        return tuple(str(item).strip() for item in priority if str(item).strip())

    async def set_step_source_priority(
        self,
        profile_id: str,
        source_priority: tuple[str, ...],
    ) -> tuple[str, ...]:
        """Persist profile-specific source priority override hints."""
        normalized_profile_id = self._normalize_required_text(profile_id, "profile_id")
        normalized_priority = tuple(
            str(item).strip() for item in source_priority if str(item).strip()
        )
        self._source_priority_by_profile()[normalized_profile_id] = list(
            normalized_priority
        )
        await self._store_manager.async_save()
        return normalized_priority

    async def save_step_entry(self, step_entry: StepEntry) -> StepEntry:
        """Persist or replace one step entry by external record ID."""
        self._profile_steps(step_entry.profile_id)[step_entry.external_record_id] = (
            await self._serialize_step_entry(step_entry)
        )
        await self._store_manager.async_save()
        await self._history_journal.record_snapshot(
            domain="steps",
            profile_id=step_entry.profile_id,
            records=(step_entry,),
            serialize_record=serialize_step_peer_record,
        )
        return step_entry

    async def _serialize_step_entry(self, step_entry: StepEntry) -> dict[str, object]:
        envelope = await self._crypto_service.encrypt_profile_payload(
            profile_id=step_entry.profile_id,
            data_class_id=PROTECTED_DATA_CLASS_HISTORY_PAYLOADS,
            payload={
                "device_id": step_entry.device_id,
                "source": step_entry.source,
                "start": step_entry.start.isoformat(),
                "end": step_entry.end.isoformat(),
                "steps": step_entry.steps,
                "received_at": step_entry.received_at.isoformat(),
                "timezone": step_entry.timezone,
                "origin": step_entry.origin,
                "read_mode": step_entry.read_mode,
                "data_origin": step_entry.data_origin,
            },
            aad_context=_step_payload_aad_context(
                record_id=step_entry.record_id or "",
                profile_id=step_entry.profile_id,
                revision=step_entry.revision,
                updated_at=step_entry.updated_at.isoformat(),
            ),
        )
        return {
            "external_record_id": step_entry.external_record_id,
            "profile_id": step_entry.profile_id,
            "message_id": step_entry.message_id,
            "record_id": step_entry.record_id,
            "record_type": step_entry.record_type,
            "origin_node_id": step_entry.origin_node_id,
            "source_type": step_entry.source_type,
            "source_detail": step_entry.source_detail,
            "created_at": step_entry.created_at.isoformat(),
            "updated_at": step_entry.updated_at.isoformat(),
            "updated_by_node_id": step_entry.updated_by_node_id,
            "revision": step_entry.revision,
            "payload_version": step_entry.payload_version,
            "deleted_at": (
                None if step_entry.deleted_at is None else step_entry.deleted_at.isoformat()
            ),
            "encrypted_payload": envelope.to_dict(),
        }

    def _deserialize_step_entry(self, data: dict[str, object]) -> StepEntry:
        encrypted_payload = data.get("encrypted_payload")
        if not isinstance(encrypted_payload, dict):
            return StepEntry.from_dict(data)
        payload = self._crypto_service.decrypt_profile_payload_sync(
            profile_id=str(data.get("profile_id") or "").strip(),
            envelope=EncryptedPayloadEnvelope.from_dict(encrypted_payload),
            expected_aad_context=_step_payload_aad_context(
                record_id=str(data.get("record_id") or "").strip(),
                profile_id=str(data.get("profile_id") or "").strip(),
                revision=int(data.get("revision") or 0),
                updated_at=str(data.get("updated_at") or ""),
            ),
        )
        merged = dict(data)
        merged.update(payload)
        return StepEntry.from_dict(merged)

    async def record_step_import_success(
        self,
        *,
        profile_id: str,
        processed_at: datetime,
        status: str,
    ) -> None:
        """Persist metadata for one profile's successfully processed step import."""
        normalized_processed_at = self._normalize_datetime(processed_at)
        if normalized_processed_at is None:
            normalized_processed_at = datetime.now(UTC)

        state = self._profile_import_state(profile_id)
        state["last_successful_sync"] = normalized_processed_at.isoformat()
        state["last_status"] = str(status or "success").strip() or "success"
        await self._store_manager.async_save()


def _step_payload_aad_context(
    *,
    record_id: str,
    profile_id: str,
    revision: int,
    updated_at: str,
) -> dict[str, object]:
    return {
        "data_class_id": PROTECTED_DATA_CLASS_HISTORY_PAYLOADS,
        "storage": "fit.steps",
        "record_type": "steps",
        "record_id": record_id,
        "profile_id": profile_id,
        "revision": revision,
        "updated_at": updated_at,
    }
