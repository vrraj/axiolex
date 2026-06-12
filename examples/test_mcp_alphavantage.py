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
from mcp.client.sse import sse_client

# Load environment variables
load_dotenv()

# Get API key from environment
ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_APIKEY")

if not ALPHAVANTAGE_API_KEY:
    raise ValueError("ALPHAVANTAGE_APIKEY not found in environment variables")

# Try SSE transport first (the original approach)
MCP_URL = f"https://mcp.alphavantage.co/mcp?apikey={ALPHAVANTAGE_API_KEY}"
MCP_BASE_URL = "https://mcp.alphavantage.co/mcp"


async def run_mcp_client_sse():
    """Run MCP client using SSE transport."""
    print(f"Connecting to Alpha Vantage MCP server via SSE...")
    print(f"URL: {MCP_URL}")
    print()
    
    try:
        async with sse_client(MCP_URL) as (read, write):
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
        print(f"SSE Error: {e}")
        return False
    
    return True


def run_mcp_client_http():
    """Run MCP client using HTTP POST with JSON-RPC."""
    print(f"Connecting to Alpha Vantage MCP server via HTTP POST...")
    print(f"URL: {MCP_BASE_URL}")
    print()
    
    try:
        # Step 1: List tools
        print("Step 1: Listing available tools...")
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 1
        }
        
        response = httpx.post(
            MCP_BASE_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            params={"apikey": ALPHAVANTAGE_API_KEY}
        )
        
        print(f"Status Code: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        print()
        
        # Step 2: Get schema for a specific tool (e.g., TIME_SERIES_DAILY)
        print("Step 2: Getting schema for TIME_SERIES_DAILY tool...")
        get_payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "TOOL_GET",
                "arguments": {"tool_name": "TIME_SERIES_DAILY"}
            },
            "id": 2
        }
        
        response = httpx.post(
            MCP_BASE_URL,
            json=get_payload,
            headers={"Content-Type": "application/json"},
            params={"apikey": ALPHAVANTAGE_API_KEY}
        )
        
        print(f"Status Code: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        print()
        
        # Step 3: Call the tool with arguments
        print("Step 3: Calling TIME_SERIES_DAILY tool for IBM...")
        call_payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "TOOL_CALL",
                "arguments": {
                    "tool_name": "TIME_SERIES_DAILY",
                    "arguments": {"symbol": "IBM"}
                }
            },
            "id": 3
        }
        
        response = httpx.post(
            MCP_BASE_URL,
            json=call_payload,
            headers={"Content-Type": "application/json"},
            params={"apikey": ALPHAVANTAGE_API_KEY}
        )
        
        print(f"Status Code: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        print()
        
        return True
        
    except Exception as e:
        print(f"HTTP Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_mcp_client():
    """Run MCP client to test Alpha Vantage service."""
    # Try SSE first
    sse_success = await run_mcp_client_sse()
    
    if not sse_success:
        print("\nSSE transport failed. Trying HTTP POST with JSON-RPC...")
        print()
        http_success = run_mcp_client_http()
        
        if not http_success:
            print("\nBoth SSE and HTTP POST failed.")
            print("The MCP test script has been created successfully.")
            print("You may need to check the Alpha Vantage MCP documentation for the correct connection method.")


if __name__ == "__main__":
    asyncio.run(run_mcp_client())
