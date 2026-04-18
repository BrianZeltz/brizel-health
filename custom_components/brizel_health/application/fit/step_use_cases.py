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
    record_id: str | None = None,
    record_type: str = "steps",
    origin_node_id: str | None = None,
    source_type: str | None = None,
    source_detail: str | None = None,
    created_at: datetime | str | None = None,
    updated_at: datetime | str | None = None,
    updated_by_node_id: str | None = None,
    revision: int = 1,
    payload_version: int = 1,
    deleted_at: datetime | str | None = None,
    read_mode: str = "raw",
    data_origin: str | None = None,
) -> StepImportResult:
    """Import one step entry into the Fit module.

    external_record_id identifies the canonical raw record. Identical replays
    are ignored; changed content for the same record becomes a new revision.
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
        record_id=record_id,
        record_type=record_type,
        origin_node_id=origin_node_id,
        source_type=source_type,
        source_detail=source_detail,
        created_at=created_at,
        updated_at=updated_at,
        updated_by_node_id=updated_by_node_id,
        revision=revision,
        payload_version=payload_version,
        deleted_at=deleted_at,
        read_mode=read_mode,
        data_origin=data_origin,
    )

    existing = repository.get_by_external_record_id(
        step_entry.profile_id,
        step_entry.external_record_id,
    )
    existing_message = repository.get_by_message_id(step_entry.message_id)
    if (
        existing_message is not None
        and existing is not None
        and existing_message.record_id != existing.record_id
    ):
        raise DuplicateStepMessageError(
            f"Step message '{step_entry.message_id}' was already processed."
        )
    if existing_message is not None and existing is None:
        raise DuplicateStepMessageError(
            f"Step message '{step_entry.message_id}' was already processed."
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
        updated_entry = await repository.save_step_entry(
            existing.updated_from_import(step_entry)
        )
        await repository.record_step_import_success(
            profile_id=updated_entry.profile_id,
            processed_at=updated_entry.received_at,
            status="updated",
        )
        return StepImportResult(
            step_entry=updated_entry,
            imported=0,
            updated=1,
            ignored_duplicates=0,
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
