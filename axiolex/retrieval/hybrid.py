from __future__ import annotations

from typing import Any, Iterable, Optional

from .colbert import ColBERTIndex, ColBERTModelConfig
from .config import HybridSearchSettings
from .fusion import softmax_score_fusion
from .semantic_text import documents_to_colbert


class HybridSearchEngine:
    """Own the optional ColBERT index and fuse it with lexical rankings."""

    def __init__(self, settings: Optional[HybridSearchSettings] = None):
        self.settings = settings or HybridSearchSettings.from_env()
        self.index: Optional[ColBERTIndex] = None
        self.error: Optional[str] = None

    @property
    def available(self) -> bool:
        return self.settings.enabled and self.index is not None and not self.error

    @property
    def index_ready(self) -> bool:
        return self.index is not None and bool(self.index.documents)

    def rebuild(self, documents: Iterable[Any]) -> None:
        self.index = None
        self.error = None
        if not self.settings.enabled:
            return
        try:
            config = ColBERTModelConfig(
                model_name=self.settings.model_name,
                cache_dir=self.settings.cache_dir,
                batch_size=self.settings.batch_size,
            )
            self.index = ColBERTIndex(documents_to_colbert(documents), config=config)
        except (ImportError, ModuleNotFoundError):
            self.error = (
                "Hybrid search is enabled but ColBERT dependencies are unavailable. "
                'Install them with `pip install "axiolex[colbert]"`.'
            )
        except Exception as exc:
            self.error = f"ColBERT index initialization failed: {exc}"

    def search(
        self,
        query: str,
        lexical_ranking: list[dict[str, Any]],
        documents_by_id: dict[str, Any],
        limit: Optional[int] = None,
        min_hybrid_score: Optional[float] = None,
        temperature: float = 1.0,
        bm25_weight: Optional[float] = None,
        colbert_weight: Optional[float] = None,
        candidate_limit: Optional[int] = None,
        eligible_doc_ids: Optional[set] = None,
    ) -> list[dict[str, Any]]:
        if not self.settings.enabled:
            raise RuntimeError(
                "Hybrid search is disabled. Set AXIOLEX_HYBRID_ENABLED=true."
            )
        if self.error:
            raise RuntimeError(self.error)
        if not self.index:
            raise RuntimeError("Hybrid search index is not ready")

        resolved_candidate_limit = max(
            1,
            (
                candidate_limit
                if candidate_limit is not None
                else self.settings.candidate_limit
            ),
        )
        semantic_results = self.index.search(
            query,
            top_k=resolved_candidate_limit,
            eligible_doc_ids=eligible_doc_ids,
        )
        semantic_ranking = [
            {
                "id": result.document.id,
                "score": result.score,
                "document": documents_by_id.get(result.document.id),
            }
            for result in semantic_results
        ]
        fused = softmax_score_fusion(
            lexical_ranking[:resolved_candidate_limit],
            semantic_ranking,
            temperature=temperature,
            bm25_weight=(
                self.settings.bm25_weight if bm25_weight is None else bm25_weight
            ),
            colbert_weight=(
                self.settings.colbert_weight
                if colbert_weight is None
                else colbert_weight
            ),
        )
        if min_hybrid_score is not None:
            fused = [item for item in fused if item["hybrid_score"] >= min_hybrid_score]
        return fused[:limit] if limit is not None else fused

    def status(self) -> dict[str, Any]:
        return {
            **self.settings.to_dict(),
            "available": self.available,
            "index_ready": self.index_ready,
            "error": self.error,
        }
