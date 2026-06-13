"""Document database operations using Redis cache."""

from typing import Dict, Any, List
from ..core.cache import get_cache_manager
from ..core.retriever import get_retriever


def get_documents_from_cache() -> Dict[str, Any]:
    """Get all documents from Redis cache with fallback to retriever."""
    cache_manager = get_cache_manager()
    retriever = get_retriever()
    
    if cache_manager.is_connected():
        retriever.refresh_local_yaml_cache()
        discovery_tools = cache_manager.get_all_discovery()
        documents = []
        
        for tool in discovery_tools:
            provider = tool.get("provider", "unknown")
            tool_type = "mcp" if provider != "yaml" and provider != "unknown" else "local"
            
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
            tool_type = "mcp" if provider != "yaml" and provider != "unknown" else "local"
            
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
            "source": "retriever"
        }
