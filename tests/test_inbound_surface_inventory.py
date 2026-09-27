"""Characterization coverage for Axiolex's inbound HTTP surfaces.

These tests intentionally describe the pre-security baseline found during Task
1. Later security tasks should update the tests only when they deliberately
replace the documented behavior (for example, splitting detailed status from
anonymous liveness).
"""

from contextlib import asynccontextmanager

import pytest
from starlette.routing import Mount

from axiolex.api import routes
from axiolex.api.routes import create_app
from axiolex.core.config import Config


class _Retriever:
    def get_document_count(self):
        return 7

    def get_hybrid_status(self):
        return {"enabled": False, "model": "baseline-model"}


class _SessionManager:
    @asynccontextmanager
    async def run(self):
        yield


class _McpServer:
    session_manager = _SessionManager()

    def streamable_http_app(self):
        async def app(scope, receive, send):
            return None

        return app


def _route_methods(app):
    methods = {}
    for route in app.routes:
        if hasattr(route, "methods"):
            methods.setdefault(route.path, set()).update(route.methods)
    return methods


def test_server_default_is_loopback_after_transport_hardening():
    """Keep the Task 2 loopback-default security invariant in place."""
    assert Config().server.host == "127.0.0.1"


def test_rest_and_operator_surfaces_are_present_before_security_is_added():
    """Inventory the REST, UI, docs, and status paths that need one boundary."""
    app = create_app(Config())
    route_methods = _route_methods(app)

    assert route_methods["/"] == {"GET"}
    assert route_methods["/status"] == {"GET"}
    assert route_methods["/discover"] == {"POST"}
    assert route_methods["/execute"] == {"POST"}
    assert route_methods["/namespaces"] == {"GET", "POST"}
    assert route_methods["/capabilities"] == {"GET"}
    assert route_methods["/mcp-providers"] == {"GET", "POST"}
    assert route_methods["/mcp-providers/status/check"] == {"POST"}
    assert "/openapi.json" in route_methods
    assert "/docs" in route_methods
    assert "/redoc" in route_methods
    assert any(isinstance(route, Mount) and route.path == "/static" for route in app.routes)
    assert any(isinstance(route, Mount) and route.path == "/docs" for route in app.routes)


@pytest.mark.asyncio
async def test_mcp_subapplication_is_mounted_during_application_lifespan(monkeypatch):
    """The mounted MCP app requires ASGI-level, not router-only, protection."""
    monkeypatch.setenv("AXIOLEX_CATALOG_REFRESH_INTERVAL_SECONDS", "0")
    monkeypatch.setattr(routes, "get_retriever", lambda: _Retriever())
    monkeypatch.setattr(routes, "create_mcp_server", lambda **kwargs: _McpServer())
    app = create_app(Config())

    async with app.router.lifespan_context(app):
        assert any(isinstance(route, Mount) and route.path == "/mcp" for route in app.routes)


@pytest.mark.asyncio
async def test_status_currently_contains_operational_diagnostics(monkeypatch):
    """Establish why `/status` cannot remain the anonymous liveness endpoint."""
    monkeypatch.setattr(routes, "get_retriever", lambda: _Retriever())
    monkeypatch.setattr(
        "axiolex.services.tool_discovery_service.get_default_top_k", lambda: 7
    )
    app = create_app(Config())
    status_endpoint = next(route.endpoint for route in app.routes if route.path == "/status")

    assert await status_endpoint() == {
        "status": "healthy",
        "document_count": 7,
        "retriever_initialized": True,
        "version": routes.__version__,
        "hybrid_search": {"enabled": False, "model": "baseline-model"},
        "default_top_k": 7,
    }
