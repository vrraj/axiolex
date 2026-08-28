"""Tests for namespace-scoped retrieval filtering."""

import os
import tempfile

import pytest

from axiolex.core.retriever import BM25SRetriever, Document
from axiolex.mcp.discovery import (
    MCPProviderConfig,
    MCPProviderAuth,
    load_namespaces,
    validate_provider_namespaces,
)


# ---------------------------------------------------------------------------
# Namespace registry loading and validation
# ---------------------------------------------------------------------------


def _write_namespaces_yaml(tmpdir, namespaces):
    path = os.path.join(tmpdir, "namespaces.yaml")
    with open(path, "w") as f:
        f.write("namespaces:\n")
        for ns in namespaces:
            enabled = ns.get("enabled", True)
            f.write(f"  - id: {ns['id']}\n")
            f.write(f"    name: {ns.get('name', '')}\n")
            f.write(f"    description: {ns.get('description', '')}\n")
            f.write(f"    enabled: {enabled}\n")
    return path


def test_load_namespaces_returns_enabled_ids():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_namespaces_yaml(tmpdir, [
            {"id": "finance.market_data", "name": "Market Data"},
            {"id": "finance.trading", "name": "Trading"},
            {"id": "disabled.ns", "name": "Disabled", "enabled": False},
        ])
        result = load_namespaces(path)
        assert "finance.market_data" in result
        assert "finance.trading" in result
        assert "disabled.ns" not in result


def test_load_namespaces_missing_file_returns_empty():
    assert load_namespaces("/nonexistent/path.yaml") == []


def test_validate_provider_namespaces_accepts_valid():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_namespaces_yaml(tmpdir, [
            {"id": "finance.market_data"},
            {"id": "research.web"},
        ])
        providers = [
            MCPProviderConfig(
                id="p1",
                name="Provider 1",
                namespaces=["finance.market_data"],
            ),
            MCPProviderConfig(
                id="p2",
                name="Provider 2",
                namespaces=["finance.market_data", "research.web"],
            ),
        ]
        # Should not raise
        validate_provider_namespaces(providers, path)


def test_validate_provider_namespaces_rejects_unknown():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_namespaces_yaml(tmpdir, [{"id": "finance.market_data"}])
        providers = [
            MCPProviderConfig(
                id="p1",
                name="Provider 1",
                namespaces=["finance.market_data", "unknown.namespace"],
            ),
        ]
        with pytest.raises(ValueError, match="Unknown namespace"):
            validate_provider_namespaces(providers, path)


def test_validate_provider_namespaces_skips_when_registry_empty():
    providers = [
        MCPProviderConfig(
            id="p1",
            name="Provider 1",
            namespaces=["anything"],
        ),
    ]
    # No registry file → validation is skipped
    validate_provider_namespaces(providers, "/nonexistent/path.yaml")


# ---------------------------------------------------------------------------
# Namespace mapping and weight mask in BM25SRetriever
# ---------------------------------------------------------------------------


def _make_documents():
    return [
        Document(
            id="finance:tool1",
            title="Stock Price History",
            content="Fetch historical stock prices and market data.",
            metadata={"namespaces": ["finance.market_data"]},
            runtime={"tool_name": "get_stock_history", "transport": "http", "endpoint": "http://example.com"},
            params={},
        ),
        Document(
            id="finance:tool2",
            title="Trade Executor",
            content="Execute a trade order.",
            metadata={"namespaces": ["finance.trading"]},
            runtime={"tool_name": "execute_trade", "transport": "http", "endpoint": "http://example.com"},
            params={},
        ),
        Document(
            id="research:tool1",
            title="Web Search",
            content="Search the web for information.",
            metadata={"namespaces": ["research.web"]},
            runtime={"tool_name": "web_search", "transport": "http", "endpoint": "http://example.com"},
            params={},
        ),
        Document(
            id="multi:tool1",
            title="Market News",
            content="Get latest market news and analysis.",
            metadata={"namespaces": ["finance.market_data", "research.web"]},
            runtime={"tool_name": "market_news", "transport": "http", "endpoint": "http://example.com"},
            params={},
        ),
    ]


def _build_retriever(documents):
    retriever = BM25SRetriever(use_cache=False)
    retriever.documents = documents
    retriever._build_index_from_documents()
    return retriever


def test_namespace_docs_mapping_built_correctly():
    retriever = _build_retriever(_make_documents())
    assert "finance.market_data" in retriever.namespace_docs
    assert "finance.trading" in retriever.namespace_docs
    assert "research.web" in retriever.namespace_docs
    # Multi-namespace tool appears in both
    multi_idx = next(
        i for i, d in enumerate(retriever.documents) if d.id == "multi:tool1"
    )
    assert multi_idx in retriever.namespace_docs["finance.market_data"]
    assert multi_idx in retriever.namespace_docs["research.web"]


def test_eligible_indices_single_namespace():
    retriever = _build_retriever(_make_documents())
    eligible = retriever._eligible_indices(["finance.market_data"])
    # Should include finance:tool1 and multi:tool1
    eligible_ids = {retriever.documents[i].id for i in eligible}
    assert "finance:tool1" in eligible_ids
    assert "multi:tool1" in eligible_ids
    assert "finance:tool2" not in eligible_ids
    assert "research:tool1" not in eligible_ids


def test_eligible_indices_union_of_namespaces():
    retriever = _build_retriever(_make_documents())
    eligible = retriever._eligible_indices(["finance.market_data", "research.web"])
    eligible_ids = {retriever.documents[i].id for i in eligible}
    assert "finance:tool1" in eligible_ids
    assert "research:tool1" in eligible_ids
    assert "multi:tool1" in eligible_ids
    assert "finance:tool2" not in eligible_ids


def test_eligible_indices_no_namespaces_returns_all():
    retriever = _build_retriever(_make_documents())
    eligible = retriever._eligible_indices(None)
    assert len(eligible) == len(retriever.documents)


def test_weight_mask_zeros_ineligible_docs():
    retriever = _build_retriever(_make_documents())
    mask = retriever._build_weight_mask(["finance.trading"])
    assert mask is not None
    # Only finance:tool2 should be 1.0
    tool2_idx = next(
        i for i, d in enumerate(retriever.documents) if d.id == "finance:tool2"
    )
    for i in range(len(retriever.documents)):
        if i == tool2_idx:
            assert mask[i] == 1.0
        else:
            assert mask[i] == 0.0


def test_weight_mask_none_when_no_namespaces():
    retriever = _build_retriever(_make_documents())
    assert retriever._build_weight_mask(None) is None


def test_weight_mask_zeros_all_when_no_matching_docs():
    retriever = _build_retriever(_make_documents())
    mask = retriever._build_weight_mask(["nonexistent.namespace"])
    assert mask is not None
    assert all(v == 0.0 for v in mask)


# ---------------------------------------------------------------------------
# End-to-end retrieval with namespace filtering
# ---------------------------------------------------------------------------


def test_retrieve_with_namespace_filter_excludes_other_namespaces():
    retriever = _build_retriever(_make_documents())
    result = retriever.retrieve_documents(
        "stock price market data",
        namespaces=["finance.market_data"],
        ignore_zero=True,
        llm_tools_cutoff=0.0,
    )
    assert result["success"]
    doc_ids = {doc["id"] for doc in result["documents"]}
    # Only finance.market_data namespace docs should appear
    assert "finance:tool1" in doc_ids or "multi:tool1" in doc_ids
    assert "finance:tool2" not in doc_ids
    assert "research:tool1" not in doc_ids


def test_retrieve_with_multiple_namespaces_returns_union():
    retriever = _build_retriever(_make_documents())
    result = retriever.retrieve_documents(
        "market data trade",
        namespaces=["finance.market_data", "finance.trading"],
        ignore_zero=True,
        llm_tools_cutoff=0.0,
    )
    assert result["success"]
    doc_ids = {doc["id"] for doc in result["documents"]}
    assert "research:tool1" not in doc_ids


def test_retrieve_without_namespaces_searches_all():
    retriever = _build_retriever(_make_documents())
    result = retriever.retrieve_documents(
        "search web information",
        ignore_zero=True,
        llm_tools_cutoff=0.0,
    )
    assert result["success"]
    doc_ids = {doc["id"] for doc in result["documents"]}
    # Research tool should be eligible when no namespace filter
    assert "research:tool1" in doc_ids


def test_retrieve_with_nonexistent_namespace_returns_empty():
    retriever = _build_retriever(_make_documents())
    result = retriever.retrieve_documents(
        "stock price",
        namespaces=["nonexistent.namespace"],
        ignore_zero=True,
        llm_tools_cutoff=0.0,
    )
    # Should return success but no documents (all masked to zero)
    assert result["success"]
    assert len(result["documents"]) == 0
