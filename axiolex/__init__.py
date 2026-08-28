"""
AxioLex: Multi-modal retrieval primitive for agentic infrastructure (Lexical & Neural).

Currently powered by BM25S + PyStemmer for fast, deterministic lexical retrieval
with a routing layer for LLM tools, documents, and hybrid RAG.
"""

from .core.retriever import BM25SRetriever, retrieve_documents, Document
from .services.indexing_service import IndexingResult, ToolIndexingService
from .services.tool_discovery_service import ToolDiscoveryService, discover_tools

try:
    from .api.client import BM25SClient
    from .api.models import RetrieveRequest, RetrieveResponse
    _HAS_API = True
except ImportError:
    _HAS_API = False
    BM25SClient = None
    RetrieveRequest = None
    RetrieveResponse = None

try:
    from importlib.metadata import version as _pkg_version
    __version__ = _pkg_version("axiolex")
except Exception:
    __version__ = "1.0.8"
__all__ = [
    "BM25SRetriever",
    "retrieve_documents", 
    "BM25SClient",
    "Document",
    "RetrieveRequest",
    "RetrieveResponse",
    "ToolDiscoveryService",
    "discover_tools",
    "IndexingResult",
    "ToolIndexingService",
]
