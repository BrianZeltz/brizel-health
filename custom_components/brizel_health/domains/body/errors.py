"""Domain errors for the Body module."""

from __future__ import annotations


class BrizelBodyError(Exception):
    """Base exception for body domain errors."""


class BrizelBodyProfileValidationError(BrizelBodyError):
    """Raised when body profile data is invalid."""


class BrizelBodyProfileNotFoundError(BrizelBodyError):
    """Raised when no body profile exists for a profile."""
