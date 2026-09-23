"""Tests for the POST /catalog/refresh endpoint and background refresh loop."""

import asyncio
import os

import pytest

from axiolex.api.routes import _refresh_catalog, _provider_tool_counts, _catalog_refresh_loop


# ---------------------------------------------------------------------------
# _provider_tool_counts
# ---------------------------------------------------------------------------

def test_provider_tool_counts_returns_empty_when_redis_unavailable(monkeypatch):
    """When Redis is not connected, _provider_tool_counts returns {}."""

    class DisconnectedCache:
        def is_connected(self):
            return False

    monkeypatch.setattr(
        "axiolex.core.cache.get_cache_manager",
        lambda: DisconnectedCache(),
    )
    assert _provider_tool_counts() == {}


def test_provider_tool_counts_groups_by_provider(monkeypatch):
    """Tool counts are grouped by the 'provider' field."""

    class ConnectedCache:
        def is_connected(self):
            return True

        def get_all_discovery(self):
            return [
                {"provider": "alpha"},
                {"provider": "alpha"},
                {"provider": "jira"},
            ]

    monkeypatch.setattr(
        "axiolex.core.cache.get_cache_manager",
        lambda: ConnectedCache(),
    )
    counts = _provider_tool_counts()
    assert counts == {"alpha": 2, "jira": 1}


# ---------------------------------------------------------------------------
# _refresh_catalog
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_catalog_returns_diff(monkeypatch, tmp_path):
    """_refresh_catalog returns a per-provider diff when counts change."""

    tools_file = tmp_path / "tools.yaml"
    tools_file.write_text("documents: []")

    providers_file = tmp_path / "providers.yaml"
    providers_file.write_text("providers: []")

    monkeypatch.setenv("AXIOLEX_TOOLS_FILE", str(tools_file))
    monkeypatch.setenv("AXIOLEX_MCP_PROVIDERS_FILE", str(providers_file))

    # Simulate before: alpha has 3, jira has 2
    before_counts = {"alpha": 3, "jira": 2}
    # Simulate after: alpha has 5, jira has 2 (unchanged)
    after_counts = {"alpha": 5, "jira": 2}

    call_count = {"n": 0}

    def fake_counts():
        call_count["n"] += 1
        return before_counts if call_count["n"] == 1 else after_counts

    monkeypatch.setattr("axiolex.api.routes._provider_tool_counts", fake_counts)

    # Mock ToolIndexingService.refresh to avoid real Redis/discovery
    class FakeResult:
        def to_dict(self):
            return {"yaml_tools": 0, "mcp_tools": 5, "provider_count": 1, "total_tools": 5}

    class FakeService:
        def __init__(self, **kwargs):
            pass

        async def refresh(self):
            return FakeResult()

    monkeypatch.setattr("axiolex.services.indexing_service.ToolIndexingService", FakeService)

    result = await _refresh_catalog()

    assert result["success"] is True
    assert result["changed"] is True
    assert len(result["changes"]) == 1
    change = result["changes"][0]
    assert change["provider"] == "alpha"
    assert change["before"] == 3
    assert change["after"] == 5
    assert change["delta"] == 2


@pytest.mark.asyncio
async def test_refresh_catalog_no_changes(monkeypatch, tmp_path):
    """When counts don't change, changed is False and changes is empty."""

    tools_file = tmp_path / "tools.yaml"
    tools_file.write_text("documents: []")

    providers_file = tmp_path / "providers.yaml"
    providers_file.write_text("providers: []")

    monkeypatch.setenv("AXIOLEX_TOOLS_FILE", str(tools_file))
    monkeypatch.setenv("AXIOLEX_MCP_PROVIDERS_FILE", str(providers_file))

    counts = {"alpha": 3, "jira": 2}
    monkeypatch.setattr(
        "axiolex.api.routes._provider_tool_counts",
        lambda: counts,
    )

    class FakeResult:
        def to_dict(self):
            return {"yaml_tools": 0, "mcp_tools": 5, "provider_count": 2, "total_tools": 5}

    class FakeService:
        def __init__(self, **kwargs):
            pass

        async def refresh(self):
            return FakeResult()

    monkeypatch.setattr("axiolex.services.indexing_service.ToolIndexingService", FakeService)

    result = await _refresh_catalog()

    assert result["success"] is True
    assert result["changed"] is False
    assert result["changes"] == []


@pytest.mark.asyncio
async def test_refresh_catalog_raises_when_source_files_missing(monkeypatch):
    """_refresh_catalog raises ValueError when source files can't be found."""

    monkeypatch.delenv("AXIOLEX_TOOLS_FILE", raising=False)
    monkeypatch.delenv("AXIOLEX_MCP_PROVIDERS_FILE", raising=False)
    monkeypatch.setattr("axiolex.api.routes._resolve_source_dir", lambda: "")

    with pytest.raises(ValueError, match="Could not find source_files"):
        await _refresh_catalog()


# ---------------------------------------------------------------------------
# Eager index rebuild after catalog writes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_catalog_triggers_eager_rebuild(monkeypatch, tmp_path):
    """_refresh_catalog eagerly rebuilds the in-memory indexes after refresh."""

    tools_file = tmp_path / "tools.yaml"
    tools_file.write_text("documents: []")

    providers_file = tmp_path / "providers.yaml"
    providers_file.write_text("providers: []")

    monkeypatch.setenv("AXIOLEX_TOOLS_FILE", str(tools_file))
    monkeypatch.setenv("AXIOLEX_MCP_PROVIDERS_FILE", str(providers_file))

    monkeypatch.setattr(
        "axiolex.api.routes._provider_tool_counts",
        lambda: {},
    )

    class FakeResult:
        def to_dict(self):
            return {"yaml_tools": 0, "mcp_tools": 0, "provider_count": 0, "total_tools": 0}

    class FakeService:
        def __init__(self, **kwargs):
            pass

        async def refresh(self):
            return FakeResult()

    monkeypatch.setattr("axiolex.services.indexing_service.ToolIndexingService", FakeService)

    rebuild_calls = {"n": 0}

    def fake_rebuild():
        rebuild_calls["n"] += 1

    monkeypatch.setattr("axiolex.api.routes.rebuild_index_now", fake_rebuild)

    await _refresh_catalog()

    assert rebuild_calls["n"] == 1


def test_rebuild_index_now_rebuilds_all_live_instances(monkeypatch):
    """rebuild_index_now rebuilds every live global retriever instance."""

    import axiolex.core.retriever as retriever_module

    calls = []

    class FakeRetriever:
        def _load_and_index_documents(self, documents=None):
            calls.append(id(self))

    fake_admin = FakeRetriever()
    fake_discovery = FakeRetriever()

    monkeypatch.setattr(retriever_module, "_retriever_instance", fake_admin)
    monkeypatch.setattr(retriever_module, "_tool_discovery_retriever_instance", fake_discovery)

    retriever_module.rebuild_index_now()

    assert sorted(calls) == sorted([id(fake_admin), id(fake_discovery)])


def test_rebuild_index_now_noop_when_no_instances(monkeypatch):
    """rebuild_index_now is a safe no-op when no retriever is initialized."""

    import axiolex.core.retriever as retriever_module

    monkeypatch.setattr(retriever_module, "_retriever_instance", None)
    monkeypatch.setattr(retriever_module, "_tool_discovery_retriever_instance", None)

    # Must not raise
    retriever_module.rebuild_index_now()


# ---------------------------------------------------------------------------
# _catalog_refresh_loop
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_loop_calls_refresh_and_handles_errors(monkeypatch):
    """The background loop calls _refresh_catalog and survives errors."""

    call_count = {"n": 0}

    async def fake_refresh():
        call_count["n"] += 1
        if call_count["n"] == 1:
            return {"success": True, "changed": False, "changes": []}
        raise RuntimeError("Redis exploded")

    monkeypatch.setattr("axiolex.api.routes._refresh_catalog", fake_refresh)

    # Use a very short interval so the loop runs quickly in the test.
    # We need to control asyncio.sleep so the test doesn't actually wait.
    original_sleep = asyncio.sleep

    sleep_count = {"n": 0}

    async def fast_sleep(seconds):
        sleep_count["n"] += 1
        if sleep_count["n"] >= 3:
            raise asyncio.CancelledError()
        # Don't actually sleep
        return

    monkeypatch.setattr("axiolex.api.routes.asyncio.sleep", fast_sleep)

    with pytest.raises(asyncio.CancelledError):
        await _catalog_refresh_loop(1)

    # The loop should have called refresh at least once
    assert call_count["n"] >= 1
