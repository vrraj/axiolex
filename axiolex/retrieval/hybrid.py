from __future__ import annotations

from typing import Any, Iterable, Optional

from .colbert import ColBERTIndex, ColBERTModelConfig
from .config import HybridSearchSettings
from .fusion import reciprocal_rank_fusion
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
        min_rrf_score: Optional[float] = None,
    ) -> list[dict[str, Any]]:
        if not self.settings.enabled:
            raise RuntimeError(
                "Hybrid search is disabled. Set AXIOLEX_HYBRID_ENABLED=true."
            )
        if self.error:
            raise RuntimeError(self.error)
        if not self.index:
            raise RuntimeError("Hybrid search index is not ready")

        candidate_limit = max(1, self.settings.candidate_limit)
        semantic_results = self.index.search(query, top_k=candidate_limit)
        semantic_ranking = [
            {
                "id": result.document.id,
                "score": result.score,
                "document": documents_by_id.get(result.document.id),
            }
            for result in semantic_results
        ]
        fused = reciprocal_rank_fusion(
            lexical_ranking[:candidate_limit],
            semantic_ranking,
            rrf_k=self.settings.rrf_k,
        )
        if min_rrf_score is not None:
            fused = [
                item for item in fused
                if item["rrf_score"] >= min_rrf_score
            ]
        return fused[:limit] if limit is not None else fused

    def status(self) -> dict[str, Any]:
        return {
            **self.settings.to_dict(),
            "available": self.available,
            "index_ready": self.index_ready,
            "error": self.error,
        }
