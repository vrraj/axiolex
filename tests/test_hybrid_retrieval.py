from axiolex.core import retriever as retriever_module
from axiolex.core.retriever import BM25SRetriever, Document
from axiolex.retrieval.colbert import ColBERTModelConfig
from axiolex.retrieval.config import HybridSearchSettings
from axiolex.retrieval.fusion import reciprocal_rank_fusion, softmax_score_fusion
from axiolex.retrieval.hybrid import HybridSearchEngine
from axiolex.retrieval.semantic_text import document_semantic_text


def test_hybrid_settings_are_disabled_by_default(monkeypatch):
    monkeypatch.delenv("AXIOLEX_HYBRID_ENABLED", raising=False)

    settings = HybridSearchSettings.from_env()

    assert settings.enabled is False


def test_hybrid_settings_load_from_environment(monkeypatch):
    monkeypatch.setenv("AXIOLEX_HYBRID_ENABLED", "true")
    monkeypatch.setenv("AXIOLEX_RRF_K", "42")
    monkeypatch.setenv("AXIOLEX_HYBRID_CANDIDATE_LIMIT", "25")
    monkeypatch.setenv("AXIOLEX_HYBRID_BM25_WEIGHT", "0.3")
    monkeypatch.setenv("AXIOLEX_HYBRID_COLBERT_WEIGHT", "0.7")

    settings = HybridSearchSettings.from_env()

    assert settings.enabled is True
    assert settings.rrf_k == 42
    assert settings.candidate_limit == 25
    assert settings.bm25_weight == 0.3
    assert settings.colbert_weight == 0.7


def test_colbert_cache_uses_only_axiolex_cache_setting(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_CACHE_PATH", "/ignored/models")
    monkeypatch.delenv("AXIOLEX_COLBERT_CACHE_DIR", raising=False)

    assert HybridSearchSettings.from_env().cache_dir is None
    assert ColBERTModelConfig().resolved_cache_dir() is None

    monkeypatch.setenv("AXIOLEX_COLBERT_CACHE_DIR", "~/models/fastembed_cache")
    settings = HybridSearchSettings.from_env()

    assert settings.cache_dir == "~/models/fastembed_cache"
    assert (
        ColBERTModelConfig(cache_dir=settings.cache_dir)
        .resolved_cache_dir()
        .endswith("/models/fastembed_cache")
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


def test_softmax_score_fusion_normalizes_each_model_before_blending():
    fused = softmax_score_fusion(
        lexical=[
            {"id": "a", "score": 4.0, "document": {"id": "a"}},
            {"id": "b", "score": 3.0, "document": {"id": "b"}},
        ],
        semantic=[
            {"id": "b", "score": 90.0, "document": {"id": "b"}},
            {"id": "c", "score": 80.0, "document": {"id": "c"}},
        ],
        temperature=1.0,
        bm25_weight=0.4,
        colbert_weight=0.6,
    )

    assert [item["id"] for item in fused] == ["b", "a", "c"]
    assert fused[0]["bm25_rank"] == 2
    assert fused[0]["colbert_rank"] == 1
    assert fused[0]["bm25_softmax_score"] > 0
    assert fused[0]["colbert_softmax_score"] > 0
    assert fused[0]["hybrid_score"] > fused[1]["hybrid_score"]


def test_hybrid_engine_filters_min_hybrid_score_before_limit():
    class SemanticResult:
        def __init__(self, document, score):
            self.document = document
            self.score = score

    class FakeIndex:
        def search(self, query, top_k):
            return [
                SemanticResult(Document(id="semantic", title="", content=""), 9.0),
                SemanticResult(Document(id="both", title="", content=""), 8.0),
            ]

    engine = HybridSearchEngine(
        HybridSearchSettings(enabled=True, rrf_k=60, candidate_limit=10)
    )
    engine.index = FakeIndex()
    documents = {
        "lexical": Document(id="lexical", title="", content=""),
        "semantic": Document(id="semantic", title="", content=""),
        "both": Document(id="both", title="", content=""),
    }

    results = engine.search(
        query="query",
        lexical_ranking=[
            {"id": "both", "score": 5.0, "document": documents["both"]},
            {"id": "lexical", "score": 4.0, "document": documents["lexical"]},
        ],
        documents_by_id=documents,
        limit=1,
        min_hybrid_score=0.2,
        temperature=1.0,
        bm25_weight=0.4,
        colbert_weight=0.6,
    )

    assert [result["id"] for result in results] == ["both"]


def test_hybrid_retrieval_uses_softmax_score_fusion(monkeypatch):
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

        def search(
            self,
            query,
            lexical_ranking,
            documents_by_id,
            limit=None,
            min_hybrid_score=None,
            temperature=1.0,
            bm25_weight=None,
            colbert_weight=None,
            candidate_limit=None,
        ):
            assert lexical_ranking
            assert min_hybrid_score is None
            assert temperature == 0.5
            assert bm25_weight == 0.4
            assert colbert_weight == 0.6
            assert candidate_limit == 20
            return [
                {
                    "id": "quote",
                    "document": documents_by_id["quote"],
                    "bm25_score": lexical_ranking[0]["score"],
                    "bm25_rank": 1,
                    "bm25_softmax_score": 1.0,
                    "colbert_score": 12.0,
                    "colbert_rank": 1,
                    "colbert_softmax_score": 1.0,
                    "hybrid_score": 1.0,
                }
            ]

    retriever.hybrid_search = FakeHybridSearch()

    result = retriever.retrieve_documents(
        "stock quote",
        hybrid_search=True,
        temperature=0.5,
        bm25_weight=0.4,
        colbert_weight=0.6,
        candidate_limit=20,
    )

    assert result["success"] is True
    assert result["search_mode"] == "hybrid"
    assert result["documents"][0]["hybrid_score"] == 1.0
    assert result["documents"][0]["bm25_softmax_score"] == 1.0
    assert result["documents"][0]["colbert_softmax_score"] == 1.0
    assert result["settings"]["temperature"] == 0.5
    assert result["settings"]["bm25_weight"] == 0.4
    assert result["settings"]["colbert_weight"] == 0.6
    assert result["settings"]["candidate_limit"] == 20


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

        def search(
            self,
            query,
            lexical_ranking,
            documents_by_id,
            limit=None,
            min_hybrid_score=None,
            temperature=1.0,
            bm25_weight=None,
            colbert_weight=None,
            candidate_limit=None,
        ):
            assert lexical_ranking == []
            assert min_hybrid_score is None
            return [
                {
                    "id": "quote",
                    "document": documents_by_id["quote"],
                    "bm25_score": None,
                    "bm25_rank": None,
                    "bm25_softmax_score": 0.0,
                    "colbert_score": 7.0,
                    "colbert_rank": 1,
                    "colbert_softmax_score": 1.0,
                    "hybrid_score": 0.6,
                }
            ]

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

    retriever.rebuild_index(
        [
            Document(id="quote", title="Get Quote", content="Get a stock quote."),
            Document(id="order", title="Get Order", content="Get an order."),
        ]
    )

    assert retriever.retriever is not None
    assert indexed_batches == [["quote", "order"]]


def test_lexical_retrieval_limits_final_results():
    retriever = BM25SRetriever(
        use_cache=False,
        document_file="missing.yaml",
        hybrid_settings=HybridSearchSettings(enabled=False),
    )
    retriever.rebuild_index(
        [
            Document(id="quote-a", title="Stock Quote A", content="Get stock quote."),
            Document(id="quote-b", title="Stock Quote B", content="Get stock quote."),
            Document(id="quote-c", title="Stock Quote C", content="Get stock quote."),
        ]
    )

    result = retriever.retrieve_documents(
        "stock quote",
        llm_tools_cutoff=0.0,
        max_results=2,
    )

    assert result["success"] is True
    assert len(result["documents"]) == 2
    assert result["total_retrieved"] == 3
    assert result["settings"]["max_results"] == 2


def test_hybrid_retrieval_filters_min_hybrid_score_before_limit():
    retriever = BM25SRetriever(
        use_cache=False,
        document_file="missing.yaml",
        hybrid_settings=HybridSearchSettings(enabled=False),
    )
    documents = [
        Document(id="strong", title="Strong", content="Strong match."),
        Document(id="weak", title="Weak", content="Weak match."),
    ]
    retriever.rebuild_index(documents)

    class ThresholdHybridSearch:
        settings = HybridSearchSettings(enabled=True, rrf_k=60, candidate_limit=10)

        def rebuild(self, documents):
            pass

        def search(
            self,
            query,
            lexical_ranking,
            documents_by_id,
            limit=None,
            min_hybrid_score=None,
            temperature=1.0,
            bm25_weight=None,
            colbert_weight=None,
            candidate_limit=None,
        ):
            assert limit == 1
            assert min_hybrid_score == 0.2
            fused = [
                {
                    "id": "weak",
                    "document": documents_by_id["weak"],
                    "bm25_score": None,
                    "bm25_rank": None,
                    "bm25_softmax_score": 0.0,
                    "colbert_score": 4.0,
                    "colbert_rank": 1,
                    "colbert_softmax_score": 1.0,
                    "hybrid_score": 0.1,
                },
                {
                    "id": "strong",
                    "document": documents_by_id["strong"],
                    "bm25_score": 3.0,
                    "bm25_rank": 1,
                    "bm25_softmax_score": 1.0,
                    "colbert_score": 5.0,
                    "colbert_rank": 1,
                    "colbert_softmax_score": 1.0,
                    "hybrid_score": 0.5,
                },
            ]
            filtered = [
                item for item in fused if item["hybrid_score"] >= min_hybrid_score
            ]
            return filtered[:limit]

    retriever.hybrid_search = ThresholdHybridSearch()

    result = retriever.retrieve_documents(
        "match",
        hybrid_search=True,
        min_hybrid_score=0.2,
        max_results=1,
    )

    assert [document["id"] for document in result["documents"]] == ["strong"]
    assert result["settings"]["min_hybrid_score"] == 0.2
