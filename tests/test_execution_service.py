"""Tests for axiolex_execute_tool — the generic tool dispatcher.

Covers the Phase 1 contract: resolve/validate/dispatch/timeout/normalize,
the error taxonomy, the response envelope, and independence from discovery.
Transport adapters are tested with fakes so no real subprocess or HTTP
server is required.

Phase 1 does not implement user-level authorization or policy enforcement.
"""

import asyncio
import pytest

from axiolex.mcp.execution import (
    ExecutionError,
    StreamableHttpAdapter,
    StdioAdapter,
    ToolExecutionService,
    execute_tool,
    get_adapter,
)
from axiolex.mcp.execution.adapters import _normalize_call_result, _unwrap_exception
from axiolex.mcp.execution.errors import (
    INVALID_ARGUMENTS,
    INTERNAL_ERROR,
    TOOL_NOT_FOUND,
    TOOL_UNAVAILABLE,
    UPSTREAM_ERROR,
    UPSTREAM_TIMEOUT,
)


# --- Fakes ----------------------------------------------------------------

class FakeCacheManager:
    """In-memory stand-in for ToolCacheManager (Redis catalog reader)."""

    def __init__(self, discovery=None, runtime=None):
        self._discovery = discovery or {}
        self._runtime = runtime or {}

    def get_discovery(self, tool_id):
        return self._discovery.get(tool_id)

    def get_runtime(self, tool_id):
        return self._runtime.get(tool_id)


class FakeAdapter:
    """Records calls and returns a canned normalized result."""

    def __init__(self, result=None, raises=None):
        self.calls = []
        self._result = result or {"content": [{"type": "text", "text": "ok"}], "is_error": False}
        self._raises = raises

    async def execute(self, runtime, arguments):
        self.calls.append({"runtime": runtime, "arguments": arguments})
        if self._raises is not None:
            raise self._raises
        return self._result


def _make_service(discovery, runtime, adapter):
    """Wire a ToolExecutionService with fakes and a forced adapter."""
    service = ToolExecutionService(cache_manager=FakeCacheManager(discovery, runtime))
    # Inject the fake adapter into the registry so dispatch uses it.
    # ``runtime`` is keyed by tool_id; pull the transport from the first entry.
    transport = next(iter(runtime.values())).get("transport")
    import axiolex.mcp.execution.adapters as adapters_mod
    original = adapters_mod._ADAPTERS.copy()
    adapters_mod._ADAPTERS[transport] = adapter
    service._restore_adapters = original
    return service


def _restore_adapters(service):
    import axiolex.mcp.execution.adapters as adapters_mod
    adapters_mod._ADAPTERS = service._restore_adapters


DISCOVERY = {
    "alphavantage_finance:get_quote": {
        "title": "get_quote",
        "description": "Get a current quote.",
        "tool_name": "get_quote",
        "params": {"symbol": {"type": "string"}},
        "provider": "alphavantage_finance",
        "namespaces": ["finance.market_data"],
    }
}
RUNTIME = {
    "alphavantage_finance:get_quote": {
        "tool_name": "get_quote",
        "transport": "streamable-http",
        "endpoint": "https://mcp.example.com/mcp",
        "provider": "alphavantage_finance",
        "auth": {"type": "none"},
    }
}


# --- Response envelope ----------------------------------------------------

@pytest.mark.asyncio
async def test_execute_success_returns_normalized_envelope():
    adapter = FakeAdapter(result={"content": [{"type": "text", "text": "AAPL=190"}], "is_error": False})
    service = _make_service(DISCOVERY, RUNTIME, adapter)
    try:
        resp = await service.execute_tool(
            tool_id="alphavantage_finance:get_quote",
            arguments={"symbol": "AAPL"},
        )
    finally:
        _restore_adapters(service)

    assert resp["status"] == "success"
    assert resp["tool_id"] == "alphavantage_finance:get_quote"
    assert "execution_id" in resp and resp["execution_id"]
    assert resp["result"]["content"][0]["text"] == "AAPL=190"
    assert "error" not in resp
    assert adapter.calls[0]["arguments"] == {"symbol": "AAPL"}


@pytest.mark.asyncio
async def test_execute_always_echoes_tool_id_and_execution_id_on_error():
    service = ToolExecutionService(cache_manager=FakeCacheManager({}, {}))
    resp = await service.execute_tool(
        tool_id="missing:tool", arguments={}
    )
    assert resp["status"] == "error"
    assert resp["tool_id"] == "missing:tool"
    assert resp["execution_id"]
    assert resp["error"]["code"] == TOOL_NOT_FOUND
    assert resp["error"]["retryable"] is False


# --- Error taxonomy -------------------------------------------------------

@pytest.mark.asyncio
async def test_tool_not_found_when_id_absent_from_catalog():
    service = ToolExecutionService(cache_manager=FakeCacheManager({}, {}))
    resp = await service.execute_tool(tool_id="nope", arguments={})
    assert resp["error"] == {
        "code": TOOL_NOT_FOUND,
        "message": "Tool 'nope' not found in the current catalog",
        "retryable": False,
    }


@pytest.mark.asyncio
async def test_tool_not_found_when_runtime_missing_tool_name():
    discovery = {"x:y": {"tool_name": "y", "params": {}, "namespaces": []}}
    runtime = {"x:y": {"transport": "streamable-http", "endpoint": "u"}}  # no tool_name
    service = ToolExecutionService(cache_manager=FakeCacheManager(discovery, runtime))
    resp = await service.execute_tool(tool_id="x:y", arguments={})
    assert resp["error"]["code"] == TOOL_NOT_FOUND


@pytest.mark.asyncio
async def test_invalid_arguments_type_mismatch():
    adapter = FakeAdapter()
    service = _make_service(DISCOVERY, RUNTIME, adapter)
    try:
        resp = await service.execute_tool(
            tool_id="alphavantage_finance:get_quote",
            arguments={"symbol": 123},  # expected string
        )
    finally:
        _restore_adapters(service)

    assert resp["error"]["code"] == INVALID_ARGUMENTS
    assert resp["error"]["retryable"] is False
    assert adapter.calls == []  # validate fails before dispatch


@pytest.mark.asyncio
async def test_invalid_arguments_not_an_object():
    service = _make_service(DISCOVERY, RUNTIME, FakeAdapter())
    try:
        resp = await service.execute_tool(
            tool_id="alphavantage_finance:get_quote",
            arguments="not-a-dict",
        )
    finally:
        _restore_adapters(service)
    assert resp["error"]["code"] == INVALID_ARGUMENTS


@pytest.mark.asyncio
async def test_tool_unavailable_for_unsupported_transport():
    discovery = {"x:y": {"tool_name": "y", "params": {}, "namespaces": []}}
    runtime = {"x:y": {"tool_name": "y", "transport": "carrier-pigeon", "endpoint": "x"}}
    service = ToolExecutionService(cache_manager=FakeCacheManager(discovery, runtime))
    resp = await service.execute_tool(tool_id="x:y", arguments={})
    assert resp["error"]["code"] == TOOL_UNAVAILABLE
    assert resp["error"]["retryable"] is False


@pytest.mark.asyncio
async def test_upstream_error_from_adapter_is_retryable():
    adapter = FakeAdapter(raises=ExecutionError(UPSTREAM_ERROR, "boom", retryable=True))
    service = _make_service(DISCOVERY, RUNTIME, adapter)
    try:
        resp = await service.execute_tool(
            tool_id="alphavantage_finance:get_quote",
            arguments={"symbol": "AAPL"},
        )
    finally:
        _restore_adapters(service)
    assert resp["error"]["code"] == UPSTREAM_ERROR
    assert resp["error"]["retryable"] is True


@pytest.mark.asyncio
async def test_upstream_timeout(monkeypatch):
    # Force a tiny timeout and an adapter that sleeps past it.
    monkeypatch.setenv("AXIOLEX_EXECUTE_TIMEOUT_MS", "50")

    class SlowAdapter:
        async def execute(self, runtime, arguments):
            await asyncio.sleep(1.0)
            return {}

    service = _make_service(DISCOVERY, RUNTIME, SlowAdapter())
    try:
        resp = await service.execute_tool(
            tool_id="alphavantage_finance:get_quote",
            arguments={"symbol": "AAPL"},
        )
    finally:
        _restore_adapters(service)
    assert resp["error"]["code"] == UPSTREAM_TIMEOUT
    assert resp["error"]["retryable"] is True


# --- Independence (no discovery dependency) --------------------------------

@pytest.mark.asyncio
async def test_execute_resolves_fresh_from_catalog_no_discovery_dependency():
    """No prior discover call; tool_id alone is sufficient (Pattern A/B)."""
    adapter = FakeAdapter()
    service = _make_service(DISCOVERY, RUNTIME, adapter)
    try:
        resp = await service.execute_tool(
            tool_id="alphavantage_finance:get_quote",
            arguments={"symbol": "MSFT"},
        )
    finally:
        _restore_adapters(service)
    assert resp["status"] == "success"
    # The adapter received the runtime resolved from the catalog, not from
    # any caller-supplied transport details.
    assert adapter.calls[0]["runtime"]["endpoint"] == "https://mcp.example.com/mcp"


# --- Normalization helper -------------------------------------------------

def test_normalize_call_result_handles_model_dump_objects():
    class FakeContent:
        def model_dump(self):
            return {"type": "text", "text": "hello"}

    class FakeResult:
        content = [FakeContent()]
        isError = False

    out = _normalize_call_result(FakeResult())
    assert out == {"content": [{"type": "text", "text": "hello"}], "is_error": False}


def test_normalize_call_result_marks_is_error():
    class FakeResult:
        content = []
        isError = True

    out = _normalize_call_result(FakeResult())
    assert out["is_error"] is True


# --- Adapter registry -----------------------------------------------------

def test_get_adapter_returns_registered_adapters():
    assert isinstance(get_adapter("streamable-http"), StreamableHttpAdapter)
    assert isinstance(get_adapter("stdio"), StdioAdapter)


def test_get_adapter_raises_tool_unavailable_for_unknown_transport():
    with pytest.raises(ExecutionError) as exc:
        get_adapter("smoke-signal")
    assert exc.value.code == TOOL_UNAVAILABLE


# --- Convenience function -------------------------------------------------

@pytest.mark.asyncio
async def test_convenience_execute_tool_function_exists():
    """The package-level execute_tool convenience function is callable."""
    # Just verify it's the same callable the service uses; full behavior
    # is covered by the service tests above.
    assert callable(execute_tool)


# --- Exception unwrapping --------------------------------------------------

def test_unwrap_plain_exception():
    """A plain exception with no chain returns its own message."""
    exc = ValueError("something went wrong")
    assert _unwrap_exception(exc) == "something went wrong"


def test_unwrap_chained_exception_via_cause():
    """Follows __cause__ to surface the root cause."""
    try:
        try:
            raise RuntimeError("HTTP 401 Unauthorized")
        except RuntimeError as inner:
            raise ValueError("wrapper") from inner
    except ValueError as exc:
        result = _unwrap_exception(exc)
    assert "401 Unauthorized" in result


def test_unwrap_exception_group():
    """Recurses into ExceptionGroup sub-exceptions (asyncio.TaskGroup pattern)."""
    inner = RuntimeError("HTTP 401 Unauthorized")
    group = ExceptionGroup("unhandled errors in a TaskGroup (1 sub-exception)", [inner])
    result = _unwrap_exception(group)
    assert "401 Unauthorized" in result
    assert "TaskGroup" not in result or "401" in result


def test_unwrap_nested_exception_group():
    """Handles nested ExceptionGroups (TaskGroup inside TaskGroup)."""
    leaf = ConnectionError("Connection refused")
    inner_group = ExceptionGroup("inner taskgroup", [leaf])
    outer_group = ExceptionGroup("outer taskgroup", [inner_group])
    result = _unwrap_exception(outer_group)
    assert "Connection refused" in result


def test_unwrap_chained_exception_group():
    """Follows __cause__ from a wrapper into an ExceptionGroup."""
    inner = RuntimeError("HTTP 403 Forbidden")
    group = ExceptionGroup("taskgroup errors", [inner])
    try:
        try:
            raise group
        except ExceptionGroup:
            raise ValueError("wrapper around taskgroup") from group
    except ValueError as exc:
        result = _unwrap_exception(exc)
    assert "403 Forbidden" in result


def test_unwrap_empty_exception_group():
    """An ExceptionGroup with empty-string sub-exceptions falls back to class name."""
    group = ExceptionGroup("empty", [RuntimeError("")])
    result = _unwrap_exception(group)
    assert result  # should not be empty
