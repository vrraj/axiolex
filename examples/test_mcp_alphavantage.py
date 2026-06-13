#!/usr/bin/env python3
"""
Test script for MCP client with Alpha Vantage service.

This script demonstrates how to connect to the Alpha Vantage MCP server,
list available tools, and call a tool to get stock quotes.
"""

import asyncio
import os
import json
import httpx
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client

# Load environment variables
load_dotenv()

# Get API key from environment
ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")

if not ALPHAVANTAGE_API_KEY:
    raise ValueError("ALPHAVANTAGE_API_KEY not found in environment variables")

# Try streamable-http transport first (the original approach)
MCP_URL = f"https://mcp.alphavantage.co/mcp?apikey={ALPHAVANTAGE_API_KEY}"
MCP_BASE_URL = "https://mcp.alphavantage.co/mcp"


async def run_mcp_client_streamable_http():
    """Run MCP client using streamable-http transport."""
    print(f"Connecting to Alpha Vantage MCP server via streamable-http...")
    print(f"URL: {MCP_URL}")
    print()
    
    try:
        async with streamable_http_client(MCP_URL) as (read, write):
            async with ClientSession(read, write) as session:
                print("Initializing session...")
                await session.initialize()
                print("Session initialized successfully")
                print()
                
                print("Listing available tools...")
                tools_list = await session.list_tools()
                print(f"Available Tools: {[t.name for t in tools_list.tools]}")
                print()
                
                print("Tool Details:")
                for tool in tools_list.tools:
                    print(f"  - {tool.name}")
                    if tool.description:
                        print(f"    Description: {tool.description}")
                print()
                
                print("Calling get_stock_quote tool for IBM...")
                result = await session.call_tool(
                    "get_stock_quote", 
                    arguments={"symbol": "IBM"}
                )
                print(f"Result: {result.content}")
                print()
                
    except Exception as e:
        print(f"Streamable-http Error: {e}")
        return False
    
    return True


async def run_mcp_client_http():
    """Run MCP client using standard MCP client (streamable-http)."""
    print(f"Connecting to Alpha Vantage MCP server via standard MCP client...")
    print(f"URL: {MCP_URL}")
    print()

    try:
        # Connect using standard MCP client
        read, write, _ = await streamable_http_client(MCP_URL).__aenter__()
        session = ClientSession(read, write)
        await session.__aenter__()
        await session.initialize()
        print("Session initialized successfully")
        print()

        # Step 1: List tools
        print("Step 1: Listing available tools...")
        tools_response = await session.list_tools()
        print(f"Available Tools: {[t.name for t in tools_response.tools]}")
        print()

        # Step 2: Call TOOL_LIST to enumerate available tools
        print("Step 2: Getting list of available tools via TOOL_LIST...")
        list_result = await session.call_tool("TOOL_LIST", {})

        # Extract tool names from response
        available_tools = []
        if hasattr(list_result, 'content'):
            content = list_result.content
            if isinstance(content, list) and len(content) > 0:
                for item in content:
                    if hasattr(item, 'text'):
                        text = item.text
                        # Extract tool names (uppercase with underscores)
                        import re
                        tool_matches = re.findall(r'[A-Z_]+', text)
                        available_tools.extend(tool_matches)

        # Remove duplicates and filter
        available_tools = list(set(available_tools))
        available_tools = [t for t in available_tools if len(t) > 3 and '_' in t]

        if available_tools:
            print(f"Available tools (showing 12/{len(available_tools)}):")
            for i, tool in enumerate(available_tools[:12]):
                print(f"  {i+1}. {tool}")
            print()
        else:
            print("No tool list extracted, using hardcoded TIME_SERIES_DAILY")
            available_tools = ["TIME_SERIES_DAILY"]
            print()

        # Step 3: Get schema for the first tool
        first_tool = available_tools[0] if available_tools else "TIME_SERIES_DAILY"
        print(f"Step 3: Getting schema for {first_tool} tool...")
        schema_result = await session.call_tool("TOOL_GET", {"tool_name": first_tool})

        if hasattr(schema_result, 'content'):
            print(f"Schema response content: {schema_result.content}")
        print()

        # Step 4: Call TIME_SERIES_DAILY tool via TOOL_CALL
        print("Step 4: Calling TIME_SERIES_DAILY tool for IBM via TOOL_CALL...")
        call_result = await session.call_tool(
            "TOOL_CALL",
            {
                "tool_name": "TIME_SERIES_DAILY",
                "arguments": {"symbol": "IBM"}
            }
        )

        if hasattr(call_result, 'content'):
            print("Result content:")
            for content in call_result.content:
                if hasattr(content, 'text'):
                    print(content.text)
        print()

        # Close session
        await session.__aexit__(None, None, None)

        return True

    except Exception as e:
        print(f"MCP Client Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_mcp_client():
    """Run MCP client to test Alpha Vantage service."""
    # Try streamable-http first
    streamable_http_success = await run_mcp_client_streamable_http()

    if not streamable_http_success:
        print("\nStreamable-http transport failed. Trying standard MCP client...")
        print()
        http_success = await run_mcp_client_http()

        if not http_success:
            print("\nBoth streamable-http approaches failed.")
            print("The MCP test script has been created successfully.")
            print("You may need to check the Alpha Vantage MCP documentation for the correct connection method.")


if __name__ == "__main__":
    asyncio.run(run_mcp_client())
