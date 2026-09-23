"""Tests for provider health status tracking.

Covers the Redis status store roundtrip, probe classification
(healthy / degraded / unreachable / timeout), the three status write
hooks (discovery, execution, on-demand probe), status surfacing in
``get_all_providers``, the discovery response annotation, and the
preservation of status keys across catalog replacement.
"""

import asyncio

import pytest

import axiolex.mcp.health as health_mod
from axiolex.mcp import discovery as discovery_mod
from axiolex.mcp.execution import service as execution_service
from axiolex.mcp.execution.errors import ExecutionError, UPSTREAM_ERROR, INVALID_ARGUMENTS
from axiolex.mcp.health import (
    DEGRADED,
    HEALTHY,
    UNREACHABLE,
    UNKNOWN,
    ProviderHealthService,
    _DegradedProbeError,
)
from axiolex.mcp.discovery import MCPProviderConfig
from axiolex.services import mcp_service
from axiolex.services.tool_discovery_service import _attach_provider_status
from axiolex.core.cache import ToolCacheManager


# --- Fakes ----------------------------------------------------------------


class FakeStatusRedis:
    """In-memory stand-in for the Redis client (status hashes only)."""

    def __init__(self):
        self.store = {}
        self.broken = False

    def hset(self, key, mapping=None, **kwargs):
        if self.broken:
            raise ConnectionError("redis down")
        self.store.setdefault(key, {}).update(mapping or kwargs)

    def hgetall(self, key):
        if self.broken:
            raise ConnectionError("redis down")
        return dict(self.store.get(key, {}))

    def keys(self, pattern):
        if self.broken:
            raise ConnectionError("redis down")
        prefix = pattern.rstrip("*")
        return [key for key in self.store if key.startswith(prefix)]


class FakeStatusCacheManager:
    def __init__(self):
        self.client = FakeStatusRedis()

    def is_connected(self):
        return True


def make_provider(**overrides):
    defaults = dict(
        id="markets",
        name="Markets",
        transport="streamable-http",
        endpoint="http://localhost:9001/mcp",
    )
    defaults.update(overrides)
    return MCPProviderConfig(**defaults)


class FakeHealth:
    """Configurable stand-in for ProviderHealthService in mcp_service."""

    def __init__(self, statuses=None, probe_results=None):
        self._statuses = statuses or {}
        self._probe_results = probe_results or {}
        self.probed = []

    def get_status(self, provider_id):
        return self._statuses.get(provider_id)

    async def check_provider(self, provider, source="probe"):
        self.probed.append(provider.id)
        result = self._probe_results.get(provider.id, {"state": HEALTHY, "error": None})
        return result


# --- Status store ---------------------------------------------------------


def test_record_and_get_status_roundtrip():
    service = ProviderHealthService(cache_manager=FakeStatusCacheManager())

    service.record_status(
        "markets", HEALTHY, source="discovery", tool_count=4
    )

    status = service.get_status("markets")
    assert status["state"] == HEALTHY
    assert status["source"] == "discovery"
    assert status["tool_count"] == 4
    assert status["last_error"] is None
    assert status["last_checked"]
    assert status["last_success"] == status["last_checked"]


def test_get_status_missing_provider_returns_none():
    service = ProviderHealthService(cache_manager=FakeStatusCacheManager())
    assert service.get_status("nobody") is None


def test_record_status_swallows_redis_errors():
    cache = FakeStatusCacheManager()
    cache.client.broken = True
    service = ProviderHealthService(cache_manager=cache)

    # Must not raise despite Redis being down.
    service.record_status("markets", UNREACHABLE, error="boom")
    assert service.get_status("markets") is None


def test_get_all_statuses():
    service = ProviderHealthService(cache_manager=FakeStatusCacheManager())
    service.record_status("markets", HEALTHY)
    service.record_status("jira", UNREACHABLE, error="connection refused")

    statuses = service.get_all_statuses()
    assert set(statuses) == {"markets", "jira"}
    assert statuses["markets"]["state"] == HEALTHY
    assert statuses["jira"]["state"] == UNREACHABLE


# --- Probe classification ---------------------------------------------------


@pytest.mark.asyncio
async def test_probe_provider_success(monkeypatch):
    async def ok(provider):
        return None

    monkeypatch.setattr(health_mod, "_probe_transport", ok)
    result = await ProviderHealthService(
        cache_manager=FakeStatusCacheManager()
    ).probe_provider(make_provider())
    assert result["state"] == HEALTHY
    assert result["error"] is None


@pytest.mark.asyncio
async def test_probe_provider_unreachable(monkeypatch):
    async def broken(provider):
        raise ConnectionError("connection refused")

    monkeypatch.setattr(health_mod, "_probe_transport", broken)
    result = await ProviderHealthService(
        cache_manager=FakeStatusCacheManager()
    ).probe_provider(make_provider())
    assert result["state"] == UNREACHABLE
    assert "connection refused" in result["error"]


@pytest.mark.asyncio
async def test_probe_provider_timeout(monkeypatch):
    async def hang(provider):
        raise asyncio.TimeoutError()

    monkeypatch.setattr(health_mod, "_probe_transport", hang)
    result = await ProviderHealthService(
        cache_manager=FakeStatusCacheManager()
    ).probe_provider(make_provider())
    assert result["state"] == UNREACHABLE
    assert "timed out" in result["error"]


@pytest.mark.asyncio
async def test_probe_provider_degraded_auth(monkeypatch):
    class FakeExceptionGroup(Exception):
        # Stand-in for the builtin ExceptionGroup (Python 3.11+) so the
        # group-aware unwrapping is exercised on every supported version.
        def __init__(self, msg, excs):
            super().__init__(msg)
            self.exceptions = tuple(excs)

    async def auth_failed(provider):
        raise FakeExceptionGroup("taskgroup", [_DegradedProbeError("HTTP 401")])

    monkeypatch.setattr(health_mod, "_probe_transport", auth_failed)
    result = await ProviderHealthService(
        cache_manager=FakeStatusCacheManager()
    ).probe_provider(make_provider())
    assert result["state"] == DEGRADED
    assert "401" in result["error"]


@pytest.mark.asyncio
async def test_check_provider_records_result(monkeypatch):
    async def broken(provider):
        raise ConnectionError("connection refused")

    monkeypatch.setattr(health_mod, "_probe_transport", broken)
    cache = FakeStatusCacheManager()
    result = await ProviderHealthService(cache_manager=cache).check_provider(
        make_provider(), source="probe"
    )
    assert result["state"] == UNREACHABLE
    status = ProviderHealthService(cache_manager=cache).get_status("markets")
    assert status["state"] == UNREACHABLE
    assert status["source"] == "probe"
    assert "connection refused" in status["last_error"]


# --- Discovery hook ---------------------------------------------------------


def discovery_status_calls(monkeypatch, state_map=None, probe=None):
    """Patch discovery's health imports and return the recorded calls."""
    calls = []

    def fake_record(provider_id, state, error=None, source=None, tool_count=None):
        calls.append(
            {
                "provider_id": provider_id,
                "state": state,
                "error": error,
                "source": source,
                "tool_count": tool_count,
            }
        )

    monkeypatch.setattr(discovery_mod, "record_provider_status", fake_record)

    class FakeProbeService:
        async def probe_provider(self, config):
            return probe or {"state": HEALTHY, "error": None}

    monkeypatch.setattr(discovery_mod, "ProviderHealthService", FakeProbeService)
    return calls


@pytest.mark.asyncio
async def test_discovery_records_healthy_with_tool_count(monkeypatch):
    calls = discovery_status_calls(monkeypatch)
    discovery = discovery_mod.MCPDiscovery(providers=[], config_file=None)

    await discovery._record_discovery_status(
        make_provider(), [{"id": "markets:get_quote"}]
    )

    assert calls == [
        {
            "provider_id": "markets",
            "state": HEALTHY,
            "error": None,
            "source": "discovery",
            "tool_count": 1,
        }
    ]


@pytest.mark.asyncio
async def test_discovery_empty_and_reachable_is_degraded(monkeypatch):
    calls = discovery_status_calls(
        monkeypatch, probe={"state": HEALTHY, "error": None}
    )
    discovery = discovery_mod.MCPDiscovery(providers=[], config_file=None)

    await discovery._record_discovery_status(make_provider(), [])

    assert calls[0]["state"] == DEGRADED
    assert "no tools" in calls[0]["error"]


@pytest.mark.asyncio
async def test_discovery_empty_and_unreachable(monkeypatch):
    calls = discovery_status_calls(
        monkeypatch,
        probe={"state": UNREACHABLE, "error": "connection refused"},
    )
    discovery = discovery_mod.MCPDiscovery(providers=[], config_file=None)

    await discovery._record_discovery_status(make_provider(), [])

    assert calls[0]["state"] == UNREACHABLE
    assert "connection refused" in calls[0]["error"]


# --- Execution hook ---------------------------------------------------------


class FakeExecutionCache:
    def __init__(self, discovery, runtime):
        self._discovery = discovery
        self._runtime = runtime

    def get_discovery(self, tool_id):
        return self._discovery.get(tool_id)

    def get_runtime(self, tool_id):
        return self._runtime.get(tool_id)


class FakeFailingAdapter:
    def __init__(self, raises):
        self._raises = raises

    async def execute(self, runtime, arguments):
        raise self._raises


def wire_fake_adapter(monkeypatch, transport, adapter):
    import axiolex.mcp.execution.adapters as adapters_mod

    monkeypatch.setitem(adapters_mod._ADAPTERS, transport, adapter)


def execution_status_spy(monkeypatch):
    calls = []

    def spy(provider_id, state, error=None, source=None, tool_count=None):
        calls.append(
            {"provider_id": provider_id, "state": state, "error": error, "source": source}
        )

    monkeypatch.setattr(execution_service, "record_provider_status", spy)
    return calls


@pytest.mark.asyncio
async def test_execution_upstream_error_marks_provider_unreachable(monkeypatch):
    calls = execution_status_spy(monkeypatch)
    from axiolex.mcp.execution import ToolExecutionService

    service = ToolExecutionService(
        cache_manager=FakeExecutionCache(
            {"markets:get_quote": {"params": {}, "provider": "markets"}},
            {
                "markets:get_quote": {
                    "tool_name": "get_quote",
                    "transport": "streamable-http",
                    "provider": "markets",
                }
            },
        )
    )
    wire_fake_adapter(
        monkeypatch,
        "streamable-http",
        FakeFailingAdapter(ExecutionError(UPSTREAM_ERROR, "upstream down", retryable=True)),
    )

    response = await service.execute_tool("markets:get_quote", {})

    assert response["status"] == "error"
    assert response["error"]["code"] == UPSTREAM_ERROR
    assert calls == [
        {
            "provider_id": "markets",
            "state": UNREACHABLE,
            "error": "upstream down",
            "source": "execution",
        }
    ]


@pytest.mark.asyncio
async def test_execution_validation_error_leaves_status_alone(monkeypatch):
    calls = execution_status_spy(monkeypatch)
    from axiolex.mcp.execution import ToolExecutionService

    service = ToolExecutionService(
        cache_manager=FakeExecutionCache(
            {
                "markets:get_quote": {
                    "params": {"symbol": {"type": "string"}},
                    "provider": "markets",
                }
            },
            {
                "markets:get_quote": {
                    "tool_name": "get_quote",
                    "transport": "streamable-http",
                    "provider": "markets",
                }
            },
        )
    )

    # Invalid arguments (not a string) — a caller error, not a provider failure.
    response = await service.execute_tool(
        "markets:get_quote", {"symbol": {"bad": "type"}}
    )

    assert response["error"]["code"] == INVALID_ARGUMENTS
    assert calls == []


# --- Discovery response annotation ------------------------------------------


def test_attach_provider_status(monkeypatch):
    statuses = {
        "markets": {
            "state": UNREACHABLE,
            "last_checked": "2026-09-23T10:00:00+00:00",
            "last_error": "connection refused",
        }
    }

    class FakeHealthService:
        def __init__(self, cache_manager=None):
            pass

        def get_all_statuses(self):
            return statuses

    monkeypatch.setattr(health_mod, "ProviderHealthService", FakeHealthService)

    tools = [
        {"name": "get_quote", "provider": "markets"},
        {"name": "local_tool", "provider": "yaml"},
    ]
    result = _attach_provider_status(tools)

    assert result[0]["provider_status"]["state"] == UNREACHABLE
    assert result[0]["provider_status"]["last_error"] == "connection refused"
    assert "provider_status" not in result[1]


def test_attach_provider_status_tolerates_redis_outage(monkeypatch):
    class BrokenHealthService:
        def __init__(self, cache_manager=None):
            pass

        def get_all_statuses(self):
            raise ConnectionError("redis down")

    monkeypatch.setattr(health_mod, "ProviderHealthService", BrokenHealthService)

    tools = [{"name": "get_quote", "provider": "markets"}]
    result = _attach_provider_status(tools)
    assert "provider_status" not in result[0]


# --- Provider listing and check-all ------------------------------------------


class FakeProviderDiscovery:
    def __init__(self):
        self.providers = [
            make_provider(),
            make_provider(id="jira", name="Jira", transport="stdio", command="python"),
            make_provider(id="ghost", name="Ghost", enabled=False),
        ]

    def close(self):
        pass


@pytest.mark.asyncio
async def test_get_all_providers_includes_status(monkeypatch):
    health = FakeHealth(
        statuses={
            "markets": {
                "state": HEALTHY,
                "last_checked": "2026-09-23T10:00:00+00:00",
                "last_success": "2026-09-23T10:00:00+00:00",
                "last_error": None,
                "source": "discovery",
            }
        }
    )
    monkeypatch.setattr(mcp_service, "MCPDiscovery", FakeProviderDiscovery)
    monkeypatch.setattr(mcp_service, "ProviderHealthService", lambda: health)
    monkeypatch.setattr(
        "axiolex.core.cache.get_cache_manager",
        lambda: FakeStatusCacheManager(),
    )

    result = mcp_service.get_all_providers()

    by_id = {p["id"]: p for p in result["providers"]}
    assert by_id["markets"]["status"]["state"] == HEALTHY
    assert by_id["markets"]["status"]["source"] == "discovery"
    # Never-checked providers surface as unknown.
    assert by_id["jira"]["status"]["state"] == UNKNOWN
    # Disabled providers surface as disabled regardless of stored status.
    assert by_id["ghost"]["status"]["state"] == "disabled"


@pytest.mark.asyncio
async def test_check_providers_probes_enabled_subset(monkeypatch):
    health = FakeHealth()
    monkeypatch.setattr(mcp_service, "MCPDiscovery", FakeProviderDiscovery)
    monkeypatch.setattr(mcp_service, "ProviderHealthService", lambda: health)

    # Subset check (per-card Check button).
    result = await mcp_service.check_providers(["jira"])
    assert result["checked"] == 1
    assert health.probed == ["jira"]

    # Check All probes every enabled provider.
    result = await mcp_service.check_providers()
    assert result["checked"] == 2
    assert health.probed == ["jira", "markets", "jira"]


# --- Catalog replacement preserves status keys --------------------------------


class FakePipeline:
    def __init__(self):
        self.commands = []

    def delete(self, *keys):
        self.commands.append(("delete", keys))
        return self

    def hset(self, key, mapping):
        self.commands.append(("hset", key, mapping))
        return self

    def set(self, key, value):
        self.commands.append(("set", key, value))
        return self

    def execute(self):
        self.commands.append(("execute",))


class FakeRedisWithStatusKeys:
    def __init__(self):
        self.pipeline_instance = FakePipeline()

    def keys(self, pattern):
        return [
            "axiolex:idx:tool:old",
            "axiolex:run:tool:old",
            "axiolex:status:provider:markets",
            "axiolex:status:provider:jira",
        ]

    def pipeline(self, transaction):
        return self.pipeline_instance


def test_replace_all_tools_preserves_status_keys():
    manager = ToolCacheManager()
    manager._client = FakeRedisWithStatusKeys()

    manager.replace_all_tools(
        [{
            "id": "quote",
            "title": "Quote",
            "description": "Get quote.",
            "tool_name": "get_quote",
            "params": {},
            "provider": "markets",
            "source": "mcp-discovery",
        }],
        [{"id": "quote", "runtime": {"tool_name": "get_quote"}}],
    )

    deletes = [
        cmd[1]
        for cmd in manager._client.pipeline_instance.commands
        if cmd[0] == "delete"
    ]
    deleted = set().union(*deletes)
    assert "axiolex:status:provider:markets" not in deleted
    assert "axiolex:status:provider:jira" not in deleted
    assert "axiolex:idx:tool:old" in deleted
