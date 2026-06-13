import pytest

from axiolex.core import retriever as retriever_module
from axiolex.core.retriever import BM25SRetriever


class ReadOnlyCache:
    def __init__(self, discovery=None):
        self.discovery = discovery or []
        self.write_calls = []

    def is_connected(self):
        return True

    def get_all_discovery(self):
        return self.discovery

    def get_runtime(self, tool_id):
        return {
            "tool_name": "get_quote",
            "transport": "http",
            "endpoint": "/api/quote",
            "params": {"symbol": {"type": "string"}},
        }

    def get_catalog_version(self):
        return "version-1"

    def delete_discovery_by_source(self, source):
        self.write_calls.append(("delete", source))

    def cache_all_discovery(self, tools):
        self.write_calls.append(("discovery", tools))

    def cache_all_runtime(self, tools):
        self.write_calls.append(("runtime", tools))


def test_read_only_retriever_consumes_cache_without_refreshing_it(monkeypatch):
    cache = ReadOnlyCache(
        discovery=[
            {
                "id": "quote",
                "title": "Get Quote",
                "description": "Get a stock quote.",
                "tool_name": "get_quote",
                "params": {"symbol": {"type": "string"}},
                "provider": "internal",
            }
        ]
    )
    monkeypatch.setattr(retriever_module, "get_cache_manager", lambda: cache)

    retriever = BM25SRetriever(cache_read_only=True, require_cache=True)

    assert retriever.get_document_count() == 1
    assert cache.write_calls == []
    with pytest.raises(RuntimeError, match="read-only cache access"):
        retriever.refresh_local_yaml_cache()


def test_read_only_retriever_requires_prebuilt_cache(monkeypatch):
    monkeypatch.setattr(
        retriever_module,
        "get_cache_manager",
        lambda: ReadOnlyCache(),
    )

    with pytest.raises(RuntimeError, match="Redis tool cache is empty"):
        BM25SRetriever(cache_read_only=True, require_cache=True)


def test_read_only_retriever_rejects_incomplete_runtime_metadata(monkeypatch):
    class IncompleteRuntimeCache(ReadOnlyCache):
        def get_runtime(self, tool_id):
            return {"tool_name": "get_quote", "params": {}}

    cache = IncompleteRuntimeCache(
        discovery=[
            {
                "id": "quote",
                "title": "Get Quote",
                "description": "Get a stock quote.",
                "tool_name": "get_quote",
                "provider": "internal",
            }
        ]
    )
    monkeypatch.setattr(retriever_module, "get_cache_manager", lambda: cache)

    with pytest.raises(RuntimeError, match="complete runtime metadata"):
        BM25SRetriever(cache_read_only=True, require_cache=True)


def test_read_only_retriever_reloads_when_external_catalog_changes(monkeypatch):
    cache = ReadOnlyCache(
        discovery=[
            {
                "id": "quote",
                "title": "Get Quote",
                "description": "Get a stock quote.",
                "tool_name": "get_quote",
                "provider": "internal",
            }
        ]
    )
    monkeypatch.setattr(retriever_module, "get_cache_manager", lambda: cache)
    retriever = BM25SRetriever(cache_read_only=True, require_cache=True)
    cache.get_catalog_version = lambda: "version-2"

    assert retriever.reload_cache_if_changed() is True
    assert retriever.cache_catalog_version == "version-2"
    assert cache.write_calls == []


def test_read_only_retriever_does_not_fallback_when_redis_is_unavailable(
    monkeypatch,
):
    class UnavailableCache:
        def is_connected(self):
            return False

    monkeypatch.setattr(
        retriever_module,
        "get_cache_manager",
        lambda: UnavailableCache(),
    )

    with pytest.raises(RuntimeError, match="Redis tool cache is unavailable"):
        BM25SRetriever(cache_read_only=True, require_cache=True)
