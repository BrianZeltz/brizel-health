"""Read-side helpers for Fit step entries."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta, tzinfo

from ...domains.fit.interfaces.step_repository import StepRepository
from ...domains.fit.models.step_entry import StepEntry
from .step_resolver import StepResolutionResult, resolve_step_records


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
    """Return raw step entries whose measurement interval overlaps a local date."""
    day_start, day_end = _day_bounds(target_date, time_zone)

    return tuple(
        sorted(
            (
                step_entry
                for step_entry in repository.list_step_entries(profile_id)
                if step_entry.end > day_start and step_entry.start < day_end
            ),
            key=lambda step_entry: step_entry.start,
        )
    )


def resolve_steps_for_date(
    *,
    repository: StepRepository,
    profile_id: str,
    target_date: date,
    time_zone: tzinfo | None = None,
    source_priority_override: tuple[str, ...] | None = None,
) -> StepResolutionResult:
    """Resolve the canonical step view for one profile/date from raw records."""
    source_priority = (
        source_priority_override
        if source_priority_override is not None
        else repository.get_step_source_priority(profile_id)
    )
    return resolve_step_records(
        get_steps_for_date(
            repository=repository,
            profile_id=profile_id,
            target_date=target_date,
            time_zone=time_zone,
        ),
        source_priority=source_priority,
    )


def get_today_steps(
    *,
    repository: StepRepository,
    profile_id: str,
    today: date,
    time_zone: tzinfo | None = None,
) -> int:
    """Return one profile's resolved canonical step count for one local day."""
    return resolve_steps_for_date(
        repository=repository,
        profile_id=profile_id,
        target_date=today,
        time_zone=time_zone,
    ).total_steps


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


def _day_bounds(
    target_date: date,
    time_zone: tzinfo | None,
) -> tuple[datetime, datetime]:
    zone = time_zone or UTC
    day_start = datetime.combine(target_date, time.min, tzinfo=zone)
    day_end = datetime.combine(
        target_date + timedelta(days=1),
        time.min,
        tzinfo=zone,
    )
    return day_start, day_end
