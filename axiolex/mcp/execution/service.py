"""ToolExecutionService — the axiolex_execute_tool dispatcher core.

Implements the execution flow:

    1. Resolve   — look up tool_id in the current catalog (Redis).
    2. Validate  — validate arguments against the tool's *current* schema.
    3. Dispatch  — route to the transport adapter for the resolved transport.
    4. Timeout   — enforce timeout_ms (or the dispatcher default ceiling).
    5. Normalize — map the adapter result into the response contract.

Every call is fully self-contained: everything needed to execute is
resolved fresh from the catalog by ``tool_id``. The dispatcher does not
depend on ``axiolex_discover_tools`` having been called in the same
session, process, or with any shared server-side state.

Phase 1 does not implement user-level authorization or policy enforcement.
The execution interface is intended for trusted environments. Authentication,
authorization, and per-user capability governance can be added later as a
separate execution-policy layer without changing this contract.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, Optional

from ...core.cache import ToolCacheManager, get_cache_manager
from .adapters import get_adapter
from .errors import (
    ExecutionError,
    INTERNAL_ERROR,
    INVALID_ARGUMENTS,
    TOOL_NOT_FOUND,
    UPSTREAM_TIMEOUT,
)


# --- Configuration --------------------------------------------------------

def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _resolve_timeout_seconds(timeout_ms: Optional[int]) -> float:
    """Caller timeout clamped to the dispatcher ceiling (seconds)."""
    ceiling_ms = _env_int("AXIOLEX_EXECUTE_TIMEOUT_MS", 30000)
    if timeout_ms is None:
        return ceiling_ms / 1000.0
    return min(max(int(timeout_ms), 1), ceiling_ms) / 1000.0


# --- Argument validation (JSON-Schema-lite) -------------------------------

_JSON_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "null": lambda v: v is None,
}


def _validate_arguments(
    arguments: Any,
    params: Dict[str, Any],
) -> None:
    """Validate ``arguments`` against the tool's current property schema.

    ``params`` is the JSON Schema ``properties`` dict cached at index time.
    ``required`` is not currently persisted in the catalog, so required-field
    checks are deferred until the schema store carries them. Type checks use
    JSON Schema primitive types; ``additionalProperties`` defaults to true,
    so unknown keys are allowed (lenient) to avoid breaking tools that
    accept extra fields.
    """
    if not isinstance(arguments, dict):
        raise ExecutionError(
            INVALID_ARGUMENTS,
            "arguments must be an object",
            retryable=False,
        )
    for key, value in arguments.items():
        spec = params.get(key)
        if spec is None:
            continue
        types = spec.get("type") if isinstance(spec, dict) else None
        if types is None:
            continue
        allowed = types if isinstance(types, list) else [types]
        if not any(
            t in _JSON_TYPE_CHECKS and _JSON_TYPE_CHECKS[t](value) for t in allowed
        ):
            raise ExecutionError(
                INVALID_ARGUMENTS,
                f"argument '{key}' expected type {types}, "
                f"got {type(value).__name__}",
                retryable=False,
            )


# --- Execution audit logging ----------------------------------------------

_AUDIT_LOGGER_NAME = "axiolex.execution_audit"
_audit_logger_configured = False


def _get_audit_logger() -> logging.Logger:
    global _audit_logger_configured
    audit_logger = logging.getLogger(_AUDIT_LOGGER_NAME)
    if not _audit_logger_configured:
        log_dir = os.getenv("AXIOLEX_LOG_DIR", "logs")
        try:
            os.makedirs(log_dir, exist_ok=True)
            handler = RotatingFileHandler(
                os.path.join(log_dir, "execution_audit.jsonl"),
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8",
            )
            handler.setFormatter(logging.Formatter("%(message)s"))
            audit_logger.addHandler(handler)
            audit_logger.setLevel(logging.INFO)
            audit_logger.propagate = False
        except Exception as exc:
            logging.getLogger("axiolex").warning(
                "Could not configure execution audit logger: %s", exc
            )
        _audit_logger_configured = True
    return audit_logger


def _write_audit_record(
    execution_id: str,
    tool_id: str,
    namespace: Optional[str],
    status: str,
    error: Optional[Dict[str, Any]],
    latency_ms: int,
    idempotency_key: Optional[str],
) -> None:
    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "execution_id": execution_id,
        "tool_id": tool_id,
        "namespace": namespace,
        "status": status,
        "error": error,
        "latency_ms": latency_ms,
        "idempotency_key": idempotency_key,
    }
    # Phase 1: argument/result payloads are NOT logged. They will be logged
    # subject to the tool's namespace/sensitivity classification once that
    # classification is wired through the catalog.
    try:
        _get_audit_logger().info(json.dumps(record, ensure_ascii=False))
    except Exception as exc:
        logging.getLogger("axiolex").warning(
            "Failed to write execution audit record: %s", exc
        )


# --- Service --------------------------------------------------------------

class ToolExecutionService:
    """Generic tool dispatcher backing ``axiolex_execute_tool``.

    Args:
        cache_manager: Redis catalog reader. Defaults to the global manager.
    """

    def __init__(
        self,
        cache_manager: Optional[ToolCacheManager] = None,
    ):
        self.cache_manager = cache_manager or get_cache_manager()

    async def execute_tool(
        self,
        tool_id: str,
        arguments: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        timeout_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Execute a tool and return the full response envelope.

        Always echoes ``tool_id`` and a fresh ``execution_id`` on both
        success and error paths. Never raises: every failure is normalized
        into the ``error`` field of the response.
        """
        execution_id = uuid.uuid4().hex
        start = time.monotonic()
        status = "error"
        result: Optional[Dict[str, Any]] = None
        error: Optional[Dict[str, Any]] = None
        namespace: Optional[str] = None

        try:
            # 1. Resolve — fresh from the current catalog.
            discovery = self.cache_manager.get_discovery(tool_id)
            if not discovery:
                raise ExecutionError(
                    TOOL_NOT_FOUND,
                    f"Tool '{tool_id}' not found in the current catalog",
                    retryable=False,
                )
            runtime = self.cache_manager.get_runtime(tool_id) or {}
            if not runtime.get("tool_name"):
                raise ExecutionError(
                    TOOL_NOT_FOUND,
                    f"Tool '{tool_id}' has no executable runtime metadata",
                    retryable=False,
                )
            namespaces = discovery.get("namespaces") or []
            namespace = namespaces[0] if namespaces else None

            # 2. Validate — against the *current* schema, not a caller cache.
            _validate_arguments(arguments, discovery.get("params") or {})

            # 3-4. Dispatch via transport adapter, enforce timeout.
            adapter = get_adapter(runtime.get("transport"))
            timeout_s = _resolve_timeout_seconds(timeout_ms)
            raw = await asyncio.wait_for(
                adapter.execute(runtime, arguments), timeout=timeout_s
            )

            # 5. Normalize.
            result = raw
            status = "success"
        except ExecutionError as exc:
            error = {
                "code": exc.code,
                "message": exc.message,
                "retryable": exc.retryable,
            }
        except asyncio.TimeoutError:
            error = {
                "code": UPSTREAM_TIMEOUT,
                "message": (
                    f"Tool '{tool_id}' exceeded the "
                    f"{int(_resolve_timeout_seconds(timeout_ms) * 1000)}ms timeout"
                ),
                "retryable": True,
            }
        except Exception as exc:  # noqa: BLE001 — dispatcher must not leak
            error = {
                "code": INTERNAL_ERROR,
                "message": f"Internal dispatcher error: {exc}",
                "retryable": True,
            }

        latency_ms = int((time.monotonic() - start) * 1000)
        _write_audit_record(
            execution_id=execution_id,
            tool_id=tool_id,
            namespace=namespace,
            status=status,
            error=error,
            latency_ms=latency_ms,
            idempotency_key=idempotency_key,
        )

        response: Dict[str, Any] = {
            "status": status,
            "tool_id": tool_id,
            "execution_id": execution_id,
        }
        if status == "success":
            response["result"] = result
        else:
            response["error"] = error
        return response


# --- Convenience module-level function ------------------------------------

async def execute_tool(
    tool_id: str,
    arguments: Dict[str, Any],
    idempotency_key: Optional[str] = None,
    timeout_ms: Optional[int] = None,
    cache_manager: Optional[ToolCacheManager] = None,
) -> Dict[str, Any]:
    """Convenience API for package consumers."""
    service = ToolExecutionService(cache_manager=cache_manager)
    return await service.execute_tool(
        tool_id=tool_id,
        arguments=arguments,
        idempotency_key=idempotency_key,
        timeout_ms=timeout_ms,
    )
