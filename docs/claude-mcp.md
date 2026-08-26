---
layout: default
title: "Connect Claude Desktop | AxioLex"
description: "Run AxioLex as an MCP stdio server and connect it to Claude Desktop for tool discovery."
---

# Connect Claude Desktop to AxioLex

AxioLex can expose its tool catalog to **Claude Desktop** through the **MCP stdio** transport. Claude can then discover the most relevant tool for a request before deciding how to act.

## What Claude sees

When connected, Claude can call the `discover_tools` MCP tool with a natural-language request. AxioLex returns the top-ranked tools from the Redis catalog, including their names, descriptions, parameter schemas, endpoints, transports, and execution metadata.

> **Important:** `axiolex-mcp-server` is a discovery server. It tells Claude which tool to use and how to reach it. Claude (or the calling application) still executes the tool itself.

## Quick setup

1. Clone and install the repo:

```bash
git clone https://github.com/vrraj/axiolex.git
cd axiolex
make install
```

2. Start Redis and load the catalog:

```bash
make start        # starts Redis, FastAPI server, and MCP HTTP server
# or, for just the cache:
make redis-start
uv run -- axiolex-index refresh --tools-file source_files/tools_list.yaml --providers-file source_files/mcp_providers.yaml
```

3. Find the absolute path to the virtual environment's Python:

```bash
realpath .venv/bin/python
```

4. Edit your Claude Desktop MCP configuration:

```bash
# macOS
open -a TextEdit ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

5. Add the AxioLex server:

```json
{
  "mcpServers": {
    "axiolex": {
      "command": "/ABSOLUTE/PATH/TO/axiolex/.venv/bin/python",
      "args": ["-m", "axiolex.mcp.server"]
    }
  }
}
```

6. Save, quit, and restart Claude Desktop.

## Try it

Once the hammer icon appears in Claude, try prompts like:

- "Discover the best tool for getting a stock quote."
- "What tools are available for finance research?"
- "Find the most relevant tool for placing a buy order."
- "Discover a tool that can search the web."

Claude will receive the ranked tool list from AxioLex and can then choose how to use it.

## Notes

- **MCP stdio does not require the FastAPI server to be running**, but it does require a reachable Redis with the catalog already loaded.
- For remote MCP clients, run `axiolex-mcp-server --transport streamable-http --host 0.0.0.0 --port 9701`.
- `make mcp-run` starts the HTTP transport, which is what remote clients and the built-in `mcp` test page use.
- See [setup-usage.html](setup-usage.html) for the full management and automation guide.
