"""
AxioLex: Multi-modal retrieval primitive for agentic infrastructure (Lexical & Neural).

Currently powered by BM25S + PyStemmer for fast, deterministic lexical retrieval
with a routing layer for LLM tools, documents, and hybrid RAG.
"""

# The thin SDK client is always available (only needs httpx + pydantic).
from .sdk import Axiolex, AxiolexError

# Server-side imports are conditional — they require the [server] extra.
try:
    from .core.retriever import BM25SRetriever, retrieve_documents, Document
    from .services.indexing_service import IndexingResult, ToolIndexingService
    from .services.tool_discovery_service import ToolDiscoveryService, discover_tools
    from .mcp.execution import ToolExecutionService, execute_tool
    _HAS_SERVER = True
except ImportError:
    _HAS_SERVER = False
    BM25SRetriever = None
    retrieve_documents = None
    Document = None
    IndexingResult = None
    ToolIndexingService = None
    ToolDiscoveryService = None
    discover_tools = None
    ToolExecutionService = None
    execute_tool = None

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
    __version__ = "1.0.9"

__all__ = [
    "Axiolex",
    "AxiolexError",
    "BM25SRetriever",
    "retrieve_documents",
    "BM25SClient",
    "Document",
    "RetrieveRequest",
    "RetrieveResponse",
    "ToolDiscoveryService",
    "discover_tools",
    "ToolExecutionService",
    "execute_tool",
    "IndexingResult",
    "ToolIndexingService",
]
