"""Read queries for body measurements."""

from __future__ import annotations

from ...core.interfaces.user_repository import UserRepository
from ...domains.body.interfaces.body_measurement_repository import (
    BodyMeasurementRepository,
)
from ...domains.body.models.body_measurement_entry import BodyMeasurementEntry
from ...domains.body.models.body_measurement_type import (
    BodyMeasurementTypeDefinition,
    get_body_measurement_types,
)
from ..users.user_use_cases import get_user


def _measurement_sort_key(entry: BodyMeasurementEntry) -> tuple[str, str, str]:
    return (entry.measured_at, entry.updated_at, entry.created_at)


def get_body_measurement_definitions() -> tuple[BodyMeasurementTypeDefinition, ...]:
    """Return the stable registry of supported measurement types."""
    return get_body_measurement_types()


def get_measurement_history(
    repository: BodyMeasurementRepository,
    user_repository: UserRepository,
    *,
    profile_id: str,
    measurement_type: str | None = None,
    limit: int | None = None,
) -> list[BodyMeasurementEntry]:
    """Return measurement history sorted from newest to oldest."""
    user = get_user(user_repository, profile_id)
    entries = repository.get_by_profile_id(user.user_id)
    if measurement_type is not None:
        normalized_type = str(measurement_type).strip().lower()
        entries = [
            entry
            for entry in entries
            if entry.measurement_type == normalized_type
        ]

    entries.sort(key=_measurement_sort_key, reverse=True)
    if limit is not None and limit >= 0:
        return entries[:limit]
    return entries


def get_latest_measurement(
    repository: BodyMeasurementRepository,
    user_repository: UserRepository,
    *,
    profile_id: str,
    measurement_type: str,
) -> BodyMeasurementEntry | None:
    """Return the latest measurement for one type."""
    history = get_measurement_history(
        repository,
        user_repository,
        profile_id=profile_id,
        measurement_type=measurement_type,
        limit=1,
    )
    return history[0] if history else None
