"""Standard response helpers for the Brizel Health app bridge."""

from __future__ import annotations

from uuid import uuid4


def bridge_success_response(**payload: object) -> dict[str, object]:
    """Return a standardized bridge success response."""
    return {
        "ok": True,
        **payload,
    }


def bridge_error_response(
    *,
    error_code: str,
    message: str,
    field_errors: dict[str, str] | None = None,
    correlation_id: str | None = None,
) -> dict[str, object]:
    """Return a standardized bridge error response."""
    return {
        "ok": False,
        "correlation_id": correlation_id or str(uuid4()),
        "error_code": error_code,
        "message": message,
        "field_errors": field_errors or {},
    }
