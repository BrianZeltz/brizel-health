"""Home Assistant backed body measurement repository."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...adapters.homeassistant.bridge_schemas import (
    serialize_body_measurement_peer_record,
)
from ...domains.body.errors import BrizelBodyMeasurementNotFoundError
from ...domains.body.models.body_measurement_entry import BodyMeasurementEntry
from ...domains.security.models.key_hierarchy import (
    EncryptedPayloadEnvelope,
    PROTECTED_DATA_CLASS_HISTORY_PAYLOADS,
)
from ..security.ha_local_crypto_service import HomeAssistantLocalCryptoService
from .ha_history_sync_journal_repository import (
    HomeAssistantHistorySyncJournalRepository,
)
from .ha_key_hierarchy_repository import HomeAssistantKeyHierarchyRepository

if TYPE_CHECKING:
    from ..storage.store_manager import BrizelHealthStoreManager


class HomeAssistantBodyMeasurementRepository:
    """Persist body measurements inside the integration store."""

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

    def _measurements(self) -> dict[str, dict]:
        body = self._store_manager.data.setdefault("body", {})
        return body.setdefault("measurements", {})

    async def add(self, measurement: BodyMeasurementEntry) -> BodyMeasurementEntry:
        self._measurements()[measurement.record_id] = await self._serialize_measurement(
            measurement
        )
        await self._store_manager.async_save()
        await self._history_journal.record_snapshot(
            domain="body_measurements",
            profile_id=measurement.profile_id,
            records=(measurement,),
            serialize_record=serialize_body_measurement_peer_record,
        )
        return measurement

    async def update(self, measurement: BodyMeasurementEntry) -> BodyMeasurementEntry:
        self._measurements()[measurement.record_id] = await self._serialize_measurement(
            measurement
        )
        await self._store_manager.async_save()
        await self._history_journal.record_snapshot(
            domain="body_measurements",
            profile_id=measurement.profile_id,
            records=(measurement,),
            serialize_record=serialize_body_measurement_peer_record,
        )
        return measurement

    async def delete(self, measurement_id: str) -> BodyMeasurementEntry:
        deleted_measurement = self.get_by_id(measurement_id)
        deleted_measurement.mark_deleted()
        self._measurements()[deleted_measurement.record_id] = (
            await self._serialize_measurement(deleted_measurement)
        )
        await self._store_manager.async_save()
        await self._history_journal.record_snapshot(
            domain="body_measurements",
            profile_id=deleted_measurement.profile_id,
            records=(deleted_measurement,),
            serialize_record=serialize_body_measurement_peer_record,
        )
        return deleted_measurement

    def get_by_id(self, measurement_id: str) -> BodyMeasurementEntry:
        normalized_id = str(measurement_id).strip()
        measurement_data = self._measurements().get(normalized_id)
        if measurement_data is None:
            measurement_data = next(
                (
                    data
                    for data in self._measurements().values()
                    if str(
                        data.get("record_id") or data.get("measurement_id") or ""
                    ).strip()
                    == normalized_id
                ),
                None,
            )
        if measurement_data is None:
            raise BrizelBodyMeasurementNotFoundError(
                f"No body measurement found for measurement_id '{measurement_id}'."
            )

        return self._deserialize_measurement(measurement_data)

    def get_by_profile_id(
        self,
        profile_id: str,
        *,
        include_deleted: bool = False,
    ) -> list[BodyMeasurementEntry]:
        normalized_profile_id = str(profile_id).strip()
        return [
            measurement
            for data in self._measurements().values()
            for measurement in [self._deserialize_measurement(data)]
            if str(data.get("profile_id", "")).strip() == normalized_profile_id
            and (include_deleted or measurement.deleted_at is None)
        ]

    async def migrate_legacy_plaintext_measurements(self) -> int:
        """Re-write legacy plaintext measurements into encrypted payload form."""
        measurements = self._measurements()
        migrated = 0
        updated_measurements = dict(measurements)

        for key, data in measurements.items():
            if not isinstance(data, dict):
                continue
            if isinstance(data.get("encrypted_payload"), dict):
                continue
            measurement = self._deserialize_measurement(data)
            serialized = await self._serialize_measurement(measurement)
            updated_measurements[measurement.record_id] = serialized
            if key != measurement.record_id:
                updated_measurements.pop(key, None)
            migrated += 1

        if migrated:
            self._store_manager.data.setdefault("body", {})[
                "measurements"
            ] = updated_measurements
            await self._store_manager.async_save()
        return migrated

    async def _serialize_measurement(
        self,
        measurement: BodyMeasurementEntry,
    ) -> dict[str, object]:
        envelope = await self._crypto_service.encrypt_profile_payload(
            profile_id=measurement.profile_id,
            data_class_id=PROTECTED_DATA_CLASS_HISTORY_PAYLOADS,
            payload={
                "measurement_type": measurement.measurement_type,
                "canonical_value": measurement.canonical_value,
                "measured_at": measurement.measured_at,
                "note": measurement.note,
            },
            aad_context=_body_measurement_payload_aad_context(
                record_id=measurement.record_id,
                profile_id=measurement.profile_id,
                revision=measurement.revision,
                updated_at=measurement.updated_at,
            ),
        )
        return {
            "record_id": measurement.record_id,
            "record_type": measurement.record_type,
            "profile_id": measurement.profile_id,
            "source_type": measurement.source_type,
            "source_detail": measurement.source_detail,
            "origin_node_id": measurement.origin_node_id,
            "created_at": measurement.created_at,
            "updated_at": measurement.updated_at,
            "updated_by_node_id": measurement.updated_by_node_id,
            "revision": measurement.revision,
            "payload_version": measurement.payload_version,
            "deleted_at": measurement.deleted_at,
            "encrypted_payload": envelope.to_dict(),
        }

    def _deserialize_measurement(
        self,
        data: dict[str, object],
    ) -> BodyMeasurementEntry:
        encrypted_payload = data.get("encrypted_payload")
        if not isinstance(encrypted_payload, dict):
            return BodyMeasurementEntry.from_dict(data)
        payload = self._crypto_service.decrypt_profile_payload_sync(
            profile_id=str(data.get("profile_id") or "").strip(),
            envelope=EncryptedPayloadEnvelope.from_dict(encrypted_payload),
            expected_aad_context=_body_measurement_payload_aad_context(
                record_id=str(data.get("record_id") or "").strip(),
                profile_id=str(data.get("profile_id") or "").strip(),
                revision=int(data.get("revision") or 0),
                updated_at=str(data.get("updated_at") or ""),
            ),
        )
        merged = dict(data)
        merged.update(payload)
        return BodyMeasurementEntry.from_dict(merged)


def _body_measurement_payload_aad_context(
    *,
    record_id: str,
    profile_id: str,
    revision: int,
    updated_at: str,
) -> dict[str, object]:
    return {
        "data_class_id": PROTECTED_DATA_CLASS_HISTORY_PAYLOADS,
        "storage": "body.measurements",
        "record_type": "body_measurement",
        "record_id": record_id,
        "profile_id": profile_id,
        "revision": revision,
        "updated_at": updated_at,
    }
