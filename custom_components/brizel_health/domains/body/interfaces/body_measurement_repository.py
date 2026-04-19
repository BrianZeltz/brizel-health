"""Repository interface for body measurement entries."""

from __future__ import annotations

from typing import Protocol

from ..models.body_measurement_entry import BodyMeasurementEntry


class BodyMeasurementRepository(Protocol):
    """Persistence interface for body measurement entries."""

    async def add(self, measurement: BodyMeasurementEntry) -> BodyMeasurementEntry:
        """Persist one new measurement entry."""

    async def update(self, measurement: BodyMeasurementEntry) -> BodyMeasurementEntry:
        """Persist one updated measurement entry."""

    async def delete(self, measurement_id: str) -> BodyMeasurementEntry:
        """Tombstone one measurement entry."""

    def get_by_id(self, measurement_id: str) -> BodyMeasurementEntry:
        """Load one measurement entry by ID."""

    def get_by_profile_id(
        self,
        profile_id: str,
        *,
        include_deleted: bool = False,
    ) -> list[BodyMeasurementEntry]:
        """Load all measurement entries for one profile."""
