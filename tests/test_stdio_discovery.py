"""Tests for stdio MCP transport discovery."""

import sys
import textwrap

import pytest

from axiolex.mcp.discovery import MCPDiscovery, MCPProviderConfig


@pytest.mark.asyncio
async def test_stdio_discovery_finds_tools(tmp_path):
    """A stdio MCP server subprocess should expose its tools via discovery."""
    server_script = tmp_path / "server.py"
    server_script.write_text(textwrap.dedent("""
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("test-server")

        @mcp.tool()
        def echo(text: str) -> str:
            \"\"\"Echo the input text.\"\"\"
            return text

        if __name__ == "__main__":
            mcp.run()
    """))

    config = MCPProviderConfig(
        id="test_stdio",
        name="Test Stdio",
        transport="stdio",
        command=sys.executable,
        args=[str(server_script)],
    )
    discovery = MCPDiscovery(providers=[config], config_file=None)

    tools = await discovery.discover_from_config(config)

    assert len(tools) == 1
    assert tools[0]["id"] == "test_stdio:echo"
    assert tools[0]["tool_name"] == "echo"


@pytest.mark.asyncio
async def test_stdio_discovery_missing_command_returns_empty():
    """A stdio provider with no command should return no tools."""
    config = MCPProviderConfig(
        id="no_command",
        name="No Command",
        transport="stdio",
        command=None,
        args=[],
    )
    discovery = MCPDiscovery(providers=[config], config_file=None)

    tools = await discovery.discover_from_config(config)

    assert tools == []
