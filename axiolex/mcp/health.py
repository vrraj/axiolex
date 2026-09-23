"""Provider health status tracking for MCP and A2A providers.

States:
- ``healthy``: the last check succeeded and the provider returned tools
- ``degraded``: reachable, but returned no tools or the last check was
  only partially successful (e.g. auth accepted, nothing to serve)
- ``unreachable``: the connection failed on the last attempt
- ``unknown``: the provider has never been checked
- ``disabled``: derived at read time when the provider is disabled in
  the registry (never stored)

Status lives in a Redis hash per provider (``axiolex:status:provider:{id}``)
shared by the API server and the MCP server. It is written by three
sources:

1. Discovery attempts (manual "Retrieve Tools" and catalog refresh)
2. Execution failures (``UPSTREAM_ERROR`` / ``UPSTREAM_TIMEOUT`` mark the
   provider unreachable within seconds of a real failure)
3. On-demand probes (``POST /mcp-providers/status/check``)

Status is advisory: a tool whose provider looks healthy can still fail,
and one marked unreachable may recover. Execution errors remain the
source of truth.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..core.cache import ToolCacheManager, get_cache_manager
from .security import append_api_key, build_stdio_env, redact_url, resolve_secret

HEALTHY = "healthy"
DEGRADED = "degraded"
UNREACHABLE = "unreachable"
UNKNOWN = "unknown"

STATUS_PREFIX = "axiolex:status:provider:"

_MAX_ERROR_LENGTH = 500


class _DegradedProbeError(Exception):
    """Raised by probes when the provider is reachable but not usable."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _probe_timeout_seconds(provider: Any) -> float:
    """Probe timeout: provider timeout, capped by the deployment ceiling."""
    ceiling = 10.0
    raw = os.getenv("AXIOLEX_HEALTH_CHECK_TIMEOUT_SECONDS")
    if raw:
        try:
            ceiling = float(raw)
        except ValueError:
            pass
    provider_timeout = getattr(getattr(provider, "limits", None), "timeout_seconds", 10)
    try:
        return min(ceiling, max(float(provider_timeout), 1.0))
    except (TypeError, ValueError):
        return ceiling


class ProviderHealthService:
    """Read/write provider status and actively probe providers."""

    def __init__(self, cache_manager: Optional[ToolCacheManager] = None):
        self.cache_manager = cache_manager or get_cache_manager()

    # --- Store -------------------------------------------------------------

    def record_status(
        self,
        provider_id: str,
        state: str,
        error: Optional[str] = None,
        source: str = "discovery",
        tool_count: Optional[int] = None,
    ) -> None:
        """Write the latest status for a provider. Never raises."""
        try:
            key = f"{STATUS_PREFIX}{provider_id}"
            now = _now_iso()
            mapping: Dict[str, str] = {
                "state": state,
                "last_checked": now,
                "last_error": (error or "")[:_MAX_ERROR_LENGTH],
                "source": source,
            }
            if state == HEALTHY:
                mapping["last_success"] = now
            if tool_count is not None:
                mapping["tool_count"] = str(tool_count)
            self.cache_manager.client.hset(key, mapping=mapping)
        except Exception:
            # Status tracking must never break discovery or execution.
            pass

    def get_status(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """Return the stored status for a provider, or None if never checked."""
        try:
            data = self.cache_manager.client.hgetall(
                f"{STATUS_PREFIX}{provider_id}"
            )
            if not data:
                return None
            return {
                "state": data.get("state", UNKNOWN),
                "last_checked": data.get("last_checked"),
                "last_success": data.get("last_success"),
                "last_error": data.get("last_error") or None,
                "source": data.get("source"),
                "tool_count": int(data["tool_count"]) if data.get("tool_count") else None,
            }
        except Exception:
            return None

    def get_all_statuses(self) -> Dict[str, Dict[str, Any]]:
        """Return {provider_id: status} for every provider ever checked."""
        try:
            keys = self.cache_manager.client.keys(f"{STATUS_PREFIX}*")
            statuses = {}
            for key in keys:
                provider_id = key.replace(STATUS_PREFIX, "")
                status = self.get_status(provider_id)
                if status:
                    statuses[provider_id] = status
            return statuses
        except Exception:
            return {}

    # --- Active probing ----------------------------------------------------

    async def check_provider(
        self,
        provider: Any,
        source: str = "probe",
    ) -> Dict[str, Any]:
        """Actively probe a provider, record the result, and return it.

        The probe performs the same connection handshake discovery uses
        (MCP initialize for streamable-http/stdio, agent-card fetch for
        A2A), so a successful probe means the discovery pipeline can
        reach the provider. stdio probes spawn a subprocess and are
        intended for on-demand checks only.
        """
        result = await self.probe_provider(provider)
        self.record_status(
            getattr(provider, "id", "unknown"),
            result["state"],
            error=result.get("error"),
            source=source,
        )
        return result

    async def probe_provider(self, provider: Any) -> Dict[str, Any]:
        """Probe a provider without recording the result."""
        timeout_s = _probe_timeout_seconds(provider)
        state, error = UNKNOWN, None
        try:
            await asyncio.wait_for(_probe_transport(provider), timeout=timeout_s)
            state, error = HEALTHY, None
        except asyncio.TimeoutError:
            state, error = UNREACHABLE, f"probe timed out after {timeout_s:.0f}s"
        except Exception as exc:
            if _exception_contains(exc, _DegradedProbeError):
                state, error = DEGRADED, redact_url(_brief_exception(exc))
            else:
                state, error = UNREACHABLE, redact_url(_brief_exception(exc))
        return {"state": state, "error": error, "timeout_seconds": timeout_s}


def _exception_contains(exc: BaseException, cls: type) -> bool:
    """True if the exception chain (groups included) contains ``cls``."""
    if isinstance(exc, cls):
        return True
    sub_exceptions = getattr(exc, "exceptions", None)
    if sub_exceptions and any(
        _exception_contains(sub, cls) for sub in sub_exceptions
    ):
        return True
    chained = exc.__cause__ or exc.__context__
    if chained is not None and chained is not exc:
        return _exception_contains(chained, cls)
    return False


def _brief_exception(exc: BaseException) -> str:
    """One-line root-cause message for an exception (group-aware)."""
    sub_exceptions = getattr(exc, "exceptions", None)
    if sub_exceptions:
        inner = "; ".join(
            part for part in (_brief_exception(sub) for sub in sub_exceptions) if part
        )
        if inner:
            return inner
    chained = exc.__cause__ or exc.__context__
    if chained is not None and chained is not exc:
        inner = _brief_exception(chained)
        if inner and inner != str(exc):
            return inner
    return str(exc) or exc.__class__.__name__


async def _probe_transport(provider: Any) -> None:
    """Dispatch to the transport-specific probe. Raises on failure."""
    transport = getattr(provider, "transport", "")
    probe = _PROBES.get(transport)
    if probe is None:
        raise RuntimeError(f"transport '{transport}' has no health probe")
    await probe(provider)


async def _probe_streamable_http(provider: Any) -> None:
    """Probe a streamable-http provider with an MCP initialize handshake."""
    from mcp import ClientSession
    from mcp.client.streamable_http import (
        create_mcp_http_client,
        streamable_http_client,
    )

    url = provider.endpoint
    http_client = None
    secret = resolve_secret(provider.auth.secret_env, provider.id)
    if provider.auth.type == "api_key" and secret:
        url = append_api_key(url, secret, provider.auth.key_param)
    elif provider.auth.type == "bearer" and secret:
        http_client = create_mcp_http_client(
            headers={"Authorization": f"Bearer {secret}"}
        )

    async with streamable_http_client(url, http_client=http_client) as streams:
        read, write = streams[:2]
        async with ClientSession(read, write) as session:
            await session.initialize()


async def _probe_stdio(provider: Any) -> None:
    """Probe a stdio provider by spawning it and completing a handshake."""
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    if not provider.command:
        raise RuntimeError("stdio provider has no command configured")
    command = provider.command
    if command == "python":
        command = sys.executable
    server_params = StdioServerParameters(
        command=command,
        args=list(provider.args or []),
        env=build_stdio_env(
            provider.auth.type,
            provider.auth.secret_env,
            provider.auth.username,
            provider.id,
        ) or None,
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()


async def _probe_a2a(provider: Any) -> None:
    """Probe an A2A agent by fetching its agent card."""
    import httpx

    base_url = (provider.endpoint or "").rstrip("/")
    if not base_url:
        raise RuntimeError("a2a provider has no endpoint configured")
    card_url = f"{base_url}/.well-known/agent-card.json"

    headers = {"A2A-Version": "1.0"}
    secret = resolve_secret(provider.auth.secret_env, provider.id)
    if provider.auth.type == "bearer" and secret:
        headers["Authorization"] = f"Bearer {secret}"

    async with httpx.AsyncClient(timeout=_probe_timeout_seconds(provider)) as client:
        response = await client.get(card_url, headers=headers)

    if response.status_code in (401, 403):
        raise _DegradedProbeError(
            f"agent card returned HTTP {response.status_code} (auth failed)"
        )
    if response.status_code != 200:
        raise RuntimeError(f"agent card returned HTTP {response.status_code}")


async def _probe_http(provider: Any) -> None:
    """Probe a legacy http provider with a tools/list JSON-RPC call."""
    import httpx

    if not provider.endpoint:
        raise RuntimeError("http provider has no endpoint configured")
    payload = {"jsonrpc": "2.0", "method": "tools/list", "id": 1}
    async with httpx.AsyncClient(timeout=_probe_timeout_seconds(provider)) as client:
        response = await client.post(provider.endpoint, json=payload)
    if response.status_code != 200:
        raise RuntimeError(f"HTTP probe returned status {response.status_code}")


_PROBES = {
    "streamable-http": _probe_streamable_http,
    "stdio": _probe_stdio,
    "a2a": _probe_a2a,
    "http": _probe_http,
}


# --- Module-level convenience ---------------------------------------------


def record_provider_status(
    provider_id: str,
    state: str,
    error: Optional[str] = None,
    source: str = "discovery",
    tool_count: Optional[int] = None,
    cache_manager: Optional[ToolCacheManager] = None,
) -> None:
    """Record provider status without constructing a service manually."""
    ProviderHealthService(cache_manager).record_status(
        provider_id, state, error=error, source=source, tool_count=tool_count
    )


def get_all_provider_statuses(
    cache_manager: Optional[ToolCacheManager] = None,
) -> Dict[str, Dict[str, Any]]:
    """Return {provider_id: status} for every provider ever checked."""
    return ProviderHealthService(cache_manager).get_all_statuses()
