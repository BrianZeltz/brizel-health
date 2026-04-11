"""Range-based target data for one derived body goal."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class BodyTargetRange:
    """Transparent range model for one body target."""

    minimum: float | int | None
    recommended: float | int | None
    maximum: float | int | None
    method: str
    formula: str
    required_fields: tuple[str, ...]
    missing_fields: tuple[str, ...] = ()
    unsupported_reasons: tuple[str, ...] = ()
    inputs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the target range for service responses and debugging."""
        return {
            "minimum": self.minimum,
            "recommended": self.recommended,
            "maximum": self.maximum,
            "method": self.method,
            "formula": self.formula,
            "required_fields": list(self.required_fields),
            "missing_fields": list(self.missing_fields),
            "unsupported_reasons": list(self.unsupported_reasons),
            "inputs": self.inputs,
        }
