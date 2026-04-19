"""Write use cases for body measurements."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from ...core.interfaces.user_repository import UserRepository
from ...domains.body.interfaces.body_measurement_repository import (
    BodyMeasurementRepository,
)
from ...domains.body.errors import BrizelBodyMeasurementNotFoundError
from ...domains.body.models.body_measurement_entry import BodyMeasurementEntry
from ...domains.body.services.body_measurement_units import convert_input_to_canonical
from ..users.user_use_cases import get_user

BODY_MEASUREMENT_UNSET = object()
BODY_MEASUREMENT_PEER_SYNC_TYPE = "weight"


@dataclass(frozen=True)
class BodyMeasurementPeerSyncResult:
    """Outcome of one body measurement peer upsert."""

    measurement: BodyMeasurementEntry
    imported: int
    updated: int
    ignored: int

    def to_result_dict(self) -> dict[str, int]:
        """Serialize counters for bridge responses."""
        return {
            "imported": self.imported,
            "updated": self.updated,
            "ignored": self.ignored,
        }


async def add_body_measurement(
    repository: BodyMeasurementRepository,
    user_repository: UserRepository,
    *,
    profile_id: str,
    measurement_type: str,
    value: float | int,
    unit: str | None = None,
    measured_at: str | None = None,
    source: str | None = None,
    note: str | None = None,
) -> BodyMeasurementEntry:
    """Create and persist one body measurement entry."""
    user = get_user(user_repository, profile_id)
    canonical_value = convert_input_to_canonical(
        measurement_type=measurement_type,
        value=value,
        unit=unit,
    )
    entry = BodyMeasurementEntry.create(
        profile_id=user.user_id,
        measurement_type=measurement_type,
        canonical_value=canonical_value,
        measured_at=measured_at,
        source=source,
        note=note,
    )
    return await repository.add(entry)


async def update_body_measurement(
    repository: BodyMeasurementRepository,
    user_repository: UserRepository,
    *,
    measurement_id: str,
    measurement_type: str | None = None,
    value: float | int | None = None,
    unit: str | None = None,
    measured_at: str | None | object = BODY_MEASUREMENT_UNSET,
    source: str | None | object = BODY_MEASUREMENT_UNSET,
    note: str | None | object = BODY_MEASUREMENT_UNSET,
) -> BodyMeasurementEntry:
    """Update and persist one existing body measurement entry."""
    entry = repository.get_by_id(str(measurement_id).strip())
    get_user(user_repository, entry.profile_id)

    next_measurement_type = measurement_type or entry.measurement_type
    canonical_value = (
        convert_input_to_canonical(
            measurement_type=next_measurement_type,
            value=value,
            unit=unit,
        )
        if value is not None
        else None
    )

    entry.update(
        measurement_type=measurement_type,
        canonical_value=canonical_value,
        measured_at=measured_at if measured_at is not BODY_MEASUREMENT_UNSET else None,
        source=source if source is not BODY_MEASUREMENT_UNSET else None,
        note=note if note is not BODY_MEASUREMENT_UNSET else None,
    )
    return await repository.update(entry)


async def delete_body_measurement(
    repository: BodyMeasurementRepository,
    *,
    measurement_id: str,
) -> BodyMeasurementEntry:
    """Tombstone one measurement entry."""
    return await repository.delete(str(measurement_id).strip())


def get_body_measurement_weight_records_for_peer(
    repository: BodyMeasurementRepository,
    *,
    profile_id: str,
    include_deleted: bool = True,
) -> list[BodyMeasurementEntry]:
    """Return weight CoreRecords for the body-measurement peer pilot."""
    return [
        entry
        for entry in repository.get_by_profile_id(
            str(profile_id).strip(),
            include_deleted=include_deleted,
        )
        if entry.measurement_type == BODY_MEASUREMENT_PEER_SYNC_TYPE
    ]


async def upsert_body_measurement_weight_peer_record(
    repository: BodyMeasurementRepository,
    *,
    incoming: BodyMeasurementEntry,
) -> BodyMeasurementPeerSyncResult:
    """Upsert one peer-synced weight CoreRecord using v1 peer conflict rules."""
    if incoming.measurement_type != BODY_MEASUREMENT_PEER_SYNC_TYPE:
        raise ValueError("Only weight body measurements are supported by this pilot.")

    try:
        existing = repository.get_by_id(incoming.record_id)
    except BrizelBodyMeasurementNotFoundError:
        saved = await repository.add(incoming)
        return BodyMeasurementPeerSyncResult(
            measurement=saved,
            imported=1,
            updated=0,
            ignored=0,
        )

    if existing.profile_id != incoming.profile_id:
        raise ValueError("Body measurement record_id belongs to another profile.")
    if existing.measurement_type != BODY_MEASUREMENT_PEER_SYNC_TYPE:
        raise ValueError("Existing body measurement is not a weight record.")

    if not _incoming_body_measurement_wins(existing=existing, incoming=incoming):
        return BodyMeasurementPeerSyncResult(
            measurement=existing,
            imported=0,
            updated=0,
            ignored=1,
        )

    saved = await repository.update(incoming)
    return BodyMeasurementPeerSyncResult(
        measurement=saved,
        imported=0,
        updated=1,
        ignored=0,
    )


def _incoming_body_measurement_wins(
    *,
    existing: BodyMeasurementEntry,
    incoming: BodyMeasurementEntry,
) -> bool:
    if incoming.revision != existing.revision:
        return incoming.revision > existing.revision

    existing_updated_at = _parse_timestamp(existing.updated_at)
    incoming_updated_at = _parse_timestamp(incoming.updated_at)
    if incoming_updated_at != existing_updated_at:
        return incoming_updated_at > existing_updated_at

    return incoming.updated_by_node_id > existing.updated_by_node_id


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
