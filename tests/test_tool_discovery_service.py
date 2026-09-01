from axiolex.services.tool_discovery_service import ToolDiscoveryService


class FakeRetriever:
    def reload_cache_if_changed(self):
        return False

    def retrieve_documents(self, query, **kwargs):
        assert query == "get stock price history"
        assert kwargs["ignore_zero"] is True
        assert kwargs["llm_tools_cutoff"] == 0.0
        assert kwargs.get("min_hybrid_score") is None
        assert "max_results" not in kwargs
        return {
            "success": True,
            "documents": [
                {
                    "id": "stock_history",
                    "content": "Fetch historical stock prices.",
                    "metadata": {"provider": "markets", "namespaces": ["finance.market_data"]},
                    "bm25_score": 4.0,
                    "softmax_score": 0.72,
                    "relevance_score": 0.72,
                    "rank": 1,
                    "bm25_rank": None,
                    "bm25_softmax_score": None,
                    "colbert_score": None,
                    "colbert_rank": None,
                    "colbert_softmax_score": None,
                    "hybrid_score": None,
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
        "get stock price history", max_tools=1, hybrid_search=False
    )

    assert result["count"] == 1
    assert result["search_mode"] == "lexical"
    assert result["tools"] == [
        {
            "tool_id": "stock_history",
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
            "namespaces": ["finance.market_data"],
            "rank": 1,
            "relevance_score": 0.72,
            "bm25_score": 4.0,
            "softmax_score": 0.72,
            "bm25_rank": None,
            "bm25_softmax_score": None,
            "colbert_score": None,
            "colbert_rank": None,
            "colbert_softmax_score": None,
            "hybrid_score": None,
        }
    ]


def test_discover_tools_validates_top_k():
    service = ToolDiscoveryService(FakeRetriever())

    try:
        service.discover_tools("get stock price history", top_k=0)
    except ValueError as exc:
        assert str(exc) == "top_k must be between 1 and 100"
    else:
        raise AssertionError("Expected top_k validation error")


def test_discover_tools_skips_non_tool_documents_before_applying_limit():
    result = ToolDiscoveryService(FakeRetriever()).discover_tools(
        "get stock price history", max_tools=2, hybrid_search=False
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


def test_discover_tools_passes_hybrid_params_to_retriever():
    class ThresholdRetriever(FakeRetriever):
        def retrieve_documents(self, query, **kwargs):
            assert kwargs["hybrid_search"] is True
            assert kwargs["temperature"] == 0.7
            assert kwargs["min_hybrid_score"] == 0.012
            assert kwargs["bm25_weight"] == 0.4
            assert kwargs["colbert_weight"] == 0.6
            assert kwargs["candidate_limit"] == 50
            result = super().retrieve_documents(
                query,
                ignore_zero=True,
                llm_tools_cutoff=0.0,
                hybrid_search=False,
                temperature=0.7,
                min_hybrid_score=None,
            )
            result["search_mode"] = "hybrid"
            return result

    result = ToolDiscoveryService(ThresholdRetriever()).discover_tools(
        "get stock price history",
        hybrid_search=True,
        temperature=0.7,
        min_hybrid_score=0.012,
        bm25_weight=0.4,
        colbert_weight=0.6,
        candidate_limit=50,
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

    result = service.discover_tools("get stock price history", max_tools=1, hybrid_search=False)

    assert result["tools"][0]["transport"] == "streamable-http"
    assert result["tools"][0]["endpoint"] == "http://localhost:9001/mcp"


def test_discover_tools_includes_unified_relevance_score_and_rank_lexical():
    """Lexical results must include relevance_score (0-1) and rank."""
    result = ToolDiscoveryService(FakeRetriever()).discover_tools(
        "get stock price history", max_tools=1, hybrid_search=False
    )
    tool = result["tools"][0]
    assert "relevance_score" in tool
    assert "rank" in tool
    assert 0.0 <= tool["relevance_score"] <= 1.0
    assert tool["rank"] == 1
    # relevance_score equals softmax_score in lexical mode
    assert tool["relevance_score"] == tool["softmax_score"]


def test_discover_tools_includes_unified_relevance_score_and_rank_hybrid():
    """Hybrid results must include relevance_score (0-1) and rank."""
    class HybridScoreRetriever:
        def reload_cache_if_changed(self):
            return False

        def retrieve_documents(self, query, **kwargs):
            return {
                "success": True,
                "search_mode": "hybrid",
                "documents": [
                    {
                        "id": "stock_history",
                        "content": "Fetch historical stock prices.",
                        "metadata": {"provider": "markets", "namespaces": ["finance.market_data"]},
                        "bm25_score": 4.0,
                        "softmax_score": 0.72,
                        "relevance_score": 0.85,
                        "rank": 1,
                        "bm25_rank": 1,
                        "bm25_softmax_score": 0.6,
                        "colbert_score": 3.5,
                        "colbert_rank": 1,
                        "colbert_softmax_score": 0.9,
                        "hybrid_score": 0.85,
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
                ],
            }

    result = ToolDiscoveryService(HybridScoreRetriever()).discover_tools(
        "get stock price history", max_tools=1, hybrid_search=True
    )
    tool = result["tools"][0]
    assert "relevance_score" in tool
    assert "rank" in tool
    assert 0.0 <= tool["relevance_score"] <= 1.0
    assert tool["rank"] == 1
    # relevance_score equals hybrid_score in hybrid mode
    assert tool["relevance_score"] == tool["hybrid_score"]


def test_discover_tools_includes_namespaces_in_tool_definition():
    """Tool definitions must include namespace metadata."""
    result = ToolDiscoveryService(FakeRetriever()).discover_tools(
        "get stock price history", max_tools=1, hybrid_search=False
    )
    tool = result["tools"][0]
    assert "namespaces" in tool
    assert tool["namespaces"] == ["finance.market_data"]


def test_discover_tools_hybrid_search_none_uses_deployment_default(monkeypatch):
    """When hybrid_search is None, the deployment config decides."""
    class HybridCheckRetriever(FakeRetriever):
        def retrieve_documents(self, query, **kwargs):
            self.last_hybrid = kwargs["hybrid_search"]
            return super().retrieve_documents(query, **kwargs)

    # When hybrid is disabled on the deployment, None → lexical
    monkeypatch.setenv("AXIOLEX_HYBRID_ENABLED", "false")
    from importlib import reload
    from axiolex.services import tool_discovery_service as tds_mod
    reload(tds_mod)
    retriever = HybridCheckRetriever()
    tds_mod.ToolDiscoveryService(retriever).discover_tools(
        "get stock price history", max_tools=1
    )
    assert retriever.last_hybrid is False

    # When hybrid is enabled on the deployment, None → hybrid
    monkeypatch.setenv("AXIOLEX_HYBRID_ENABLED", "true")
    reload(tds_mod)
    retriever2 = HybridCheckRetriever()
    tds_mod.ToolDiscoveryService(retriever2).discover_tools(
        "get stock price history", max_tools=1
    )
    assert retriever2.last_hybrid is True

    # Restore module
    monkeypatch.delenv("AXIOLEX_HYBRID_ENABLED", raising=False)
    reload(tds_mod)


# ---------------------------------------------------------------------------
# Discovery audit logging
# ---------------------------------------------------------------------------


def test_audit_log_writes_jsonl_record(tmp_path, monkeypatch):
    """discover_tools writes one JSONL audit record with the right fields."""
    import json
    from importlib import reload
    from axiolex.services import tool_discovery_service as tds_mod

    monkeypatch.setenv("AXIOLEX_LOG_DIR", str(tmp_path))
    reload(tds_mod)

    result = tds_mod.ToolDiscoveryService(FakeRetriever()).discover_tools(
        "get stock price history", max_tools=1, hybrid_search=False
    )

    log_file = tmp_path / "discovery_audit.jsonl"
    assert log_file.exists(), "Audit log file was not created"
    lines = log_file.read_text().strip().split("\n")
    assert len(lines) == 1, "Should write exactly one line"
    record = json.loads(lines[0])

    assert record["caller"] == "default"
    assert record["query"] == "get stock price history"
    assert record["namespaces"] == []
    assert isinstance(record["latency_ms"], int)
    assert record["latency_ms"] >= 0
    assert len(record["results"]) == 1
    assert record["results"][0]["tool"] == "get_stock_price_history"
    assert record["results"][0]["score"] == 0.72
    # Must not log internal retrieval scores
    assert "bm25_score" not in record["results"][0]
    assert "softmax_score" not in record["results"][0]
    assert "hybrid_score" not in record["results"][0]

    monkeypatch.delenv("AXIOLEX_LOG_DIR", raising=False)
    reload(tds_mod)


def test_audit_log_logs_only_top_k_results(tmp_path, monkeypatch):
    """Audit log should contain only the top_k results returned to the consumer."""
    import json
    from importlib import reload
    from axiolex.services import tool_discovery_service as tds_mod

    monkeypatch.setenv("AXIOLEX_LOG_DIR", str(tmp_path))
    reload(tds_mod)

    tds_mod.ToolDiscoveryService(FakeRetriever()).discover_tools(
        "get stock price history", max_tools=1, hybrid_search=False
    )

    log_file = tmp_path / "discovery_audit.jsonl"
    record = json.loads(log_file.read_text().strip())
    # FakeRetriever returns 2 tools (stock_history + quote), but top_k=1
    assert len(record["results"]) == 1

    monkeypatch.delenv("AXIOLEX_LOG_DIR", raising=False)
    reload(tds_mod)


def test_audit_log_failure_does_not_crash_discovery(monkeypatch):
    """If audit logging fails, discovery should still return results."""
    from importlib import reload
    from axiolex.services import tool_discovery_service as tds_mod

    monkeypatch.setenv("AXIOLEX_LOG_DIR", "/nonexistent/path/that/cannot/be/created")
    reload(tds_mod)

    # Should not raise even though the log directory is invalid
    result = tds_mod.ToolDiscoveryService(FakeRetriever()).discover_tools(
        "get stock price history", max_tools=1, hybrid_search=False
    )
    assert result["count"] == 1
    assert result["tools"][0]["name"] == "get_stock_price_history"

    monkeypatch.delenv("AXIOLEX_LOG_DIR", raising=False)
    reload(tds_mod)


def test_audit_log_logs_namespaces(tmp_path, monkeypatch):
    """Audit record should include the namespaces used for retrieval."""
    import json
    from importlib import reload
    from axiolex.services import tool_discovery_service as tds_mod

    monkeypatch.setenv("AXIOLEX_LOG_DIR", str(tmp_path))
    reload(tds_mod)

    tds_mod.ToolDiscoveryService(FakeRetriever()).discover_tools(
        "get stock price history",
        max_tools=1,
        hybrid_search=False,
        namespaces=["finance.market_data"],
    )

    log_file = tmp_path / "discovery_audit.jsonl"
    record = json.loads(log_file.read_text().strip())
    assert record["namespaces"] == ["finance.market_data"]

    monkeypatch.delenv("AXIOLEX_LOG_DIR", raising=False)
    reload(tds_mod)
