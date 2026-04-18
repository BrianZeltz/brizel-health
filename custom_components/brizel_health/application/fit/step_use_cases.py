"""Use-case skeleton for Fit step imports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from ...domains.fit.interfaces.step_repository import StepRepository
from ...domains.fit.models.step_entry import StepEntry


class ConflictingStepRecordError(ValueError):
    """Raised when an immutable external step record differs from stored content."""


class DuplicateStepMessageError(ValueError):
    """Raised when one message ID is reused for another import."""


@dataclass(frozen=True)
class StepImportResult:
    """Outcome of one app bridge step import."""

    step_entry: StepEntry
    imported: int
    updated: int
    ignored_duplicates: int

    def to_result_dict(self) -> dict[str, int]:
        """Serialize counters for bridge responses."""
        return {
            "imported": self.imported,
            "updated": self.updated,
            "ignored_duplicates": self.ignored_duplicates,
        }


async def import_step_entry(
    *,
    repository: StepRepository,
    external_record_id: str,
    profile_id: str,
    message_id: str,
    device_id: str,
    source: str,
    start: datetime | str,
    end: datetime | str,
    steps: int,
    received_at: datetime | str | None = None,
    timezone: str | None = None,
    origin: str | None = None,
) -> StepImportResult:
    """Import one step entry into the Fit module.

    external_record_id is immutable. Identical replays are accepted as ignored
    duplicates; conflicting replays are rejected instead of overwritten.
    """
    step_entry = StepEntry(
        external_record_id=external_record_id,
        profile_id=profile_id,
        message_id=message_id,
        device_id=device_id,
        source=source,
        start=start,
        end=end,
        steps=steps,
        received_at=received_at or datetime.now(UTC),
        timezone=timezone,
        origin=origin,
    )

    existing = repository.get_by_external_record_id(
        step_entry.profile_id,
        step_entry.external_record_id,
    )
    if existing is not None:
        if existing.has_same_import_content(step_entry):
            await repository.record_step_import_success(
                profile_id=step_entry.profile_id,
                processed_at=step_entry.received_at,
                status="duplicate_ignored",
            )
            return StepImportResult(
                step_entry=existing,
                imported=0,
                updated=0,
                ignored_duplicates=1,
            )
        raise ConflictingStepRecordError(
            f"Step record '{step_entry.external_record_id}' already exists with different content."
        )

    existing_message = repository.get_by_message_id(step_entry.message_id)
    if existing_message is not None:
        raise DuplicateStepMessageError(
            f"Step message '{step_entry.message_id}' was already processed."
        )

    saved_entry = await repository.save_step_entry(step_entry)
    await repository.record_step_import_success(
        profile_id=saved_entry.profile_id,
        processed_at=saved_entry.received_at,
        status="success",
    )
    return StepImportResult(
        step_entry=saved_entry,
        imported=1,
        updated=0,
        ignored_duplicates=0,
    )
