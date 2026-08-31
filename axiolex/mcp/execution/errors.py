"""Error taxonomy for axiolex_execute_tool — Phase 1.

These codes are the stable external contract. A caller handling errors
must never need transport-specific error logic, so every adapter maps its
raw upstream failure into one of these codes.

Phase 1 does not implement user-level authorization or policy enforcement.
The execution interface is intended for trusted environments. Authentication,
authorization, and per-user capability governance can be added later as a
separate execution-policy layer without changing this contract.
"""

from __future__ import annotations

from typing import Optional


# --- Phase 1 error codes --------------------------------------------------
TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
TOOL_UNAVAILABLE = "TOOL_UNAVAILABLE"
INVALID_ARGUMENTS = "INVALID_ARGUMENTS"
UPSTREAM_TIMEOUT = "UPSTREAM_TIMEOUT"
UPSTREAM_ERROR = "UPSTREAM_ERROR"
RATE_LIMITED = "RATE_LIMITED"
INTERNAL_ERROR = "INTERNAL_ERROR"


# Codes that are never retryable regardless of per-call upstream status.
_NOT_RETRYABLE = {
    TOOL_NOT_FOUND,
    TOOL_UNAVAILABLE,
    INVALID_ARGUMENTS,
}

# Codes that are always retryable (transient dispatcher/upstream failures).
_ALWAYS_RETRYABLE = {UPSTREAM_TIMEOUT, RATE_LIMITED, INTERNAL_ERROR}


class ExecutionError(Exception):
    """Raised by the execution pipeline to short-circuit into an error response.

    Attributes:
        code: One of the stable error codes above.
        message: Human-readable, safe to surface to the caller.
        retryable: Whether a caller should consider retrying. When
            ``None``, inferred from ``code`` (UPSTREAM_ERROR is the only
            code whose retryability is per-call, set explicitly by the
            adapter that raised it).
    """

    def __init__(self, code: str, message: str, retryable: Optional[bool] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        if retryable is None:
            retryable = code in _ALWAYS_RETRYABLE
        self.retryable = retryable
