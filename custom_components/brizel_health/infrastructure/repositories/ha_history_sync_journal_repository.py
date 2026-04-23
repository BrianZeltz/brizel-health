"""Home Assistant backed history sync journal."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Callable, Iterable

if TYPE_CHECKING:
    from ..storage.store_manager import BrizelHealthStoreManager

HistoryRecordSerializer = Callable[[object], dict[str, object]]

_JOURNAL_COMPACTION_THRESHOLD = 2048
_JOURNAL_COMPACTION_RECENT_TAIL = 512


@dataclass(frozen=True)
class HistorySyncJournalEntry:
    """One persisted server-side history change for sync cursors."""

    sequence: int
    domain: str
    profile_id: str
    record_id: str
    record_updated_at: datetime | None
    updated_by_node_id: str | None
    deleted_at: datetime | None
    changed_at: datetime
    record: dict[str, object]

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "HistorySyncJournalEntry":
        return cls(
            sequence=int(data.get("sequence") or 0),
            domain=str(data.get("domain") or "").strip(),
            profile_id=str(data.get("profile_id") or "").strip(),
            record_id=str(data.get("record_id") or "").strip(),
            record_updated_at=_parse_datetime(data.get("record_updated_at")),
            updated_by_node_id=_optional_text(data.get("updated_by_node_id")),
            deleted_at=_parse_datetime(data.get("deleted_at")),
            changed_at=_parse_datetime(data.get("changed_at")) or datetime.now(UTC),
            record=dict(data.get("record") if isinstance(data.get("record"), dict) else {}),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "domain": self.domain,
            "profile_id": self.profile_id,
            "record_id": self.record_id,
            "record_updated_at": _format_datetime(self.record_updated_at),
            "updated_by_node_id": self.updated_by_node_id,
            "deleted_at": _format_datetime(self.deleted_at),
            "changed_at": _format_datetime(self.changed_at),
            "record": self.record,
        }


class HomeAssistantHistorySyncJournalRepository:
    """Persist a monotone server-side change feed above canonical records."""

    def __init__(self, store_manager: "BrizelHealthStoreManager") -> None:
        self._store_manager = store_manager

    def _journal(self) -> dict[str, object]:
        sync = self._store_manager.data.setdefault("sync", {})
        journal = sync.setdefault("history_journal", {})
        journal.setdefault("next_sequence", 1)
        journal.setdefault("entries", [])
        journal.setdefault("fingerprints", {})
        return journal

    def _entries(self) -> list[dict[str, object]]:
        entries = self._journal().setdefault("entries", [])
        if not isinstance(entries, list):
            self._journal()["entries"] = []
            return self._journal()["entries"]
        return entries

    def _fingerprints(self) -> dict[str, int]:
        fingerprints = self._journal().setdefault("fingerprints", {})
        if not isinstance(fingerprints, dict):
            self._journal()["fingerprints"] = {}
            return self._journal()["fingerprints"]
        return fingerprints

    def _compact_entries_if_needed(self) -> bool:
        entries = self._entries()
        if len(entries) <= _JOURNAL_COMPACTION_THRESHOLD:
            return False

        parsed = [
            HistorySyncJournalEntry.from_dict(data)
            for data in entries
            if isinstance(data, dict)
        ]
        if len(parsed) <= _JOURNAL_COMPACTION_THRESHOLD:
            return False

        retained_by_sequence: dict[int, HistorySyncJournalEntry] = {}
        recent_tail = parsed[-_JOURNAL_COMPACTION_RECENT_TAIL :]
        for entry in recent_tail:
            retained_by_sequence[entry.sequence] = entry

        latest_by_record: dict[str, HistorySyncJournalEntry] = {}
        for entry in parsed:
            latest_by_record[_entry_key(entry)] = entry
        for entry in latest_by_record.values():
            retained_by_sequence[entry.sequence] = entry

        retained = [
            retained_by_sequence[sequence]
            for sequence in sorted(retained_by_sequence.keys())
        ]
        if len(retained) >= len(parsed):
            return False

        journal = self._journal()
        journal["entries"] = [entry.to_dict() for entry in retained]
        journal["fingerprints"] = {
            _record_fingerprint(
                domain=entry.domain,
                profile_id=entry.profile_id,
                record_id=entry.record_id,
                record_payload=entry.record,
            ): entry.sequence
            for entry in retained
        }
        return True

    async def record_snapshot(
        self,
        *,
        domain: str,
        profile_id: str,
        records: Iterable[object],
        serialize_record: HistoryRecordSerializer,
    ) -> tuple[HistorySyncJournalEntry, ...]:
        """Journal record revisions not yet represented in the HA change feed."""
        appended: list[HistorySyncJournalEntry] = []
        entries = self._entries()
        fingerprints = self._fingerprints()
        for record in records:
            record_payload = serialize_record(record)
            record_id = str(record_payload.get("record_id") or "").strip()
            if not record_id:
                continue
            fingerprint = _record_fingerprint(
                domain=domain,
                profile_id=profile_id,
                record_id=record_id,
                record_payload=record_payload,
            )
            if fingerprint in fingerprints:
                continue

            sequence = int(self._journal().get("next_sequence") or 1)
            self._journal()["next_sequence"] = sequence + 1
            entry = HistorySyncJournalEntry(
                sequence=sequence,
                domain=domain,
                profile_id=profile_id,
                record_id=record_id,
                record_updated_at=_parse_datetime(record_payload.get("updated_at")),
                updated_by_node_id=_optional_text(
                    record_payload.get("updated_by_node_id")
                ),
                deleted_at=_parse_datetime(record_payload.get("deleted_at")),
                changed_at=datetime.now(UTC),
                record=record_payload,
            )
            entries.append(entry.to_dict())
            fingerprints[fingerprint] = sequence
            appended.append(entry)

        if appended:
            self._compact_entries_if_needed()
            await self._store_manager.async_save()
        return tuple(appended)

    def list_changes(
        self,
        *,
        domain: str,
        profile_id: str,
        after_cursor: str | None = None,
        updated_after: datetime | None = None,
        requesting_node_id: str | None = None,
    ) -> tuple[HistorySyncJournalEntry, ...]:
        """Return journal entries after the requested cursor/checkpoint."""
        after_sequence = _parse_cursor(after_cursor)
        exclude_node_id = _optional_text(requesting_node_id)
        changes: list[HistorySyncJournalEntry] = []
        for data in self._entries():
            if not isinstance(data, dict):
                continue
            entry = HistorySyncJournalEntry.from_dict(data)
            if entry.domain != domain or entry.profile_id != profile_id:
                continue
            if after_sequence is not None:
                if entry.sequence <= after_sequence:
                    continue
            elif updated_after is not None:
                if entry.record_updated_at is None:
                    continue
                if entry.record_updated_at <= updated_after:
                    continue
            if exclude_node_id is not None and entry.updated_by_node_id == exclude_node_id:
                continue
            changes.append(entry)
        return tuple(sorted(changes, key=lambda entry: entry.sequence))

    def latest_cursor(self, *, domain: str, profile_id: str) -> str | None:
        """Return the latest journal cursor for one profile/domain feed."""
        latest: int | None = None
        for data in self._entries():
            if not isinstance(data, dict):
                continue
            entry = HistorySyncJournalEntry.from_dict(data)
            if entry.domain != domain or entry.profile_id != profile_id:
                continue
            latest = entry.sequence if latest is None else max(latest, entry.sequence)
        return None if latest is None else str(latest)


def _record_fingerprint(
    *,
    domain: str,
    profile_id: str,
    record_id: str,
    record_payload: dict[str, object],
) -> str:
    return "|".join(
        (
            domain,
            profile_id,
            record_id,
            str(record_payload.get("updated_at") or ""),
            str(record_payload.get("revision") or ""),
            str(record_payload.get("deleted_at") or ""),
        )
    )


def _entry_key(entry: HistorySyncJournalEntry) -> str:
    return "|".join((entry.domain, entry.profile_id, entry.record_id))


def _parse_cursor(value: object) -> int | None:
    normalized = _optional_text(value)
    if normalized is None:
        return None
    try:
        parsed = int(normalized)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def _parse_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    normalized = str(value).strip()
    if not normalized:
        return None
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _optional_text(value: object) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None
