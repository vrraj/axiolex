"""Inbound ASGI authentication for Axiolex HTTP applications."""

from __future__ import annotations

import secrets
from typing import Any, Awaitable, Callable

from .core.config import ServerConfig


ASGIApp = Callable[[dict[str, Any], Callable[[], Awaitable[dict[str, Any]]], Callable[[dict[str, Any]], Awaitable[None]]], Awaitable[None]]


class InboundAuthMiddleware:
    """Authenticate every protected HTTP request before routing.

    The middleware is intentionally a pure ASGI wrapper.  Starlette applies it
    outside mounted applications, which keeps the FastMCP Streamable HTTP app
    and its streaming requests inside the same boundary as REST routes.
    """

    def __init__(self, app: ASGIApp, *, server: ServerConfig) -> None:
        self.app = app
        self.auth_mode = server.auth_mode
        self._expected_token = (server.api_bearer_token or "").encode("ascii")

    async def __call__(self, scope: dict[str, Any], receive, send) -> None:
        if scope["type"] != "http" or self._is_anonymous_liveness(scope):
            await self.app(scope, receive, send)
            return

        if self.auth_mode != "static":
            # `off` is startup-restricted to loopback. `external` is only
            # permitted with a declared trusted gateway boundary; it must not
            # treat any client-supplied identity header as authentication.
            await self.app(scope, receive, send)
            return

        presented = self._bearer_token(scope)
        if presented is None or not secrets.compare_digest(presented, self._expected_token):
            await self._unauthorized(send)
            return

        # No route, handler, mounted MCP app, or downstream provider adapter
        # needs the inbound credential after it has been verified. Removing it
        # prevents accidental forwarding or logging by application code.
        protected_scope = dict(scope)
        protected_scope["headers"] = [
            (name, value)
            for name, value in scope.get("headers", [])
            if name.lower() != b"authorization"
        ]
        await self.app(protected_scope, receive, send)

    @staticmethod
    def _is_anonymous_liveness(scope: dict[str, Any]) -> bool:
        return scope.get("path") == "/health/live" and scope.get("method") == "GET"

    @staticmethod
    def _bearer_token(scope: dict[str, Any]) -> bytes | None:
        headers = [
            value
            for name, value in scope.get("headers", [])
            if name.lower() == b"authorization"
        ]
        if len(headers) != 1:
            return None
        value = headers[0]
        if not value.startswith(b"Bearer "):
            return None
        token = value[len(b"Bearer "):]
        if not token or b" " in token or b"\t" in token:
            return None
        return token

    @staticmethod
    async def _unauthorized(send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"www-authenticate", b"Bearer"),
                    (b"content-length", b"0"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": b""})
