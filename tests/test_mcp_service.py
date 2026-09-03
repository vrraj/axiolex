import pytest

from axiolex.mcp.discovery import MCPProviderConfig
from axiolex.services import mcp_service


class FakeDiscovery:
    provider = MCPProviderConfig(
        id="markets",
        name="Markets",
        transport="streamable-http",
        endpoint="http://localhost:9001/mcp",
    )

    def get_provider(self, provider_id):
        return self.provider if provider_id == self.provider.id else None

    async def discover_from_config(self, provider):
        return [
            {
                "id": "markets:get_quote",
                "title": "get_quote",
                "description": "Get a quote.",
                "tool_name": "get_quote",
                "params": {"symbol": {"type": "string"}},
                "category": "finance",
                "provider": "markets",
            }
        ]


class FakeCacheManager:
    def __init__(self):
        self.runtime = []
        self.invalidated = []

    def is_connected(self):
        return True

    def invalidate_provider(self, provider_id):
        self.invalidated.append(provider_id)

    def cache_all_discovery(self, tools):
        return len(tools)

    def cache_all_runtime(self, tools):
        self.runtime = tools
        return len(tools)


@pytest.mark.asyncio
async def test_discovered_mcp_runtime_is_cached_in_runtime_envelope(monkeypatch):
    cache = FakeCacheManager()
    monkeypatch.setattr(mcp_service, "MCPDiscovery", FakeDiscovery)
    monkeypatch.setattr("axiolex.core.cache.get_cache_manager", lambda: cache)

    await mcp_service.discover_provider_tools("markets")

    assert cache.invalidated == ["markets"]
    assert cache.runtime == [
        {
            "id": "markets:get_quote",
            "runtime": {
                "tool_name": "get_quote",
                "params": {"symbol": {"type": "string"}},
                "transport": "streamable-http",
                "endpoint": "http://localhost:9001/mcp",
                "provider": "markets",
                "auth": {"type": "none", "secret_env": None, "username": None},
            },
        }
    ]
