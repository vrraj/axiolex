from axiolex.db import document_service


class FakeCache:
    def __init__(self, connected=True):
        self.connected = connected
        self.discovery = []

    def is_connected(self):
        return self.connected

    def get_all_discovery(self):
        return self.discovery


class FakeRetriever:
    documents = []

    def refresh_local_yaml_cache(self):
        raise AssertionError("listing documents must not mutate Redis")


def test_get_documents_reads_redis_without_refreshing_local_yaml(monkeypatch):
    cache = FakeCache()
    cache.discovery = [{
        "id": "markets:quote",
        "title": "Quote",
        "description": "Get a quote.",
        "tool_name": "get_quote",
        "params": {},
        "category": "finance",
        "provider": "markets",
        "source": "mcp-discovery",
    }]
    monkeypatch.setattr(document_service, "get_cache_manager", lambda: cache)
    monkeypatch.setattr(document_service, "get_retriever", lambda: FakeRetriever())

    result = document_service.get_documents_from_cache()

    assert result["source"] == "redis_cache"
    assert result["documents"][0]["type"] == "mcp"


def test_get_documents_recognizes_mcp_source_when_provider_is_unknown(monkeypatch):
    cache = FakeCache()
    cache.discovery = [{
        "id": "provider:tool",
        "title": "Tool",
        "description": "Discovered tool.",
        "tool_name": "tool",
        "params": {},
        "category": "general",
        "provider": "unknown",
        "source": "mcp-discovery",
    }]
    monkeypatch.setattr(document_service, "get_cache_manager", lambda: cache)
    monkeypatch.setattr(document_service, "get_retriever", lambda: FakeRetriever())

    result = document_service.get_documents_from_cache()

    assert result["documents"][0]["type"] == "mcp"


def test_get_documents_recognizes_yaml_source_with_internal_provider(monkeypatch):
    cache = FakeCache()
    cache.discovery = [{
        "id": "local-tool",
        "title": "Local Tool",
        "description": "Local tool.",
        "tool_name": "local_tool",
        "params": {},
        "category": "general",
        "provider": "internal",
        "source": "yaml",
    }]
    monkeypatch.setattr(document_service, "get_cache_manager", lambda: cache)
    monkeypatch.setattr(document_service, "get_retriever", lambda: FakeRetriever())

    result = document_service.get_documents_from_cache()

    assert result["documents"][0]["type"] == "local"


def test_get_documents_warns_when_redis_is_unavailable(monkeypatch):
    monkeypatch.setattr(
        document_service,
        "get_cache_manager",
        lambda: FakeCache(connected=False),
    )
    monkeypatch.setattr(document_service, "get_retriever", lambda: FakeRetriever())

    result = document_service.get_documents_from_cache()

    assert result["source"] == "retriever"
    assert "MCP-discovered tools may be missing" in result["warning"]
