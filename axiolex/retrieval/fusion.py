from __future__ import annotations

import math
from typing import Any, Iterable


def reciprocal_rank_fusion(
    lexical: Iterable[dict[str, Any]],
    semantic: Iterable[dict[str, Any]],
    rrf_k: int = 60,
) -> list[dict[str, Any]]:
    """Fuse lexical and semantic rankings using reciprocal rank fusion."""
    fused: dict[str, dict[str, Any]] = {}
    _merge_ranking(fused, lexical, "bm25", rrf_k)
    _merge_ranking(fused, semantic, "colbert", rrf_k)
    return sorted(
        fused.values(),
        key=lambda item: (-item["rrf_score"], item["id"]),
    )


def _merge_ranking(
    fused: dict[str, dict[str, Any]],
    ranking: Iterable[dict[str, Any]],
    source: str,
    rrf_k: int,
) -> None:
    for rank, item in enumerate(ranking, start=1):
        doc_id = str(item["id"])
        result = fused.setdefault(
            doc_id,
            {
                "id": doc_id,
                "document": item.get("document"),
                "bm25_score": None,
                "bm25_rank": None,
                "colbert_score": None,
                "colbert_rank": None,
                "rrf_score": 0.0,
            },
        )
        if result["document"] is None:
            result["document"] = item.get("document")
        result[f"{source}_score"] = item.get("score")
        result[f"{source}_rank"] = rank
        result["rrf_score"] += 1.0 / (rrf_k + rank)


def softmax_score_fusion(
    lexical: Iterable[dict[str, Any]],
    semantic: Iterable[dict[str, Any]],
    temperature: float = 1.0,
    bm25_weight: float = 0.4,
    colbert_weight: float = 0.6,
) -> list[dict[str, Any]]:
    """Fuse lexical and semantic scores after per-model softmax normalization."""
    if temperature <= 0:
        raise ValueError("temperature must be greater than 0")
    if bm25_weight < 0 or colbert_weight < 0:
        raise ValueError("hybrid weights must be greater than or equal to 0")

    total_weight = bm25_weight + colbert_weight
    if total_weight <= 0:
        raise ValueError("at least one hybrid weight must be greater than 0")
    bm25_weight = bm25_weight / total_weight
    colbert_weight = colbert_weight / total_weight

    lexical_items = list(lexical)
    semantic_items = list(semantic)
    bm25_probs = _softmax(
        [float(item.get("score", 0.0)) for item in lexical_items], temperature
    )
    colbert_probs = _softmax(
        [float(item.get("score", 0.0)) for item in semantic_items],
        temperature,
    )

    fused: dict[str, dict[str, Any]] = {}
    _merge_probability_ranking(fused, lexical_items, bm25_probs, "bm25")
    _merge_probability_ranking(fused, semantic_items, colbert_probs, "colbert")

    for item in fused.values():
        item["hybrid_score"] = (
            bm25_weight * item["bm25_softmax_score"]
            + colbert_weight * item["colbert_softmax_score"]
        )

    return sorted(
        fused.values(),
        key=lambda item: (-item["hybrid_score"], item["id"]),
    )


def _softmax(scores: list[float], temperature: float) -> list[float]:
    if not scores:
        return []
    scaled_scores = [score / temperature for score in scores]
    max_score = max(scaled_scores)
    exp_scores = [math.exp(score - max_score) for score in scaled_scores]
    total = sum(exp_scores)
    if total == 0:
        return [0.0] * len(scores)
    return [score / total for score in exp_scores]


def _merge_probability_ranking(
    fused: dict[str, dict[str, Any]],
    ranking: Iterable[dict[str, Any]],
    probabilities: Iterable[float],
    source: str,
) -> None:
    for rank, (item, probability) in enumerate(zip(ranking, probabilities), start=1):
        doc_id = str(item["id"])
        result = fused.setdefault(
            doc_id,
            {
                "id": doc_id,
                "document": item.get("document"),
                "bm25_score": None,
                "bm25_rank": None,
                "bm25_softmax_score": 0.0,
                "colbert_score": None,
                "colbert_rank": None,
                "colbert_softmax_score": 0.0,
                "hybrid_score": 0.0,
            },
        )
        if result["document"] is None:
            result["document"] = item.get("document")
        result[f"{source}_score"] = item.get("score")
        result[f"{source}_rank"] = rank
        result[f"{source}_softmax_score"] = probability
