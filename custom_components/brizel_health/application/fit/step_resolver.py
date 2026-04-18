"""Resolve canonical step views from raw step records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ...domains.fit.models.step_entry import StepEntry

STRONG_OVERLAP_RATIO = 0.5

DEFAULT_SOURCE_PRIORITY_HINTS: tuple[tuple[str, ...], ...] = (
    ("garmin",),
    ("fitbit",),
    ("samsung", "watch"),
    ("samsunghealth", "watch"),
    ("samsung health", "watch"),
    ("watch",),
    ("wear",),
    ("tracker",),
    ("google", "fit"),
    ("fitness",),
    ("phone",),
)


@dataclass(frozen=True)
class StepResolutionInterval:
    """One accepted measurement interval in the canonical step view."""

    record_id: str
    source_key: str
    origin_node_id: str
    data_origin: str | None
    measurement_start: datetime
    measurement_end: datetime
    step_count: int


@dataclass(frozen=True)
class DiscardedStepRecord:
    """One raw record excluded from the canonical step view."""

    record_id: str
    source_key: str
    reason: str
    overlapping_record_id: str | None = None


@dataclass(frozen=True)
class StepResolutionResult:
    """Resolved canonical steps and transparent resolver decisions."""

    total_steps: int
    used_sources: tuple[str, ...]
    discarded_sources: tuple[str, ...]
    notes: tuple[str, ...]
    timeline: tuple[StepResolutionInterval, ...]
    discarded_records: tuple[DiscardedStepRecord, ...]


@dataclass(frozen=True)
class _Candidate:
    entry: StepEntry
    source_key: str
    priority_rank: int


def resolve_step_records(
    entries: tuple[StepEntry, ...],
    *,
    source_priority: tuple[str, ...] = (),
) -> StepResolutionResult:
    """Resolve one canonical step view from raw step entries.

    V1 intentionally stays conservative: high-priority sources win strong
    overlaps, exact duplicates are ignored, and non-overlapping intervals add.
    """
    candidates = tuple(
        sorted(
            (
                _Candidate(
                    entry=entry,
                    source_key=_source_key(entry),
                    priority_rank=_priority_rank(entry, source_priority),
                )
                for entry in entries
                if _is_usable_step_entry(entry)
            ),
            key=lambda candidate: (
                candidate.priority_rank,
                candidate.entry.start,
                candidate.entry.end,
                candidate.entry.record_id or candidate.entry.external_record_id,
            ),
        )
    )
    discarded = [
        DiscardedStepRecord(
            record_id=entry.record_id or entry.external_record_id,
            source_key=_source_key(entry),
            reason=reason,
        )
        for entry in entries
        if (reason := _discard_reason(entry)) is not None
    ]

    accepted: list[_Candidate] = []
    notes: list[str] = []

    for candidate in candidates:
        duplicate = _matching_duplicate(candidate, accepted)
        if duplicate is not None:
            discarded.append(
                DiscardedStepRecord(
                    record_id=candidate.entry.record_id
                    or candidate.entry.external_record_id,
                    source_key=candidate.source_key,
                    reason="duplicate_lower_priority",
                    overlapping_record_id=duplicate.entry.record_id,
                )
            )
            notes.append(
                f"Discarded duplicate {candidate.source_key} in favor of "
                f"{duplicate.source_key}."
            )
            continue

        overlap = _strong_overlap(candidate, accepted)
        if overlap is not None:
            discarded.append(
                DiscardedStepRecord(
                    record_id=candidate.entry.record_id
                    or candidate.entry.external_record_id,
                    source_key=candidate.source_key,
                    reason="overlap_lower_priority",
                    overlapping_record_id=overlap.entry.record_id,
                )
            )
            notes.append(
                f"Discarded overlapping {candidate.source_key} in favor of "
                f"{overlap.source_key}."
            )
            continue

        accepted.append(candidate)

    timeline = tuple(
        sorted(
            (
                StepResolutionInterval(
                    record_id=candidate.entry.record_id
                    or candidate.entry.external_record_id,
                    source_key=candidate.source_key,
                    origin_node_id=candidate.entry.origin_node_id or "",
                    data_origin=candidate.entry.data_origin,
                    measurement_start=candidate.entry.start,
                    measurement_end=candidate.entry.end,
                    step_count=candidate.entry.steps,
                )
                for candidate in accepted
            ),
            key=lambda interval: (interval.measurement_start, interval.measurement_end),
        )
    )

    return StepResolutionResult(
        total_steps=sum(interval.step_count for interval in timeline),
        used_sources=_unique_sorted(interval.source_key for interval in timeline),
        discarded_sources=_unique_sorted(record.source_key for record in discarded),
        notes=tuple(dict.fromkeys(notes)),
        timeline=timeline,
        discarded_records=tuple(discarded),
    )


def _is_usable_step_entry(entry: StepEntry) -> bool:
    return _discard_reason(entry) is None


def _discard_reason(entry: StepEntry) -> str | None:
    if entry.deleted_at is not None:
        return "deleted"
    if entry.record_type != "steps":
        return "unsupported_record_type"
    if entry.read_mode != "raw":
        return "legacy_read_mode"
    if entry.steps < 0:
        return "invalid_step_count"
    return None


def _source_key(entry: StepEntry) -> str:
    for value in (
        entry.data_origin,
        entry.source_detail,
        entry.source,
        entry.origin_node_id,
    ):
        normalized = str(value or "").strip()
        if normalized:
            return normalized
    return "unknown"


def _priority_rank(entry: StepEntry, override: tuple[str, ...]) -> int:
    source_text = " ".join(
        str(value or "").strip().lower()
        for value in (
            entry.data_origin,
            entry.source_detail,
            entry.source,
            entry.origin_node_id,
        )
        if str(value or "").strip()
    )

    for index, pattern in enumerate(override):
        normalized = pattern.strip().lower()
        if normalized and normalized in source_text:
            return index

    base = 100 + _default_priority_rank(source_text)
    if "phone" in source_text:
        base += 20
    if any(token in source_text for token in ("watch", "wear", "tracker")):
        base -= 10
    return base


def _default_priority_rank(source_text: str) -> int:
    for index, hints in enumerate(DEFAULT_SOURCE_PRIORITY_HINTS):
        if all(hint in source_text for hint in hints):
            return index * 10
    return 900


def _matching_duplicate(
    candidate: _Candidate,
    accepted: list[_Candidate],
) -> _Candidate | None:
    for existing in accepted:
        if (
            candidate.entry.start == existing.entry.start
            and candidate.entry.end == existing.entry.end
            and candidate.entry.steps == existing.entry.steps
        ):
            return existing
    return None


def _strong_overlap(
    candidate: _Candidate,
    accepted: list[_Candidate],
) -> _Candidate | None:
    for existing in accepted:
        if _overlap_ratio(candidate.entry, existing.entry) >= STRONG_OVERLAP_RATIO:
            return existing
    return None


def _overlap_ratio(left: StepEntry, right: StepEntry) -> float:
    overlap_start = max(left.start, right.start)
    overlap_end = min(left.end, right.end)
    if overlap_end <= overlap_start:
        return 0.0

    overlap_seconds = (overlap_end - overlap_start).total_seconds()
    shorter_seconds = min(
        (left.end - left.start).total_seconds(),
        (right.end - right.start).total_seconds(),
    )
    if shorter_seconds <= 0:
        return 0.0
    return overlap_seconds / shorter_seconds


def _unique_sorted(values) -> tuple[str, ...]:
    return tuple(sorted(dict.fromkeys(value for value in values if value)))
