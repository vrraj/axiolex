"""
Pydantic models for BM25S retriever API.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class Document(BaseModel):
    """Document model for API."""

    id: str = Field(..., description="Document identifier")
    title: str = Field(..., description="Document title")
    content: str = Field(..., description="Document content")
    keywords: List[str] = Field(default_factory=list, description="Document keywords")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
    runtime: Dict[str, Any] = Field(
        default_factory=dict,
        description="Runtime configuration (provider, transport, endpoint, params)",
    )
    artifact: Dict[str, Any] = Field(
        default_factory=dict,
        description="Artifact configuration (produces_artifact, artifact_type, placeholder)",
    )
    params: Dict[str, Any] = Field(
        default_factory=dict, description="Tool params schema"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "doc1",
                "title": "Stock Market Data",
                "content": "Real-time stock quotes and market data analysis",
                "keywords": ["stock", "market", "quote", "analysis"],
                "metadata": {"source": "financial_api", "updated": "2025-04-07"},
                "runtime": {
                    "provider": "internal",
                    "transport": "http",
                    "endpoint": "/api/stocks",
                },
                "artifact": {"produces_artifact": False},
                "params": {"symbol": {"type": "string"}},
            }
        }
    )


class RetrieveRequest(BaseModel):
    """Request model for document retrieval."""

    query: str = Field(..., description="Search query", min_length=1)
    temperature: Optional[float] = Field(
        None, ge=0.1, le=10.0, description="Softmax temperature"
    )
    ignore_zero: Optional[bool] = Field(
        None, description="Filter zero-relevance documents"
    )
    llm_tools_cutoff: Optional[float] = Field(
        None, ge=0.0, le=100.0, description="Cutoff percentage"
    )
    hybrid_search: Optional[bool] = Field(
        None,
        description="None = deployment default (hybrid if AXIOLEX_HYBRID_ENABLED, else lexical). True = force hybrid. False = force lexical.",
    )
    top_k: Optional[int] = Field(
        None, ge=1, le=1000,
        description="Maximum number of results Axiolex returns. The calling application decides how many enter LLM context.",
    )
    max_results: Optional[int] = Field(
        None, ge=1, le=1000,
        description="Deprecated alias for top_k",
    )
    bm25_weight: Optional[float] = Field(
        None,
        ge=0.0,
        description="BM25 weight for hybrid score fusion",
    )
    colbert_weight: Optional[float] = Field(
        None,
        ge=0.0,
        description="ColBERT weight for hybrid score fusion",
    )
    candidate_limit: Optional[int] = Field(
        None,
        ge=1,
        le=1000,
        description="Per-model candidate count used before hybrid fusion",
    )
    min_hybrid_score: Optional[float] = Field(
        None,
        ge=0.0,
        description="Minimum fused hybrid score for hybrid-search results",
    )
    min_rrf_score: Optional[float] = Field(
        None,
        ge=0.0,
        description="Deprecated alias for min_hybrid_score",
    )
    namespaces: Optional[List[str]] = Field(
        None,
        description="Restrict retrieval to capabilities in these namespaces.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "stock market data",
                "temperature": 0.7,
                "ignore_zero": True,
                "llm_tools_cutoff": 8.0,
            }
        }
    )


class RetrievedDocument(BaseModel):
    """Retrieved document with scores."""

    id: str
    title: str
    content: str
    keywords: List[str]
    metadata: Dict[str, Any]
    runtime: Dict[str, Any] = Field(default_factory=dict)
    artifact: Dict[str, Any] = Field(default_factory=dict)
    params: Dict[str, Any] = Field(default_factory=dict)
    rank: Optional[int] = None
    relevance_score: Optional[float] = None
    bm25_score: Optional[float] = None
    softmax_score: Optional[float] = None
    bm25_rank: Optional[int] = None
    bm25_softmax_score: Optional[float] = None
    colbert_score: Optional[float] = None
    colbert_rank: Optional[int] = None
    colbert_softmax_score: Optional[float] = None
    hybrid_score: Optional[float] = None
    rrf_score: Optional[float] = None


class RetrieveResponse(BaseModel):
    """Response model for document retrieval."""

    success: bool
    message: str
    documents: List[RetrievedDocument]
    total_retrieved: int
    cutoff_percentage: float
    settings: Dict[str, Any]
    search_mode: str = "lexical"

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Retrieved 3 documents",
                "documents": [
                    {
                        "id": "doc1",
                        "title": "Stock Market Data",
                        "content": "Real-time stock quotes...",
                        "keywords": ["stock", "market"],
                        "metadata": {},
                        "bm25_score": 2.5,
                        "softmax_score": 0.45,
                    }
                ],
                "total_retrieved": 3,
                "cutoff_percentage": 0.08,
                "settings": {
                    "temperature": 0.7,
                    "ignore_zero": True,
                    "llm_tools_cutoff": 8.0,
                },
            }
        }
    )


class IndexRequest(BaseModel):
    """Request model for building index."""

    documents: List[Document] = Field(..., description="Documents to index")
    rebuild: bool = Field(default=True, description="Rebuild entire index")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "documents": [
                    {
                        "id": "doc1",
                        "title": "Stock Market Data",
                        "content": "Real-time stock quotes...",
                        "keywords": ["stock", "market"],
                    }
                ],
                "rebuild": True,
            }
        }
    )


class IndexResponse(BaseModel):
    """Response model for index building."""

    success: bool
    message: str
    document_count: int
    index_time_ms: Optional[float] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Index built successfully",
                "document_count": 10,
                "index_time_ms": 150.5,
            }
        }
    )


class BM25SSettings(BaseModel):
    """BM25S settings model."""

    temperature: float = Field(default=0.7, ge=0.1, le=10.0)
    ignore_zero: bool = Field(default=True)
    llm_tools_cutoff: float = Field(default=8.0, ge=0.0, le=100.0)


class SettingsResponse(BaseModel):
    """Response model for settings."""

    bm25s: BM25SSettings
    documents: Dict[str, Any]
    server: Dict[str, Any]
    hybrid_search: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "bm25s": {
                    "temperature": 0.7,
                    "ignore_zero": True,
                    "llm_tools_cutoff": 8.0,
                },
                "documents": {
                    "source": "documents.yaml",
                    "auto_reload": True,
                    "encoding": "utf-8",
                },
                "server": {
                    "host": "0.0.0.0",
                    "port": 8000,
                    "reload": False,
                    "log_level": "info",
                },
            }
        }
    )


class ErrorResponse(BaseModel):
    """Error response model."""

    success: bool = False
    error: str
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": False,
                "error": "ValidationError",
                "message": "Query is required",
                "details": {"field": "query", "issue": "min_length"},
            }
        }
    )
