"""Domain errors for the Body module."""

from __future__ import annotations


class BrizelBodyError(Exception):
    """Base exception for body domain errors."""


class BrizelBodyProfileValidationError(BrizelBodyError):
    """Raised when body profile data is invalid."""


class BrizelBodyProfileNotFoundError(BrizelBodyError):
    """Raised when no body profile exists for a profile."""


class BrizelBodyGoalValidationError(BrizelBodyError):
    """Raised when body-goal data is invalid."""


class BrizelBodyMeasurementValidationError(BrizelBodyError):
    """Raised when one body measurement is invalid."""


class BrizelBodyMeasurementNotFoundError(BrizelBodyError):
    """Raised when no body measurement exists for the requested ID."""
