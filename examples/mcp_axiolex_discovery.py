#!/usr/bin/env python3
"""Test the Axiolex MCP server (discovery + execution)."""

import argparse
import asyncio
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test Axiolex tools/list, axiolex_discover_tools, and axiolex_execute_tool"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:9701/mcp",
        help="Axiolex Streamable HTTP MCP endpoint",
    )
    parser.add_argument(
        "--query",
        default="get stock price history",
        help="Natural-language tool discovery query",
    )
    parser.add_argument("--max-tools", type=int, default=3)
    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    async with streamable_http_client(args.url) as streams:
        async with ClientSession(*streams[:2]) as session:
            await session.initialize()

            listed = await session.list_tools()
            tool_names = [tool.name for tool in listed.tools]
            print("MCP tools/list:")
            print(json.dumps(tool_names, indent=2))
            assert "axiolex_discover_tools" in tool_names
            assert "axiolex_execute_tool" in tool_names
            assert "list_namespaces" in tool_names

            result = await session.call_tool(
                "axiolex_discover_tools",
                {"query": args.query, "max_tools": args.max_tools},
            )
            assert not result.isError
            discovered = result.structuredContent
            print("\nMCP axiolex_discover_tools result:")
            print(json.dumps(discovered, indent=2))

            assert discovered["count"] == len(discovered["tools"])
            for tool in discovered["tools"]:
                assert tool["tool_id"], "Missing tool_id"
                assert tool["name"]
                assert tool["transport"]

    print("\nAxiolex MCP discovery test passed.")


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
