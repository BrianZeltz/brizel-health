"""Write use cases for body measurements."""

from __future__ import annotations

from ...core.interfaces.user_repository import UserRepository
from ...domains.body.interfaces.body_measurement_repository import (
    BodyMeasurementRepository,
)
from ...domains.body.models.body_measurement_entry import BodyMeasurementEntry
from ...domains.body.services.body_measurement_units import convert_input_to_canonical
from ..users.user_use_cases import get_user

BODY_MEASUREMENT_UNSET = object()


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
    """Delete one measurement entry."""
    return await repository.delete(str(measurement_id).strip())
