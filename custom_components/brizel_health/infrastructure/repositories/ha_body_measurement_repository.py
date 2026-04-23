"""Home Assistant backed body measurement repository."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...adapters.homeassistant.bridge_schemas import (
    serialize_body_measurement_peer_record,
)
from ...domains.body.errors import BrizelBodyMeasurementNotFoundError
from ...domains.body.models.body_measurement_entry import BodyMeasurementEntry
from .ha_history_sync_journal_repository import (
    HomeAssistantHistorySyncJournalRepository,
)

if TYPE_CHECKING:
    from ..storage.store_manager import BrizelHealthStoreManager


class HomeAssistantBodyMeasurementRepository:
    """Persist body measurements inside the integration store."""

    def __init__(self, store_manager: "BrizelHealthStoreManager") -> None:
        self._store_manager = store_manager
        self._history_journal = HomeAssistantHistorySyncJournalRepository(
            store_manager
        )

    def _measurements(self) -> dict[str, dict]:
        body = self._store_manager.data.setdefault("body", {})
        return body.setdefault("measurements", {})

    async def add(self, measurement: BodyMeasurementEntry) -> BodyMeasurementEntry:
        self._measurements()[measurement.record_id] = measurement.to_dict()
        await self._store_manager.async_save()
        await self._history_journal.record_snapshot(
            domain="body_measurements",
            profile_id=measurement.profile_id,
            records=(measurement,),
            serialize_record=serialize_body_measurement_peer_record,
        )
        return measurement

    async def update(self, measurement: BodyMeasurementEntry) -> BodyMeasurementEntry:
        self._measurements()[measurement.record_id] = measurement.to_dict()
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
            deleted_measurement.to_dict()
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

        return BodyMeasurementEntry.from_dict(measurement_data)

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
            for measurement in [BodyMeasurementEntry.from_dict(data)]
            if str(data.get("profile_id", "")).strip() == normalized_profile_id
            and (include_deleted or measurement.deleted_at is None)
        ]
