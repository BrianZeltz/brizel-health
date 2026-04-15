"""Home Assistant backed body measurement repository."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...domains.body.errors import BrizelBodyMeasurementNotFoundError
from ...domains.body.models.body_measurement_entry import BodyMeasurementEntry

if TYPE_CHECKING:
    from ..storage.store_manager import BrizelHealthStoreManager


class HomeAssistantBodyMeasurementRepository:
    """Persist body measurements inside the integration store."""

    def __init__(self, store_manager: "BrizelHealthStoreManager") -> None:
        self._store_manager = store_manager

    def _measurements(self) -> dict[str, dict]:
        body = self._store_manager.data.setdefault("body", {})
        return body.setdefault("measurements", {})

    async def add(self, measurement: BodyMeasurementEntry) -> BodyMeasurementEntry:
        self._measurements()[measurement.measurement_id] = measurement.to_dict()
        await self._store_manager.async_save()
        return measurement

    async def update(self, measurement: BodyMeasurementEntry) -> BodyMeasurementEntry:
        self._measurements()[measurement.measurement_id] = measurement.to_dict()
        await self._store_manager.async_save()
        return measurement

    async def delete(self, measurement_id: str) -> BodyMeasurementEntry:
        deleted_measurement = self.get_by_id(measurement_id)
        del self._measurements()[measurement_id]
        await self._store_manager.async_save()
        return deleted_measurement

    def get_by_id(self, measurement_id: str) -> BodyMeasurementEntry:
        measurement_data = self._measurements().get(str(measurement_id).strip())
        if measurement_data is None:
            raise BrizelBodyMeasurementNotFoundError(
                f"No body measurement found for measurement_id '{measurement_id}'."
            )

        return BodyMeasurementEntry.from_dict(measurement_data)

    def get_by_profile_id(self, profile_id: str) -> list[BodyMeasurementEntry]:
        normalized_profile_id = str(profile_id).strip()
        return [
            BodyMeasurementEntry.from_dict(data)
            for data in self._measurements().values()
            if str(data.get("profile_id", "")).strip() == normalized_profile_id
        ]
