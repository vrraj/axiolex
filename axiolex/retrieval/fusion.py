from __future__ import annotations

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
