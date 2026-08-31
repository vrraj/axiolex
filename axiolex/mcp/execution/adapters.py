"""Transport adapter layer for axiolex_execute_tool (spec Section 10).

Each adapter's job is narrow: take the resolved runtime spec (endpoint /
command + validated arguments), make the actual call in the shape that
transport requires, and normalize the raw result/error back into the
Section 4 response contract. JSON-RPC 2.0 is the wire format for every
MCP message; the two official transports that carry it are stdio (local
subprocess providers) and Streamable HTTP (remote providers).

Adding a new transport later means writing a new adapter behind this
boundary — it never requires a change to the external request/response
contract or to calling clients.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from ..security import append_api_key, redact_url, resolve_secret
from .errors import ExecutionError, INTERNAL_ERROR, UPSTREAM_ERROR


# --- Normalization --------------------------------------------------------

def _content_item_to_dict(item: Any) -> Dict[str, Any]:
    """Normalize one MCP content item (TextContent, etc.) to a plain dict."""
    if hasattr(item, "model_dump"):
        return item.model_dump()
    if isinstance(item, dict):
        return item
    # Fallback: surface the raw value as text so the caller still sees output.
    return {"type": "text", "text": str(item)}


def _normalize_call_result(result: Any) -> Dict[str, Any]:
    """Map an MCP ``CallToolResult`` into the Section 4 ``result`` object.

    Returns ``{"content": [...], "is_error": bool}``. The dispatcher wraps
    this in the full response envelope (status / execution_id / tool_id).
    """
    content: List[Dict[str, Any]] = []
    raw_content = getattr(result, "content", None)
    if raw_content is None and isinstance(result, dict):
        raw_content = result.get("content")
    if raw_content:
        content = [_content_item_to_dict(item) for item in raw_content]

    is_error = bool(getattr(result, "isError", False)) or bool(
        isinstance(result, dict) and result.get("isError")
    )
    return {"content": content, "is_error": is_error}


# --- Adapter contract -----------------------------------------------------

@runtime_checkable
class TransportAdapter(Protocol):
    """One execution contract in, transport-specific handling out."""

    async def execute(
        self,
        runtime: Dict[str, Any],
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute the tool and return the normalized result object.

        Raises ``ExecutionError`` for any upstream/dispatcher failure.
        """
        ...


# --- Auth helper (shared by MCP transports) -------------------------------

def _resolve_auth(runtime: Dict[str, Any]) -> tuple[Optional[str], Optional[Any], Optional[str]]:
    """Resolve provider auth into (url, http_client, secret) for streamable-http.

    Returns the possibly-rewritten URL, an optional custom httpx client
    carrying a bearer token header, and the resolved secret. For ``api_key``
    auth the key is appended to the URL query string (required by providers
    like Alpha Vantage); for ``bearer`` auth the token travels in the
    Authorization header, keeping it out of URLs and server logs.
    """
    auth = runtime.get("auth") or {}
    provider_id = runtime.get("provider")
    secret = resolve_secret(auth.get("secret_env"), provider_id)
    url = runtime.get("endpoint")
    http_client = None
    if auth.get("type") == "api_key" and secret:
        url = append_api_key(
            url, secret, auth.get("key_param") or "api_key"
        )
    return url, http_client, secret


# --- Streamable HTTP adapter (remote MCP providers) -----------------------

class StreamableHttpAdapter:
    """Execute a tool on a remote MCP provider over Streamable HTTP.

    JSON-RPC 2.0 messages are carried as HTTP POSTs to a single MCP
    endpoint, with replies arriving as a JSON object or a request-scoped
    SSE stream. This is the right transport for a remotely-reachable
    dispatcher serving many clients.
    """

    async def execute(
        self,
        runtime: Dict[str, Any],
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        from mcp import ClientSession
        from mcp.client.streamable_http import (
            streamable_http_client,
            create_mcp_http_client,
        )

        url, http_client, secret = _resolve_auth(runtime)
        auth = runtime.get("auth") or {}
        if auth.get("type") == "bearer" and secret:
            http_client = create_mcp_http_client(
                headers={"Authorization": f"Bearer {secret}"}
            )
        if not url:
            raise ExecutionError(
                INTERNAL_ERROR,
                f"Tool '{runtime.get('tool_name')}' has no streamable-http endpoint",
                retryable=False,
            )

        tool_name = runtime.get("tool_name", "")
        try:
            async with streamable_http_client(url, http_client=http_client) as streams:
                read, write = streams[:2]
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
        except ExecutionError:
            raise
        except Exception as exc:
            raise ExecutionError(
                UPSTREAM_ERROR,
                f"Upstream streamable-http call failed: {redact_url(str(exc))}",
                retryable=True,
            )
        return _normalize_call_result(result)


# --- stdio adapter (local subprocess MCP providers) -----------------------

class StdioAdapter:
    """Execute a tool on a locally-spawned MCP server over stdio.

    The provider is launched as a subprocess; JSON-RPC 2.0 messages travel
    as newline-delimited frames over the process's stdin/stdout. This fits
    local/subprocess providers (e.g. the bundled Fetch and text_tools
    servers) but not a remotely-reachable dispatcher.
    """

    async def execute(
        self,
        runtime: Dict[str, Any],
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        from mcp import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client

        command = runtime.get("command")
        args = runtime.get("args") or []
        if not command:
            raise ExecutionError(
                INTERNAL_ERROR,
                f"Tool '{runtime.get('tool_name')}' has no stdio command",
                retryable=False,
            )

        tool_name = runtime.get("tool_name", "")
        server_params = StdioServerParameters(command=command, args=list(args))
        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
        except ExecutionError:
            raise
        except Exception as exc:
            raise ExecutionError(
                UPSTREAM_ERROR,
                f"Upstream stdio call failed: {redact_url(str(exc))}",
                retryable=True,
            )
        return _normalize_call_result(result)


# --- Registry / dispatch --------------------------------------------------

_ADAPTERS: Dict[str, TransportAdapter] = {
    "streamable-http": StreamableHttpAdapter(),
    "stdio": StdioAdapter(),
}


def get_adapter(transport: Optional[str]) -> TransportAdapter:
    """Return the adapter for a transport, or raise TOOL_UNAVAILABLE."""
    adapter = _ADAPTERS.get(transport or "")
    if adapter is None:
        from .errors import TOOL_UNAVAILABLE
        raise ExecutionError(
            TOOL_UNAVAILABLE,
            f"Tool transport '{transport}' is not available in this dispatcher build",
            retryable=False,
        )
    return adapter
