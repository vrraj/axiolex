"""
MCP client for executing tool calls on MCP servers.

This module provides functionality to:
- Execute tool calls on MCP servers
- Handle different transport methods (HTTP, streamable-http, stdio)
- Map params to JSON-RPC format
- Return results in unified format
"""

import httpx
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .discovery import MCPProvider, MCPProviderConfig


@dataclass
class MCPExecutionResult:
    """Result of MCP tool execution."""
    success: bool
    tool_id: str
    result: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class MCPClient:
    """MCP client for executing tool calls."""
    
    def __init__(self, providers: List[MCPProviderConfig] = None):
        """Initialize MCP client with provider configurations."""
        self.providers = providers or []
        self.client = httpx.Client(timeout=30.0)
    
    def add_provider(self, config: MCPProviderConfig):
        """Add a provider configuration."""
        self.providers.append(config)
    
    def execute_tool(self, tool_id: str, arguments: Dict[str, Any]) -> MCPExecutionResult:
        """
        Execute a tool call on the appropriate MCP server.
        
        Args:
            tool_id: Tool identifier (format: provider:tool_name)
            arguments: Tool arguments
            
        Returns:
            Execution result
        """
        # Parse tool_id to get provider and tool_name
        parts = tool_id.split(":", 1)
        if len(parts) != 2:
            return MCPExecutionResult(
                success=False,
                tool_id=tool_id,
                error=f"Invalid tool_id format: {tool_id}"
            )
        
        provider_name, tool_name = parts
        provider = self._get_provider_by_name(provider_name)
        
        if not provider:
            return MCPExecutionResult(
                success=False,
                tool_id=tool_id,
                error=f"Provider not configured: {provider_name}"
            )
        
        try:
            if provider.transport == "http":
                return self._execute_http(provider, tool_name, arguments)
            elif provider.transport == "streamable-http":
                return self._execute_streamable_http(provider, tool_name, arguments)
            else:
                return MCPExecutionResult(
                    success=False,
                    tool_id=tool_id,
                    error=f"Transport {provider.transport} not yet implemented"
                )
        except Exception as e:
            return MCPExecutionResult(
                success=False,
                tool_id=tool_id,
                error=str(e)
            )
    
    def _get_provider_by_name(self, provider_name: str) -> Optional[MCPProviderConfig]:
        """Get provider configuration by name."""
        for config in self.providers:
            if config.provider.value == provider_name:
                return config
        return None
    
    def _execute_http(self, config: MCPProviderConfig, tool_name: str, arguments: Dict[str, Any]) -> MCPExecutionResult:
        """Execute tool using HTTP POST with JSON-RPC."""
        try:
            # Build JSON-RPC payload
            payload = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                },
                "id": 1
            }
            
            # Add API key if configured
            params = {}
            if config.api_key:
                params["apikey"] = config.api_key
            
            response = self.client.post(
                config.base_url,
                json=payload,
                headers={"Content-Type": "application/json", **config.headers},
                params=params
            )
            
            if response.status_code != 200:
                return MCPExecutionResult(
                    success=False,
                    tool_id=f"{config.provider.value}:{tool_name}",
                    error=f"HTTP error {response.status_code}: {response.text}"
                )
            
            result = response.json()
            
            # Check for JSON-RPC error
            if "error" in result:
                return MCPExecutionResult(
                    success=False,
                    tool_id=f"{config.provider.value}:{tool_name}",
                    error=result["error"].get("message", "Unknown error")
                )
            
            # Return successful result
            return MCPExecutionResult(
                success=True,
                tool_id=f"{config.provider.value}:{tool_name}",
                result=result.get("result"),
                metadata={"status_code": response.status_code}
            )
            
        except Exception as e:
            return MCPExecutionResult(
                success=False,
                tool_id=f"{config.provider.value}:{tool_name}",
                error=str(e)
            )
    
    def _execute_streamable_http(self, config: MCPProviderConfig, tool_name: str, arguments: Dict[str, Any]) -> MCPExecutionResult:
        """Execute tool using streamable-http transport (not yet implemented)."""
        return MCPExecutionResult(
            success=False,
            tool_id=f"{config.provider.value}:{tool_name}",
            error="Streamable-http execution not yet implemented"
        )
    
    def execute_batch(self, tool_calls: List[Dict[str, Any]]) -> List[MCPExecutionResult]:
        """
        Execute multiple tool calls in batch.
        
        Args:
            tool_calls: List of tool call dicts with keys:
                - tool_id: Tool identifier
                - arguments: Tool arguments
                
        Returns:
            List of execution results
        """
        results = []
        for call in tool_calls:
            result = self.execute_tool(call["tool_id"], call["arguments"])
            results.append(result)
        return results
    
    def close(self):
        """Close HTTP client."""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
