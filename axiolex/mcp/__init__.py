"""
MCP (Model Context Protocol) client and discovery module.

This module provides functionality for discovering and interacting with MCP servers
to retrieve tool definitions and execute tool calls.
"""

from .discovery import MCPDiscovery, MCPProviderConfig
from .client import MCPClient
from .server import create_mcp_server

__all__ = ["MCPDiscovery", "MCPProviderConfig", "MCPClient", "create_mcp_server"]
