"""Transport adapter layer for axiolex_execute_tool (spec Section 10).

Each adapter's job is narrow: take the resolved runtime spec (endpoint /
command + validated arguments), make the actual call in the shape that
transport requires, and normalize the raw result/error back into the
Section 4 response contract. JSON-RPC 2.0 is the wire format for every
MCP message; the two official transports that carry it are stdio (local
subprocess providers) and Streamable HTTP (remote providers). A2A
(Agent-to-Agent) providers also use JSON-RPC 2.0 but speak a different
protocol (SendMessage / GetTask) defined by the A2A specification.

Adding a new transport later means writing a new adapter behind this
boundary — it never requires a change to the external request/response
contract or to calling clients.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from ..security import append_api_key, redact_url, resolve_secret
from .errors import ExecutionError, INTERNAL_ERROR, UPSTREAM_ERROR


# --- Exception unwrapping -------------------------------------------------

def _unwrap_exception(exc: BaseException, depth: int = 0) -> str:
    """Walk an exception chain to find the most informative root-cause message.

    ``asyncio.TaskGroup`` (Python 3.11+) wraps sub-exceptions in an
    ``ExceptionGroup``.  Calling ``str(exc)`` on the group only yields
    ``"unhandled errors in a TaskGroup (1 sub-exception)"`` — the actual
    HTTP status code or connection error is buried inside.  This helper
    recurses through ``__cause__``, ``__context__``, and the ``exceptions``
    tuple of ``BaseExceptionGroup`` to surface the real message.
    """
    if depth > 10:
        return str(exc)

    # ExceptionGroup / TaskGroup — recurse into sub-exceptions.
    sub_exceptions = getattr(exc, "exceptions", None)
    if sub_exceptions:
        parts = [_unwrap_exception(sub, depth + 1) for sub in sub_exceptions]
        return "; ".join(p for p in parts if p)

    # Standard chained exception — follow __cause__ then __context__.
    chained = exc.__cause__ or exc.__context__
    if chained is not None and chained is not exc:
        inner = _unwrap_exception(chained, depth + 1)
        if inner and inner != str(exc):
            return inner

    return str(exc) or exc.__class__.__name__


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
                f"Upstream streamable-http call failed: "
                f"{redact_url(_unwrap_exception(exc))}",
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
                f"Upstream stdio call failed: "
                f"{redact_url(_unwrap_exception(exc))}",
                retryable=True,
            )
        return _normalize_call_result(result)


# --- A2A adapter (Agent-to-Agent providers) --------------------------------

class A2AAdapter:
    """Execute a tool on a remote A2A (Agent-to-Agent) provider.

    A2A agents expose a JSON-RPC 2.0 endpoint that accepts ``SendMessage``
    requests and return a ``Task`` object with artifacts. Unlike MCP,
    there is no session handshake — each call is stateless. The
    ``A2A-Version: 1.0`` header is required.

    Arguments are mapped to the A2A message parts:
    - If the tool schema has a single ``prompt`` field, its value is sent
      as a text part (natural-language question to the agent).
    - Otherwise, the arguments dict is JSON-encoded as a text part.
    """

    async def execute(
        self,
        runtime: Dict[str, Any],
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        import asyncio
        import json
        import uuid

        import httpx

        url = runtime.get("endpoint")
        if not url:
            raise ExecutionError(
                INTERNAL_ERROR,
                f"Tool '{runtime.get('tool_name')}' has no a2a endpoint",
                retryable=False,
            )

        # Build the A2A SendMessage request.
        # If the tool accepts a single "prompt" field, send it as text.
        # Otherwise, JSON-encode the arguments.
        if len(arguments) == 1 and "prompt" in arguments:
            text = str(arguments["prompt"])
        else:
            text = json.dumps(arguments)

        message_id = str(uuid.uuid4())
        payload = {
            "jsonrpc": "2.0",
            "method": "SendMessage",
            "id": 1,
            "params": {
                "message": {
                    "message_id": message_id,
                    "role": "ROLE_USER",
                    "parts": [{"text": text}],
                }
            },
        }

        headers = {
            "Content-Type": "application/json",
            "A2A-Version": "1.0",
        }

        # Resolve auth (bearer token in Authorization header).
        auth = runtime.get("auth") or {}
        provider_id = runtime.get("provider")
        secret = resolve_secret(auth.get("secret_env"), provider_id)
        if auth.get("type") == "bearer" and secret:
            headers["Authorization"] = f"Bearer {secret}"
        elif auth.get("type") == "api_key" and secret:
            url = append_api_key(url, secret, auth.get("key_param") or "api_key")

        timeout = runtime.get("timeout_ms")
        timeout_s = timeout / 1000.0 if timeout else 30.0

        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                response = await client.post(url, json=payload, headers=headers)
                body = response.json()

            # Check for JSON-RPC error.
            if "error" in body:
                err = body["error"]
                raise ExecutionError(
                    UPSTREAM_ERROR,
                    f"A2A agent error: {err.get('message', str(err))}",
                    retryable=True,
                )

            result = body.get("result", {})
            task = result.get("task", result)

            # Extract text from artifacts.
            content: List[Dict[str, Any]] = []
            for artifact in task.get("artifacts", []):
                for part in artifact.get("parts", []):
                    if "text" in part:
                        content.append({"type": "text", "text": part["text"]})

            is_error = task.get("status", {}).get("state", "").startswith("TASK_STATE_FAILED")

            if not content and not is_error:
                content.append({
                    "type": "text",
                    "text": json.dumps(task, indent=2),
                })

            return {"content": content, "is_error": is_error}

        except ExecutionError:
            raise
        except Exception as exc:
            raise ExecutionError(
                UPSTREAM_ERROR,
                f"Upstream a2a call failed: {redact_url(_unwrap_exception(exc))}",
                retryable=True,
            )


# --- Registry / dispatch --------------------------------------------------

_ADAPTERS: Dict[str, TransportAdapter] = {
    "streamable-http": StreamableHttpAdapter(),
    "stdio": StdioAdapter(),
    "a2a": A2AAdapter(),
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
