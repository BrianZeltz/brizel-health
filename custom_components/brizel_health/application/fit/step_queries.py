"""Read-side helpers for Fit step entries."""

from __future__ import annotations

from datetime import date, datetime, tzinfo

from ...domains.fit.interfaces.step_repository import StepRepository
from ...domains.fit.models.step_entry import StepEntry


def get_step_entry_by_external_record_id(
    *,
    repository: StepRepository,
    profile_id: str,
    external_record_id: str,
) -> StepEntry | None:
    """Return one step entry by external record ID."""
    return repository.get_by_external_record_id(profile_id, external_record_id)


def step_entry_exists(
    *,
    repository: StepRepository,
    profile_id: str,
    external_record_id: str,
) -> bool:
    """Return whether one external step record is already stored."""
    return repository.exists_external_record_id(profile_id, external_record_id)


def get_steps_for_date(
    *,
    repository: StepRepository,
    profile_id: str,
    target_date: date,
    time_zone: tzinfo | None = None,
) -> tuple[StepEntry, ...]:
    """Return one profile's step entries whose start belongs to a local date."""

    def entry_date(step_entry: StepEntry) -> date:
        start = step_entry.start
        if time_zone is not None:
            start = start.astimezone(time_zone)
        return start.date()

    return tuple(
        sorted(
            (
                step_entry
                for step_entry in repository.list_step_entries(profile_id)
                if entry_date(step_entry) == target_date
            ),
            key=lambda step_entry: step_entry.start,
        )
    )


def get_today_steps(
    *,
    repository: StepRepository,
    profile_id: str,
    today: date,
    time_zone: tzinfo | None = None,
) -> int:
    """Return one profile's aggregated step count for one local day."""
    return sum(
        step_entry.steps
        for step_entry in get_steps_for_date(
            repository=repository,
            profile_id=profile_id,
            target_date=today,
            time_zone=time_zone,
        )
    )


def get_last_successful_steps_sync(
    *,
    repository: StepRepository,
    profile_id: str,
) -> datetime | None:
    """Return one profile's latest successfully processed step import timestamp."""
    return repository.get_last_successful_steps_sync(profile_id)


def get_last_steps_import_status(
    *,
    repository: StepRepository,
    profile_id: str,
) -> str | None:
    """Return one profile's latest successfully processed step import status."""
    return repository.get_last_steps_import_status(profile_id)
