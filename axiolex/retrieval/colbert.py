from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Sequence


DEFAULT_COLBERT_MODEL = "colbert-ir/colbertv2.0"


@dataclass
class ColBERTModelConfig:
    model_name: str = DEFAULT_COLBERT_MODEL
    cache_dir: Optional[str] = None
    batch_size: int = 32
    extra: Dict[str, Any] = field(default_factory=dict)

    def resolved_cache_dir(self) -> Optional[str]:
        if not self.cache_dir:
            return None
        return os.path.expandvars(os.path.expanduser(str(self.cache_dir)))

    def model_kwargs(self) -> Dict[str, Any]:
        kwargs = dict(self.extra or {})
        cache_dir = self.resolved_cache_dir()
        if cache_dir:
            kwargs["cache_dir"] = cache_dir
        return kwargs


@dataclass
class ColBERTDocument:
    id: str
    text: str
    title: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, item: Dict[str, Any]) -> "ColBERTDocument":
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else item
        text = (
            payload.get("text")
            or payload.get("snippet")
            or payload.get("content")
            or item.get("text")
            or item.get("content")
            or ""
        )
        doc_id = str(
            item.get("id")
            or payload.get("id")
            or payload.get("url")
            or payload.get("title")
            or len(text)
        )
        title = str(item.get("title") or payload.get("title") or "")
        metadata = dict(item.get("metadata") or {})
        if isinstance(item.get("payload"), dict):
            metadata.setdefault("payload", item.get("payload"))
        return cls(id=doc_id, text=str(text), title=title, metadata=metadata)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "text": self.text,
            "metadata": self.metadata,
        }


@dataclass
class ColBERTSearchResult:
    document: ColBERTDocument
    score: float
    rank: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rank": self.rank,
            "score": self.score,
            "document": self.document.to_dict(),
        }


@lru_cache(maxsize=4)
def _get_colbert_model(model_name: str, cache_dir: Optional[str], extra_items: tuple):
    from fastembed import LateInteractionTextEmbedding

    kwargs = dict(extra_items)
    if cache_dir:
        kwargs["cache_dir"] = cache_dir
    return LateInteractionTextEmbedding(model_name=model_name, **kwargs)


class ColBERTIndex:
    def __init__(
        self,
        documents: Optional[Iterable[ColBERTDocument | Dict[str, Any]]] = None,
        config: Optional[ColBERTModelConfig] = None,
    ):
        self.config = config or ColBERTModelConfig()
        self.documents: List[ColBERTDocument] = []
        self._doc_embeddings: List[Any] = []
        if documents is not None:
            self.index(documents)

    @property
    def model(self):
        kwargs = self.config.model_kwargs()
        cache_dir = kwargs.pop("cache_dir", None)
        extra_items = tuple(sorted(kwargs.items()))
        return _get_colbert_model(self.config.model_name, cache_dir, extra_items)

    def index(self, documents: Iterable[ColBERTDocument | Dict[str, Any]]) -> None:
        self.documents = [self._coerce_document(document) for document in documents]
        texts = [document.text for document in self.documents]
        if not texts:
            self._doc_embeddings = []
            return
        self._doc_embeddings = list(
            self.model.embed(texts, batch_size=self.config.batch_size)
        )

    def add_documents(self, documents: Iterable[ColBERTDocument | Dict[str, Any]]) -> None:
        new_documents = [self._coerce_document(document) for document in documents]
        if not new_documents:
            return
        new_embeddings = list(
            self.model.embed(
                [document.text for document in new_documents],
                batch_size=self.config.batch_size,
            )
        )
        self.documents.extend(new_documents)
        self._doc_embeddings.extend(new_embeddings)

    def search(self, query: str, top_k: int = 10) -> List[ColBERTSearchResult]:
        query = str(query or "").strip()
        if not query:
            raise ValueError("query must not be empty")
        if not self.documents or not self._doc_embeddings:
            return []

        scored = self.score(query)
        scored.sort(key=lambda result: result.score, reverse=True)
        limit = max(1, int(top_k))
        return [
            ColBERTSearchResult(
                document=result.document,
                score=result.score,
                rank=index + 1,
            )
            for index, result in enumerate(scored[:limit])
        ]

    def score(self, query: str) -> List[ColBERTSearchResult]:
        import numpy as np

        query_embedding = list(self.model.query_embed(query))[0]
        results: List[ColBERTSearchResult] = []
        for index, doc_matrix in enumerate(self._doc_embeddings):
            sim_matrix = np.dot(query_embedding, doc_matrix.T)
            max_sim_per_query_token = np.max(sim_matrix, axis=1)
            score = float(np.sum(max_sim_per_query_token))
            results.append(
                ColBERTSearchResult(
                    document=self.documents[index],
                    score=score,
                    rank=index + 1,
                )
            )
        return results

    def rerank(
        self,
        query: str,
        candidates: Sequence[ColBERTDocument | Dict[str, Any]],
        top_n: int = 10,
    ) -> List[ColBERTSearchResult]:
        candidate_index = ColBERTIndex(config=self.config)
        candidate_index.index(candidates)
        return candidate_index.search(query, top_k=top_n)

    def to_dicts(self, results: Sequence[ColBERTSearchResult]) -> List[Dict[str, Any]]:
        return [result.to_dict() for result in results]

    @staticmethod
    def _coerce_document(document: ColBERTDocument | Dict[str, Any]) -> ColBERTDocument:
        if isinstance(document, ColBERTDocument):
            return document
        if isinstance(document, dict):
            return ColBERTDocument.from_mapping(document)
        raise TypeError("document must be a ColBERTDocument or dict")
