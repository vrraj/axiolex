"""
Tool merger for combining YAML and MCP-discovered tools.

This module provides functionality to:
- Merge tools from multiple sources (YAML, MCP discovery)
- Deduplicate tools by ID
- Normalize to unified format
- Cache merged results
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .discovery import MCPDiscovery, MCPProviderConfig
from ..core.cache import ToolCacheManager
from ..core.retriever import Document
from ..utils.file_utils import is_source_entry_enabled


@dataclass
class ToolMergeConfig:
    """Configuration for tool merging."""
    yaml_file: str = "source_files/tools_list.yaml"
    mcp_providers: List[MCPProviderConfig] = None
    use_cache: bool = True
    cache_manager: Optional[ToolCacheManager] = None


class ToolMerger:
    """Merge tools from YAML and MCP discovery sources."""
    
    def __init__(self, config: ToolMergeConfig = None):
        """Initialize tool merger."""
        self.config = config or ToolMergeConfig()
        self.yaml_tools: List[Dict[str, Any]] = []
        self.mcp_tools: List[Dict[str, Any]] = []
        self.merged_tools: List[Dict[str, Any]] = []
        self.mcp_discovery: Optional[MCPDiscovery] = None
    
    def load_yaml_tools(self) -> List[Dict[str, Any]]:
        """Load tools from YAML file."""
        import yaml
        import os
        
        if not os.path.exists(self.config.yaml_file):
            print(f"YAML file not found: {self.config.yaml_file}")
            return []
        
        try:
            with open(self.config.yaml_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            documents = data.get('documents', [])
            
            # Convert to discovery format
            yaml_tools = []
            for doc in documents:
                if not is_source_entry_enabled(doc):
                    continue

                runtime = doc.get('runtime', {})
                metadata = doc.get('metadata', {})
                
                yaml_tool = {
                    "id": doc.get('id', ''),
                    "title": doc.get('title', ''),
                    "description": doc.get('content', ''),
                    "tool_name": runtime.get('tool_name', ''),
                    "params": runtime.get('params', {}),
                    "category": metadata.get('category', 'general'),
                    "provider": metadata.get('provider', 'yaml'),
                    "source": "yaml",
                    "runtime": runtime,
                    "artifact": doc.get('artifact', {}),
                    "metadata": metadata
                }
                yaml_tools.append(yaml_tool)
            
            self.yaml_tools = yaml_tools
            print(f"Loaded {len(yaml_tools)} tools from YAML")
            return yaml_tools
            
        except Exception as e:
            print(f"Error loading YAML tools: {e}")
            return []
    
    def discover_mcp_tools(self) -> List[Dict[str, Any]]:
        """Discover tools from MCP providers."""
        if not self.config.mcp_providers:
            print("No MCP providers configured")
            return []

        try:
            self.mcp_discovery = MCPDiscovery(self.config.mcp_providers)
            mcp_tools_dict = self.mcp_discovery.discover_all()

            # Flatten dict to list
            mcp_tools = []
            for provider_id, tools in mcp_tools_dict.items():
                for tool in tools:
                    tool["source"] = "mcp-discovery"
                    mcp_tools.append(tool)

            self.mcp_tools = mcp_tools
            print(f"Discovered {len(mcp_tools)} tools from MCP providers")
            return mcp_tools

        except Exception as e:
            print(f"Error discovering MCP tools: {e}")
            return []
    
    def merge_tools(self) -> List[Dict[str, Any]]:
        """
        Merge tools from YAML and MCP sources.
        
        Returns:
            Merged list of tools with deduplication
        """
        all_tools = []
        
        # Add YAML tools
        all_tools.extend(self.yaml_tools)
        
        # Add MCP tools
        all_tools.extend(self.mcp_tools)
        
        # Deduplicate by ID (YAML takes precedence)
        seen_ids = set()
        merged = []
        
        for tool in all_tools:
            if not is_source_entry_enabled(tool):
                continue

            tool_id = tool.get('id', '')
            if tool_id and tool_id not in seen_ids:
                seen_ids.add(tool_id)
                merged.append(tool)
            elif tool_id in seen_ids:
                # Skip duplicate (YAML version already added)
                pass
        
        self.merged_tools = merged
        print(f"Merged {len(merged)} unique tools from all sources")
        return merged
    
    def cache_merged_tools(self) -> bool:
        """Cache merged tools to Redis."""
        if not self.config.cache_manager or not self.config.use_cache:
            return False
        
        try:
            discovery_list = []
            runtime_list = []
            
            for tool in self.merged_tools:
                if not is_source_entry_enabled(tool):
                    continue

                # Cache discovery data
                discovery_list.append({
                    "id": tool["id"],
                    "title": tool["title"],
                    "description": tool["description"],
                    "tool_name": tool.get("tool_name", ""),
                    "params": tool["params"],
                    "category": tool["category"],
                    "provider": tool["provider"]
                })
                
                # Cache runtime data
                runtime_data = {
                    "transport": tool.get("runtime", {}).get("transport", ""),
                    "tool_name": tool.get("runtime", {}).get("tool_name", ""),
                    "endpoint": tool.get("runtime", {}).get("endpoint", {}),
                    "params": tool["params"]
                }
                
                runtime_list.append({
                    "id": tool["id"],
                    "runtime": runtime_data
                })
            
            # Cache to Redis
            discovery_count = self.config.cache_manager.cache_all_discovery(discovery_list)
            runtime_count = self.config.cache_manager.cache_all_runtime(runtime_list)
            
            print(f"Cached {discovery_count} discovery entries and {runtime_count} runtime entries to Redis")
            return True
            
        except Exception as e:
            print(f"Error caching merged tools: {e}")
            return False
    
    def merge_and_cache(self) -> List[Dict[str, Any]]:
        """
        Load, merge, and cache tools from all sources.
        
        Returns:
            Merged list of tools
        """
        # Load from all sources
        self.load_yaml_tools()
        self.discover_mcp_tools()
        
        # Merge
        merged = self.merge_tools()
        
        # Cache
        if self.config.use_cache:
            self.cache_merged_tools()
        
        return merged
    
    def convert_to_documents(self) -> List[Document]:
        """
        Convert merged tools to Document objects for BM25S indexing.
        
        Returns:
            List of Document objects
        """
        documents = []
        
        for tool in self.merged_tools:
            if not is_source_entry_enabled(tool):
                continue

            doc = Document(
                id=tool["id"],
                title=tool["title"],
                content=tool["content"],
                keywords=tool.get("keywords", []),
                metadata={
                    "category": tool["category"],
                    "provider": tool["provider"],
                    "source": tool.get("source", "unknown")
                },
                runtime=tool.get("runtime", {}),
                artifact=tool.get("artifact", {}),
                params=tool["params"]
            )
            documents.append(doc)
        
        return documents
    
    def close(self):
        """Close resources."""
        if self.mcp_discovery:
            self.mcp_discovery.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
