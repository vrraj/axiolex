"""
Alpha Vantage MCP adapter for provider-specific discovery logic.

This module handles Alpha Vantage's unique MCP pattern:
- tools/list returns meta-tools (TOOL_GET, TOOL_CALL)
- TOOL_LIST enumerates available tools
- TOOL_GET gets tool schemas
- TOOL_CALL executes tools
"""

import re
from typing import Dict, Any, List, Optional
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from .discovery import MCPProviderConfig


class AlphaVantageAdapter:
    """Alpha Vantage-specific MCP discovery adapter."""

    def __init__(self, config: MCPProviderConfig):
        """Initialize adapter with provider config."""
        self.config = config
        self.session = None

    async def discover_tools(self) -> List[Dict[str, Any]]:
        """
        Discover tools from Alpha Vantage MCP server using standard MCP client.

        Flow:
        1. Connect via streamable-http and initialize session
        2. Call tools/list to get meta-tools
        3. Call TOOL_LIST to enumerate available tools (limited by max_page_size)
        4. Get schema for each tool via TOOL_GET
        5. Normalize to unified format

        Returns:
            List of discovered tools in unified format
        """
        tools = []

        try:
            # Build URL with auth if needed
            url = self.config.endpoint
            if self.config.auth.type == "api_key" and self.config.auth.secret_value:
                if "?" in url:
                    url += f"&apikey={self.config.auth.secret_value}"
                else:
                    url += f"?apikey={self.config.auth.secret_value}"

            # Check for environment variable if secret_value is not set
            if self.config.auth.type == "api_key" and not self.config.auth.secret_value and self.config.auth.secret_env:
                import os
                api_key = os.getenv(self.config.auth.secret_env)
                if api_key:
                    if "?" in url:
                        url += f"&apikey={api_key}"
                    else:
                        url += f"?apikey={api_key}"
                    print(f"Using API key from environment variable: {self.config.auth.secret_env}")
                else:
                    print(f"WARNING: API key environment variable {self.config.auth.secret_env} not set")

            print(f"Connecting to Alpha Vantage MCP server: {url}")

            # Connect using standard MCP client with manual context management
            streamable_ctx = streamable_http_client(url)
            read, write, _ = await streamable_ctx.__aenter__()

            try:
                session = ClientSession(read, write)
                await session.__aenter__()
                await session.initialize()
                self.session = session

                print("Session initialized successfully")

                # Step 1: Get meta-tools via tools/list
                print("Step 1: Getting meta-tools via tools/list...")
                tools_response = await session.list_tools()
                meta_tools = [{"name": t.name, "description": t.description} for t in tools_response.tools]
                print(f"Found meta-tools: {[t['name'] for t in meta_tools]}")

                # Step 2: Enumerate available tools via TOOL_LIST
                print("Step 2: Enumerating available tools via TOOL_LIST...")
                available_tools = await self._enumerate_tools_async(session)
                max_tools = self.config.limits.max_page_size
                print(f"Found {len(available_tools)} total tools, limiting to {max_tools}")

                # Limit tools based on max_page_size
                tools_to_process = available_tools[:max_tools]
                print(f"Processing {len(tools_to_process)} tools")

                # Step 3: Get schema for each tool via TOOL_GET
                print(f"Getting detailed schema for {len(tools_to_process)} tools")

                # Get schema for all tools
                for tool_name in tools_to_process:
                    print(f"  Getting schema for {tool_name}...")
                    schema = await self._get_tool_schema_async(session, tool_name)
                    normalized = self._normalize_tool(tool_name, schema or {})
                    if normalized:
                        tools.append(normalized)

                print(f"Successfully discovered {len(tools)} tools")

                # Close session
                await session.__aexit__(None, None, None)

            finally:
                # Close streamable context
                await streamable_ctx.__aexit__(None, None, None)

        except Exception as e:
            print(f"Alpha Vantage discovery error: {e}")
            import traceback
            traceback.print_exc()

        return tools

    async def _enumerate_tools_async(self, session: ClientSession) -> List[str]:
        """
        Enumerate available tools by calling TOOL_LIST via MCP client.
        Falls back to known Alpha Vantage tools if enumeration fails.

        Returns:
            List of tool names
        """
        try:
            # Call TOOL_LIST to enumerate tools
            result = await session.call_tool("TOOL_LIST", {})

            # Extract tool names from response
            available_tools = []
            if hasattr(result, 'content'):
                content = result.content
                if isinstance(content, list) and len(content) > 0:
                    for item in content:
                        if hasattr(item, 'text'):
                            text = item.text
                            # Extract tool names (uppercase with underscores)
                            tool_matches = re.findall(r'[A-Z_]+', text)
                            available_tools.extend(tool_matches)

            # Remove duplicates and filter common non-tool names
            available_tools = list(set(available_tools))
            available_tools = [t for t in available_tools if len(t) > 3 and '_' in t]

            if available_tools:
                return sorted(available_tools)

        except Exception as e:
            print(f"TOOL_LIST enumeration failed: {e}")

        # No tools found
        print("No tools discovered via TOOL_LIST")
        return []

    async def _get_tool_schema_async(self, session: ClientSession, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get schema for a specific tool via TOOL_GET using MCP client."""
        try:
            result = await session.call_tool("TOOL_GET", {"tool_name": tool_name})

            # Convert result to dict format
            if hasattr(result, 'content'):
                return {"content": result.content}
            return {"result": str(result)}

        except Exception as e:
            print(f"TOOL_GET for {tool_name} failed: {e}")
            return None

    def _normalize_tool(self, tool_name: str, schema: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize Alpha Vantage tool to unified format."""
        try:
            import json
            import ast

            # Extract description from schema
            description = ""
            params = {}

            if "content" in schema:
                content = schema["content"]
                if isinstance(content, list) and len(content) > 0:
                    for item in content:
                        # Handle both dict and TextContent objects
                        text_value = None
                        if isinstance(item, dict) and "text" in item:
                            text_value = item["text"]
                        elif hasattr(item, 'text'):
                            text_value = item.text

                        if text_value:
                            # Try to parse as JSON (Alpha Vantage returns JSON string with single quotes)
                            try:
                                # First try json.loads (for valid JSON with double quotes)
                                tool_data = json.loads(text_value)
                            except json.JSONDecodeError:
                                # If that fails, try ast.literal_eval (for Python dict syntax with single quotes)
                                try:
                                    tool_data = ast.literal_eval(text_value)
                                except (ValueError, SyntaxError) as e:
                                    print(f"Failed to parse for {tool_name}: {e}")
                                    tool_data = None

                            if tool_data and isinstance(tool_data, dict):
                                description = tool_data.get('description', '')
                                params = tool_data.get('parameters', {})
                                break

            # If description is still empty, use tool name as fallback
            if not description:
                description = f"Alpha Vantage {tool_name.replace('_', ' ').lower()}"

            # Determine category
            category = self._infer_category(tool_name)

            return {
                "id": f"{self.config.id}:{tool_name}",
                "title": tool_name,
                "description": description,
                "tool_name": tool_name,
                "params": params,
                "category": category,
                "provider": self.config.id,
                "mcp_tool": schema
            }

        except Exception as e:
            print(f"Error normalizing tool {tool_name}: {e}")
            return None

    def _infer_category(self, tool_name: str) -> str:
        """Infer category from tool name."""
        name_lower = tool_name.lower()

        if "time_series" in name_lower or "quote" in name_lower or "price" in name_lower:
            return "finance"
        elif "forex" in name_lower or "currency" in name_lower or "exchange" in name_lower:
            return "finance"
        elif "crypto" in name_lower or "digital" in name_lower:
            return "finance"
        elif "news" in name_lower or "sentiment" in name_lower:
            return "news"
        elif "earnings" in name_lower or "income" in name_lower:
            return "finance"

        return "general"
