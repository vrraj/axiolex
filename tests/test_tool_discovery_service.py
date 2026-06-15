from axiolex.services.tool_discovery_service import ToolDiscoveryService


class FakeRetriever:
    def reload_cache_if_changed(self):
        return False

    def retrieve_documents(self, query, **kwargs):
        assert query == "get stock price history"
        assert kwargs["ignore_zero"] is True
        assert kwargs["llm_tools_cutoff"] == 0.0
        assert kwargs["hybrid_search"] is False
        assert "max_results" not in kwargs
        return {
            "success": True,
            "documents": [
                {
                    "id": "stock_history",
                    "content": "Fetch historical stock prices.",
                    "metadata": {"provider": "markets"},
                    "runtime": {
                        "tool_name": "get_stock_price_history",
                        "transport": "mcp",
                        "endpoint": {
                            "url": "http://localhost:9001/mcp",
                            "tool": "get_stock_price_history",
                        },
                    },
                    "params": {
                        "symbol": {"type": "string"},
                        "period": {"type": "string"},
                    },
                },
                {
                    "id": "stock_documentation",
                    "content": "Documentation about stocks, not an executable tool.",
                    "runtime": {},
                    "params": {},
                },
                {
                    "id": "quote",
                    "content": "Get a current quote.",
                    "runtime": {"tool_name": "get_quote", "transport": "http"},
                    "params": {},
                },
            ],
        }


def test_discover_tools_returns_execution_ready_definitions():
    result = ToolDiscoveryService(FakeRetriever()).discover_tools(
        "get stock price history", max_tools=1
    )

    assert result["count"] == 1
    assert result["search_mode"] == "lexical"
    assert result["tools"] == [
        {
            "name": "get_stock_price_history",
            "description": "Fetch historical stock prices.",
            "params": {
                "symbol": {"type": "string"},
                "period": {"type": "string"},
            },
            "inputSchema": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "period": {"type": "string"},
                },
                "required": [],
            },
            "endpoint": {
                "url": "http://localhost:9001/mcp",
                "tool": "get_stock_price_history",
            },
            "transport": "mcp",
            "provider": "markets",
        }
    ]


def test_discover_tools_validates_max_tools():
    service = ToolDiscoveryService(FakeRetriever())

    try:
        service.discover_tools("get stock price history", max_tools=0)
    except ValueError as exc:
        assert str(exc) == "max_tools must be between 1 and 100"
    else:
        raise AssertionError("Expected max_tools validation error")


def test_discover_tools_skips_non_tool_documents_before_applying_limit():
    result = ToolDiscoveryService(FakeRetriever()).discover_tools(
        "get stock price history", max_tools=2
    )

    assert [tool["name"] for tool in result["tools"]] == [
        "get_stock_price_history",
        "get_quote",
    ]


def test_discover_tools_passes_hybrid_search_to_retriever():
    class HybridRetriever(FakeRetriever):
        def retrieve_documents(self, query, **kwargs):
            assert kwargs["hybrid_search"] is True
            result = super().retrieve_documents(
                query,
                ignore_zero=True,
                llm_tools_cutoff=0.0,
                hybrid_search=False,
            )
            result["search_mode"] = "hybrid"
            return result

    result = ToolDiscoveryService(HybridRetriever()).discover_tools(
        "get stock price history",
        max_tools=1,
        hybrid_search=True,
    )

    assert result["search_mode"] == "hybrid"


def test_discover_tools_fills_missing_runtime_route_from_provider_config():
    class MissingRouteRetriever(FakeRetriever):
        def retrieve_documents(self, query, **kwargs):
            result = super().retrieve_documents(query, **kwargs)
            result["documents"][0]["runtime"].pop("endpoint")
            result["documents"][0]["runtime"].pop("transport")
            return result

    service = ToolDiscoveryService(
        MissingRouteRetriever(),
        provider_routes={
            "markets": {
                "transport": "streamable-http",
                "endpoint": "http://localhost:9001/mcp",
            }
        },
    )

    result = service.discover_tools("get stock price history", max_tools=1)

    assert result["tools"][0]["transport"] == "streamable-http"
    assert result["tools"][0]["endpoint"] == "http://localhost:9001/mcp"
