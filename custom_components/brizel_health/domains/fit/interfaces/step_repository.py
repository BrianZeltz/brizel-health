"""Repository interface for Fit step entries."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from ..models.step_entry import StepEntry


class StepRepository(Protocol):
    """Persistence contract for idempotent step entries."""

    def get_by_external_record_id(
        self,
        profile_id: str,
        external_record_id: str,
    ) -> StepEntry | None:
        """Return one step entry by external record ID, if present."""

    def get_by_message_id(self, message_id: str) -> StepEntry | None:
        """Return one step entry by app bridge message ID, if present."""

    def exists_external_record_id(
        self,
        profile_id: str,
        external_record_id: str,
    ) -> bool:
        """Return whether an external record ID already exists."""

    def exists_message_id(self, message_id: str) -> bool:
        """Return whether a bridge message ID already exists."""

    def list_step_entries(self, profile_id: str) -> tuple[StepEntry, ...]:
        """Return stored step entries for one profile."""

    def get_last_successful_steps_sync(self, profile_id: str) -> datetime | None:
        """Return the latest successfully processed step import time for one profile."""

    def get_last_steps_import_status(self, profile_id: str) -> str | None:
        """Return the latest successfully processed step import status for one profile."""

    async def save_step_entry(self, step_entry: StepEntry) -> StepEntry:
        """Persist one step entry."""

    async def record_step_import_success(
        self,
        *,
        profile_id: str,
        processed_at: datetime,
        status: str,
    ) -> None:
        """Persist metadata for one profile's successfully processed step import."""
