"""Inbound ASGI authentication for Axiolex HTTP applications."""

from __future__ import annotations

import json
import secrets
import time
from http.cookies import CookieError, SimpleCookie
from typing import Any, Awaitable, Callable

from .core.config import ServerConfig


ASGIApp = Callable[[dict[str, Any], Callable[[], Awaitable[dict[str, Any]]], Callable[[dict[str, Any]], Awaitable[None]]], Awaitable[None]]


class OperatorSessionStore:
    """In-memory opaque sessions for the static-token local operator UI."""

    def __init__(self, *, ttl_seconds: int = 3600, max_attempts: int = 5, window_seconds: int = 60) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._sessions: dict[str, tuple[float, str]] = {}
        self._attempts: dict[str, list[float]] = {}

    def create(self) -> tuple[str, str]:
        self._purge()
        session_id = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        self._sessions[session_id] = (time.monotonic() + self.ttl_seconds, csrf_token)
        return session_id, csrf_token

    def csrf_for(self, session_id: str | None) -> str | None:
        self._purge()
        if not session_id:
            return None
        session = self._sessions.get(session_id)
        return session[1] if session else None

    def revoke(self, session_id: str | None) -> None:
        if session_id:
            self._sessions.pop(session_id, None)

    def login_allowed(self, client_id: str) -> bool:
        self._purge()
        return len(self._attempts.get(client_id, [])) < self.max_attempts

    def failed_login(self, client_id: str) -> None:
        self._purge()
        self._attempts.setdefault(client_id, []).append(time.monotonic())

    def successful_login(self, client_id: str) -> None:
        self._attempts.pop(client_id, None)

    def _purge(self) -> None:
        now = time.monotonic()
        self._sessions = {
            key: session for key, session in self._sessions.items() if session[0] > now
        }
        self._attempts = {
            key: recent
            for key, attempts in self._attempts.items()
            if (recent := [attempt for attempt in attempts if now - attempt < self.window_seconds])
        }


class InboundAuthMiddleware:
    """Authenticate every protected HTTP request before routing.

    The middleware is intentionally a pure ASGI wrapper.  Starlette applies it
    outside mounted applications, which keeps the FastMCP Streamable HTTP app
    and its streaming requests inside the same boundary as REST routes.
    """

    def __init__(self, app: ASGIApp, *, server: ServerConfig, sessions: OperatorSessionStore | None = None) -> None:
        self.app = app
        self.auth_mode = server.auth_mode
        self.protocol = server.protocol
        self._expected_token = (server.api_bearer_token or "").encode("ascii")
        self.sessions = sessions

    async def __call__(self, scope: dict[str, Any], receive, send) -> None:
        if scope["type"] != "http" or self._is_anonymous(scope):
            await self.app(scope, receive, send)
            return

        if self.auth_mode != "static":
            # `off` is startup-restricted to loopback. `external` is only
            # permitted with a declared trusted gateway boundary; it must not
            # treat any client-supplied identity header as authentication.
            await self.app(scope, receive, send)
            return

        presented = self._bearer_token(scope)
        if presented is not None and secrets.compare_digest(presented, self._expected_token):
            await self.app(self._without_authorization(scope), receive, send)
            return

        if self._valid_operator_session(scope):
            await self.app(scope, receive, send)
            return

        if presented is None or not secrets.compare_digest(presented, self._expected_token):
            if self._is_browser_navigation(scope):
                await self._redirect_to_login(send)
            else:
                await self._unauthorized(send, is_mcp=self._is_mcp_path(scope))
            return

    @staticmethod
    def _is_anonymous(scope: dict[str, Any]) -> bool:
        return (scope.get("path") == "/health/live" and scope.get("method") == "GET") or (
            scope.get("path") == "/auth/login" and scope.get("method") == "POST"
        ) or (scope.get("path") == "/login" and scope.get("method") == "GET")

    @staticmethod
    def _is_mcp_path(scope: dict[str, Any]) -> bool:
        path = scope.get("path", "")
        return path == "/mcp" or path.startswith("/mcp/")

    @classmethod
    def _is_browser_navigation(cls, scope: dict[str, Any]) -> bool:
        """Return whether this is a top-level browser document request.

        API clients and browser ``fetch`` calls must retain a 401 response so
        they can handle authentication programmatically.  A browser navigating
        to a UI or documentation page, however, should be sent to the operator
        sign-in screen.  MCP never redirects because its clients expect an HTTP
        authentication failure, not HTML.
        """
        if scope.get("method") not in {"GET", "HEAD"} or cls._is_mcp_path(scope):
            return False
        if cls._header(scope, b"sec-fetch-dest") == "document":
            return True
        accept = cls._header(scope, b"accept") or ""
        return "text/html" in accept.lower()

    @staticmethod
    def _without_authorization(scope: dict[str, Any]) -> dict[str, Any]:
        protected_scope = dict(scope)
        protected_scope["headers"] = [
            (name, value)
            for name, value in scope.get("headers", [])
            if name.lower() != b"authorization"
        ]
        return protected_scope

    def _valid_operator_session(self, scope: dict[str, Any]) -> bool:
        # Only the MCP endpoint itself is bearer-token-only.  Management
        # routes such as ``/mcp-providers`` use the operator session and must
        # not be caught by the similarly named MCP path prefix.
        path = scope.get("path", "")
        if self.sessions is None or path == "/mcp" or path.startswith("/mcp/"):
            return False
        session_id = self._cookie(scope, "axiolex_session")
        csrf_token = self.sessions.csrf_for(session_id)
        if csrf_token is None:
            return False
        if scope.get("method") in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = self._header(scope, b"origin")
            host = self._header(scope, b"host")
            csrf = self._header(scope, b"x-csrf-token")
            if not origin or not host or origin != f"{self.protocol}://{host}":
                return False
            if not csrf or not secrets.compare_digest(csrf, csrf_token):
                return False
        return True

    @staticmethod
    def _header(scope: dict[str, Any], expected: bytes) -> str | None:
        values = [value for name, value in scope.get("headers", []) if name.lower() == expected]
        if len(values) != 1:
            return None
        try:
            return values[0].decode("ascii")
        except UnicodeDecodeError:
            return None

    @staticmethod
    def _cookie(scope: dict[str, Any], name: str) -> str | None:
        raw = InboundAuthMiddleware._header(scope, b"cookie")
        if not raw:
            return None
        cookie = SimpleCookie()
        try:
            cookie.load(raw)
        except (CookieError, ValueError):
            return None
        morsel = cookie.get(name)
        return morsel.value if morsel else None

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
    async def _redirect_to_login(send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 307,
                "headers": [
                    (b"location", b"/login"),
                    (b"cache-control", b"no-store"),
                    (b"content-length", b"0"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": b""})

    @staticmethod
    async def _unauthorized(send, *, is_mcp: bool) -> None:
        detail = (
            "Access denied: missing or invalid bearer token."
            if is_mcp
            else "Authentication required: provide a valid bearer token."
        )
        body = json.dumps({"detail": detail}, separators=(",", ":")).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"www-authenticate", b"Bearer"),
                    (b"content-type", b"application/json"),
                    (b"cache-control", b"no-store"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
