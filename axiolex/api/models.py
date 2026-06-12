"""
Pydantic models for BM25S retriever API.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class Document(BaseModel):
    """Document model for API."""
    id: str = Field(..., description="Document identifier")
    title: str = Field(..., description="Document title")
    content: str = Field(..., description="Document content")
    keywords: List[str] = Field(default_factory=list, description="Document keywords")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    runtime: Dict[str, Any] = Field(default_factory=dict, description="Runtime configuration (provider, transport, endpoint, parameters)")
    artifact: Dict[str, Any] = Field(default_factory=dict, description="Artifact configuration (produces_artifact, artifact_type, placeholder)")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Tool parameters schema")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "doc1",
                "title": "Stock Market Data",
                "content": "Real-time stock quotes and market data analysis",
                "keywords": ["stock", "market", "quote", "analysis"],
                "metadata": {"source": "financial_api", "updated": "2025-04-07"},
                "runtime": {
                    "provider": "internal",
                    "transport": "http",
                    "endpoint": "/api/stocks"
                },
                "artifact": {
                    "produces_artifact": False
                },
                "parameters": {
                    "symbol": {"type": "string"}
                }
            }
        }


class RetrieveRequest(BaseModel):
    """Request model for document retrieval."""
    query: str = Field(..., description="Search query", min_length=1)
    temperature: Optional[float] = Field(None, ge=0.1, le=10.0, description="Softmax temperature")
    ignore_zero: Optional[bool] = Field(None, description="Filter zero-relevance documents")
    llm_tools_cutoff: Optional[float] = Field(None, ge=0.0, le=100.0, description="Cutoff percentage")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "stock market data",
                "temperature": 0.7,
                "ignore_zero": True,
                "llm_tools_cutoff": 8.0
            }
        }


class RetrievedDocument(BaseModel):
    """Retrieved document with scores."""
    id: str
    title: str
    content: str
    keywords: List[str]
    metadata: Dict[str, Any]
    runtime: Dict[str, Any] = Field(default_factory=dict)
    artifact: Dict[str, Any] = Field(default_factory=dict)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    bm25_score: float
    softmax_score: float


class RetrieveResponse(BaseModel):
    """Response model for document retrieval."""
    success: bool
    message: str
    documents: List[RetrievedDocument]
    total_retrieved: int
    cutoff_percentage: float
    settings: Dict[str, Any]
    
    class Config:
        json_schema_extra = {
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
                        "softmax_score": 0.45
                    }
                ],
                "total_retrieved": 3,
                "cutoff_percentage": 0.08,
                "settings": {
                    "temperature": 0.7,
                    "ignore_zero": True,
                    "llm_tools_cutoff": 8.0
                }
            }
        }


class IndexRequest(BaseModel):
    """Request model for building index."""
    documents: List[Document] = Field(..., description="Documents to index")
    rebuild: bool = Field(default=True, description="Rebuild entire index")
    
    class Config:
        json_schema_extra = {
            "example": {
                "documents": [
                    {
                        "id": "doc1",
                        "title": "Stock Market Data",
                        "content": "Real-time stock quotes...",
                        "keywords": ["stock", "market"]
                    }
                ],
                "rebuild": True
            }
        }


class IndexResponse(BaseModel):
    """Response model for index building."""
    success: bool
    message: str
    document_count: int
    index_time_ms: Optional[float] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Index built successfully",
                "document_count": 10,
                "index_time_ms": 150.5
            }
        }


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
    
    class Config:
        json_schema_extra = {
            "example": {
                "bm25s": {
                    "temperature": 0.7,
                    "ignore_zero": True,
                    "llm_tools_cutoff": 8.0
                },
                "documents": {
                    "source": "documents.yaml",
                    "auto_reload": True,
                    "encoding": "utf-8"
                },
                "server": {
                    "host": "0.0.0.0",
                    "port": 8000,
                    "reload": False,
                    "log_level": "info"
                }
            }
        }


class ErrorResponse(BaseModel):
    """Error response model."""
    success: bool = False
    error: str
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": "ValidationError",
                "message": "Query is required",
                "details": {"field": "query", "issue": "min_length"}
            }
        }
