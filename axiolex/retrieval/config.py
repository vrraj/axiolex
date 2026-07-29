from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from .colbert import DEFAULT_COLBERT_MODEL


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class HybridSearchSettings:
    """Configuration for the optional BM25 + ColBERT retrieval path."""

    enabled: bool = False
    model_name: str = DEFAULT_COLBERT_MODEL
    cache_dir: Optional[str] = None
    batch_size: int = 32
    candidate_limit: int = 100
    rrf_k: int = 60
    bm25_weight: float = 0.4
    colbert_weight: float = 0.6

    @classmethod
    def from_env(cls) -> "HybridSearchSettings":
        return cls(
            enabled=_env_bool("AXIOLEX_HYBRID_ENABLED"),
            model_name=os.getenv("AXIOLEX_COLBERT_MODEL", DEFAULT_COLBERT_MODEL),
            cache_dir=os.getenv("AXIOLEX_COLBERT_CACHE_DIR"),
            batch_size=int(os.getenv("AXIOLEX_COLBERT_BATCH_SIZE", "32")),
            candidate_limit=int(os.getenv("AXIOLEX_HYBRID_CANDIDATE_LIMIT", "100")),
            rrf_k=int(os.getenv("AXIOLEX_RRF_K", "60")),
            bm25_weight=float(os.getenv("AXIOLEX_HYBRID_BM25_WEIGHT", "0.4")),
            colbert_weight=float(os.getenv("AXIOLEX_HYBRID_COLBERT_WEIGHT", "0.6")),
        )

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "model": self.model_name,
            "cache_dir": self.cache_dir,
            "batch_size": self.batch_size,
            "candidate_limit": self.candidate_limit,
            "rrf_k": self.rrf_k,
            "bm25_weight": self.bm25_weight,
            "colbert_weight": self.colbert_weight,
        }
