import pytest

from axiolex.core import retriever as retriever_module
from axiolex.core.retriever import BM25SRetriever, Document
from axiolex.retrieval.colbert import ColBERTModelConfig
from axiolex.retrieval.config import HybridSearchSettings
from axiolex.retrieval.fusion import reciprocal_rank_fusion
from axiolex.retrieval.semantic_text import document_semantic_text


def test_hybrid_settings_are_disabled_by_default(monkeypatch):
    monkeypatch.delenv("AXIOLEX_HYBRID_ENABLED", raising=False)

    settings = HybridSearchSettings.from_env()

    assert settings.enabled is False


def test_hybrid_settings_load_from_environment(monkeypatch):
    monkeypatch.setenv("AXIOLEX_HYBRID_ENABLED", "true")
    monkeypatch.setenv("AXIOLEX_RRF_K", "42")
    monkeypatch.setenv("AXIOLEX_HYBRID_CANDIDATE_LIMIT", "25")

    settings = HybridSearchSettings.from_env()

    assert settings.enabled is True
    assert settings.rrf_k == 42
    assert settings.candidate_limit == 25


def test_colbert_cache_uses_only_axiolex_cache_setting(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_CACHE_PATH", "/ignored/models")
    monkeypatch.delenv("AXIOLEX_COLBERT_CACHE_DIR", raising=False)

    assert HybridSearchSettings.from_env().cache_dir is None
    assert ColBERTModelConfig().resolved_cache_dir() is None

    monkeypatch.setenv("AXIOLEX_COLBERT_CACHE_DIR", "~/models/fastembed_cache")
    settings = HybridSearchSettings.from_env()

    assert settings.cache_dir == "~/models/fastembed_cache"
    assert ColBERTModelConfig(cache_dir=settings.cache_dir).resolved_cache_dir().endswith(
        "/models/fastembed_cache"
    )


def test_semantic_text_includes_tool_name_keywords_and_parameters():
    document = Document(
        id="quote",
        title="Get Quote",
        content="Get current market pricing.",
        keywords=["stock"],
        runtime={"tool_name": "get_quote"},
        params={
            "symbol": {
                "type": "string",
                "description": "Ticker symbol",
            }
        },
    )

    text = document_semantic_text(document)

    assert "tool name: get_quote" in text
    assert "keyword: stock" in text
    assert "parameter: symbol string Ticker symbol" in text


def test_rrf_fuses_rankings_and_preserves_component_scores():
    fused = reciprocal_rank_fusion(
        lexical=[
            {"id": "a", "score": 4.0, "document": {"id": "a"}},
            {"id": "b", "score": 3.0, "document": {"id": "b"}},
        ],
        semantic=[
            {"id": "b", "score": 9.0, "document": {"id": "b"}},
            {"id": "c", "score": 8.0, "document": {"id": "c"}},
        ],
        rrf_k=60,
    )

    assert [item["id"] for item in fused] == ["b", "a", "c"]
    assert fused[0]["bm25_rank"] == 2
    assert fused[0]["colbert_rank"] == 1
    assert fused[0]["bm25_score"] == 3.0
    assert fused[0]["colbert_score"] == 9.0


def test_hybrid_retrieval_bypasses_softmax(monkeypatch):
    retriever = BM25SRetriever(
        use_cache=False,
        document_file="missing.yaml",
        hybrid_settings=HybridSearchSettings(enabled=False),
    )
    document = Document(id="quote", title="Get Quote", content="Get a stock quote.")
    retriever.rebuild_index([document])

    class FakeHybridSearch:
        settings = HybridSearchSettings(enabled=True, rrf_k=60, candidate_limit=10)

        def rebuild(self, documents):
            pass

        def search(self, query, lexical_ranking, documents_by_id, limit=None):
            assert lexical_ranking
            return [{
                "id": "quote",
                "document": documents_by_id["quote"],
                "bm25_score": lexical_ranking[0]["score"],
                "bm25_rank": 1,
                "colbert_score": 12.0,
                "colbert_rank": 1,
                "rrf_score": 2 / 61,
            }]

    retriever.hybrid_search = FakeHybridSearch()
    monkeypatch.setattr(
        retriever,
        "_calculate_softmax",
        lambda *args, **kwargs: pytest.fail("softmax must not run in hybrid mode"),
    )

    result = retriever.retrieve_documents("stock quote", hybrid_search=True)

    assert result["success"] is True
    assert result["search_mode"] == "hybrid"
    assert result["documents"][0]["rrf_score"] == 2 / 61
    assert "softmax_score" not in result["documents"][0]


def test_hybrid_retrieval_can_run_without_lexical_tokens(monkeypatch):
    retriever = BM25SRetriever(
        use_cache=False,
        document_file="missing.yaml",
        hybrid_settings=HybridSearchSettings(enabled=False),
    )
    document = Document(id="quote", title="Get Quote", content="Get a stock quote.")
    retriever.rebuild_index([document])

    class SemanticOnlyHybridSearch:
        settings = HybridSearchSettings(enabled=True)

        def rebuild(self, documents):
            pass

        def search(self, query, lexical_ranking, documents_by_id, limit=None):
            assert lexical_ranking == []
            return [{
                "id": "quote",
                "document": documents_by_id["quote"],
                "bm25_score": None,
                "bm25_rank": None,
                "colbert_score": 7.0,
                "colbert_rank": 1,
                "rrf_score": 1 / 61,
            }]

    retriever.hybrid_search = SemanticOnlyHybridSearch()
    monkeypatch.setattr(retriever_module.bm25s, "tokenize", lambda *args, **kwargs: [])

    result = retriever.retrieve_documents("the", hybrid_search=True)

    assert result["success"] is True
    assert result["documents"][0]["bm25_rank"] is None
    assert result["documents"][0]["colbert_rank"] == 1


def test_colbert_index_rebuilds_with_bm25_index():
    retriever = BM25SRetriever(
        use_cache=False,
        document_file="missing.yaml",
        hybrid_settings=HybridSearchSettings(enabled=False),
    )
    indexed_batches = []
    retriever.hybrid_search.rebuild = lambda documents: indexed_batches.append(
        [document.id for document in documents]
    )

    retriever.rebuild_index([
        Document(id="quote", title="Get Quote", content="Get a stock quote."),
        Document(id="order", title="Get Order", content="Get an order."),
    ])

    assert retriever.retriever is not None
    assert indexed_batches == [["quote", "order"]]
