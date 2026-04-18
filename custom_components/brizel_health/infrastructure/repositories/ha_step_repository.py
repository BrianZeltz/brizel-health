"""Home Assistant backed Fit step repository."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from ...domains.fit.models.step_entry import StepEntry

if TYPE_CHECKING:
    from ..storage.store_manager import BrizelHealthStoreManager


class HomeAssistantStepRepository:
    """Persist Fit step entries inside the integration store."""

    def __init__(self, store_manager: "BrizelHealthStoreManager") -> None:
        self._store_manager = store_manager

    @staticmethod
    def _normalize_required_text(value: object, field_name: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError(f"{field_name} is required.")
        return normalized

    def _steps_by_profile(self) -> dict[str, dict[str, dict]]:
        fit = self._store_manager.data.setdefault("fit", {})
        return fit.setdefault("steps_by_profile", {})

    def _profile_steps(self, profile_id: str) -> dict[str, dict]:
        normalized_profile_id = self._normalize_required_text(profile_id, "profile_id")
        return self._steps_by_profile().setdefault(normalized_profile_id, {})

    def _import_state_by_profile(self) -> dict[str, dict[str, object]]:
        fit = self._store_manager.data.setdefault("fit", {})
        return fit.setdefault("steps_import_state_by_profile", {})

    def _profile_import_state(self, profile_id: str) -> dict[str, object]:
        normalized_profile_id = self._normalize_required_text(profile_id, "profile_id")
        return self._import_state_by_profile().setdefault(normalized_profile_id, {})

    @staticmethod
    def _normalize_datetime(value: datetime | str | None) -> datetime | None:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str) and value.strip():
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        else:
            return None

        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed

    def get_by_external_record_id(
        self,
        profile_id: str,
        external_record_id: str,
    ) -> StepEntry | None:
        """Load one step entry by external record ID."""
        data = self._profile_steps(profile_id).get(str(external_record_id).strip())
        if data is None:
            return None
        return StepEntry.from_dict(data)

    def get_by_message_id(self, message_id: str) -> StepEntry | None:
        """Load one step entry by app bridge message ID."""
        normalized_message_id = str(message_id).strip()
        for steps in self._steps_by_profile().values():
            for data in steps.values():
                if str(data.get("message_id", "")).strip() == normalized_message_id:
                    return StepEntry.from_dict(data)
        return None

    def exists_external_record_id(
        self,
        profile_id: str,
        external_record_id: str,
    ) -> bool:
        """Return whether an external record ID already exists."""
        return str(external_record_id).strip() in self._profile_steps(profile_id)

    def exists_message_id(self, message_id: str) -> bool:
        """Return whether a bridge message ID already exists."""
        return self.get_by_message_id(message_id) is not None

    def list_step_entries(self, profile_id: str) -> tuple[StepEntry, ...]:
        """Load stored step entries for one profile."""
        return tuple(
            StepEntry.from_dict(data)
            for data in self._profile_steps(profile_id).values()
        )

    def get_last_successful_steps_sync(self, profile_id: str) -> datetime | None:
        """Return one profile's latest successfully processed step import time."""
        state = self._profile_import_state(profile_id)
        last_sync = self._normalize_datetime(state.get("last_successful_sync"))
        if last_sync is not None:
            return last_sync

        entries = self.list_step_entries(profile_id)
        if not entries:
            return None
        return max(entry.received_at for entry in entries)

    def get_last_steps_import_status(self, profile_id: str) -> str | None:
        """Return one profile's latest successfully processed step import status."""
        status = str(self._profile_import_state(profile_id).get("last_status") or "")
        return status.strip() or None

    async def save_step_entry(self, step_entry: StepEntry) -> StepEntry:
        """Persist or replace one step entry by external record ID."""
        self._profile_steps(step_entry.profile_id)[step_entry.external_record_id] = (
            step_entry.to_dict()
        )
        await self._store_manager.async_save()
        return step_entry

    async def record_step_import_success(
        self,
        *,
        profile_id: str,
        processed_at: datetime,
        status: str,
    ) -> None:
        """Persist metadata for one profile's successfully processed step import."""
        normalized_processed_at = self._normalize_datetime(processed_at)
        if normalized_processed_at is None:
            normalized_processed_at = datetime.now(UTC)

        state = self._profile_import_state(profile_id)
        state["last_successful_sync"] = normalized_processed_at.isoformat()
        state["last_status"] = str(status or "success").strip() or "success"
        await self._store_manager.async_save()
