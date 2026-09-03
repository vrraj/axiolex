"""Document database operations using Redis cache."""

from typing import Dict, Any
from ..core.cache import get_cache_manager
from ..core.retriever import get_retriever


def get_documents_from_cache() -> Dict[str, Any]:
    """Get all documents from Redis cache with fallback to retriever."""
    cache_manager = get_cache_manager()
    retriever = get_retriever()
    
    if cache_manager.is_connected():
        discovery_tools = cache_manager.get_all_discovery()
        documents = []
        
        for tool in discovery_tools:
            provider = tool.get("provider", "unknown")
            runtime = cache_manager.get_runtime(tool["id"]) or {}
            transport = runtime.get("transport", "")
            tool_type = _tool_type(provider, tool.get("source"), transport)
            
            documents.append({
                "id": tool["id"],
                "title": tool["title"],
                "description": tool["description"],
                "tool_name": tool.get("tool_name", ""),
                "params": tool["params"],
                "category": tool["category"],
                "provider": provider,
                "type": tool_type
            })
        
        return {
            "success": True,
            "documents": documents,
            "count": len(documents),
            "source": "redis_cache"
        }
    else:
        documents = []
        for doc in retriever.documents:
            provider = doc.metadata.get("provider", "unknown")
            transport = doc.runtime.get("transport", "")
            tool_type = _tool_type(provider, doc.metadata.get("source"), transport)
            
            documents.append({
                "id": doc.id,
                "title": doc.title,
                "description": doc.content,
                "tool_name": doc.runtime.get("tool_name", ""),
                "params": doc.params,
                "category": doc.metadata.get("category", "general"),
                "provider": provider,
                "type": tool_type
            })
        
        return {
            "success": True,
            "documents": documents,
            "count": len(documents),
            "source": "retriever",
            "warning": (
                "Redis tool catalog is unavailable. Showing local retriever "
                "documents only; MCP-discovered tools may be missing."
            ),
        }


def _tool_type(provider: str, source: str = "", transport: str = "") -> str:
    if transport == "a2a":
        return "a2a"
    if source == "mcp-discovery":
        return "mcp"
    if source in {"yaml", "local_yaml", "ui"}:
        return "local"
    return "mcp" if provider not in {"yaml", "unknown"} else "local"
