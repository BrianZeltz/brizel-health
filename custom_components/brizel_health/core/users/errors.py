"""User domain errors."""

from __future__ import annotations


class BrizelUserError(Exception):
    """Base exception for user domain errors."""


class BrizelUserValidationError(BrizelUserError):
    """Raised when user data is invalid."""


class BrizelUserAlreadyExistsError(BrizelUserError):
    """Raised when a user with the same display name already exists."""


class BrizelUserNotFoundError(BrizelUserError):
    """Raised when a user could not be found."""
