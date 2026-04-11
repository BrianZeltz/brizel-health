"""Derived target values for one profile."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .body_target_range import BodyTargetRange


@dataclass(slots=True)
class BodyTargets:
    """Derived daily targets based on body data."""

    profile_id: str
    target_daily_kcal: int | None
    target_daily_protein: float | None
    target_daily_fat: float | None
    missing_fields: tuple[str, ...] = ()
    unsupported_reasons: tuple[str, ...] = ()
    target_ranges: dict[str, BodyTargetRange] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize targets for service responses and debugging."""
        return {
            "profile_id": self.profile_id,
            "target_daily_kcal": self.target_daily_kcal,
            "target_daily_protein": self.target_daily_protein,
            "target_daily_fat": self.target_daily_fat,
            "missing_fields": list(self.missing_fields),
            "unsupported_reasons": list(self.unsupported_reasons),
            "target_ranges": {
                key: target_range.to_dict()
                for key, target_range in self.target_ranges.items()
            },
        }
