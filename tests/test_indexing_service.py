import pytest
import yaml

from axiolex.mcp.discovery import MCPProviderConfig
from axiolex.services import indexing_service
from axiolex.services.indexing_service import ToolIndexingService


class FakeCacheManager:
    def __init__(self):
        self.replacements = []

    def is_connected(self):
        return True

    def replace_all_tools(self, discovery, runtime):
        self.replacements.append((discovery, runtime))
        return len(discovery)


class FakeMCPDiscovery:
    providers = [
        MCPProviderConfig(
            id="markets",
            name="Markets",
            transport="streamable-http",
            endpoint="http://localhost:9001/mcp",
            enabled=True,
        ),
        MCPProviderConfig(
            id="disabled",
            name="Disabled",
            endpoint="http://localhost:9002/mcp",
            enabled=False,
        ),
    ]

    def __init__(self, config_file):
        self.config_file = config_file

    async def discover_from_config(self, provider):
        return [
            {
                "id": "markets:get_quote",
                "title": "get_quote",
                "description": "Get a stock quote.",
                "tool_name": "get_quote",
                "params": {"symbol": {"type": "string"}},
                "category": "finance",
                "provider": "markets",
            }
        ]

    def close(self):
        pass


@pytest.mark.asyncio
async def test_refresh_atomically_combines_yaml_and_enabled_mcp_tools(
    monkeypatch,
    tmp_path,
):
    tools_file = tmp_path / "tools.yaml"
    tools_file.write_text(
        yaml.safe_dump({
            "documents": [
                {
                    "id": "customer",
                    "title": "Get Customer",
                    "content": "Get a customer.",
                    "metadata": {"enabled": True, "category": "crm"},
                    "runtime": {
                        "provider": "internal",
                        "tool_name": "get_customer",
                        "transport": "http",
                        "endpoint": "/api/customer",
                        "params": {"id": {"type": "string"}},
                    },
                },
                {
                    "id": "disabled",
                    "title": "Disabled",
                    "content": "Disabled tool.",
                    "metadata": {"enabled": False},
                    "runtime": {},
                },
            ]
        }),
        encoding="utf-8",
    )
    cache = FakeCacheManager()
    monkeypatch.setattr(indexing_service, "MCPDiscovery", FakeMCPDiscovery)
    service = ToolIndexingService(
        tools_file=str(tools_file),
        providers_file="providers.yaml",
        cache_manager=cache,
    )

    result = await service.refresh()

    assert result.to_dict() == {
        "yaml_tools": 1,
        "mcp_tools": 1,
        "provider_count": 1,
        "total_tools": 2,
    }
    discovery, runtime = cache.replacements[0]
    assert [tool["id"] for tool in discovery] == [
        "customer",
        "markets:get_quote",
    ]
    assert runtime[1]["runtime"]["transport"] == "streamable-http"
    assert runtime[1]["runtime"]["endpoint"] == "http://localhost:9001/mcp"


@pytest.mark.asyncio
async def test_refresh_does_not_replace_cache_when_enabled_provider_fails(
    monkeypatch,
    tmp_path,
):
    class EmptyMCPDiscovery(FakeMCPDiscovery):
        async def discover_from_config(self, provider):
            return []

    tools_file = tmp_path / "tools.yaml"
    tools_file.write_text("documents: []\n", encoding="utf-8")
    cache = FakeCacheManager()
    monkeypatch.setattr(indexing_service, "MCPDiscovery", EmptyMCPDiscovery)
    service = ToolIndexingService(
        tools_file=str(tools_file),
        providers_file="providers.yaml",
        cache_manager=cache,
    )

    with pytest.raises(RuntimeError, match="returned no tools"):
        await service.refresh()

    assert cache.replacements == []
