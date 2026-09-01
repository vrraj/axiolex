---
layout: default
title: "Connect Claude Desktop | AxioLex"
description: "Connect Claude Desktop to AxioLex for tool discovery and execution over MCP."
---

# Connect Claude Desktop to AxioLex

AxioLex exposes its tool catalog to **Claude Desktop** through the **MCP Streamable HTTP** transport. Claude can discover the most relevant tool for a request and execute it through AxioLex's dispatcher — without any secrets on the desktop.

## What Claude sees

When connected, Claude can call two MCP tools:

- **`axiolex_discover_tools`** — pass a natural-language request, get back ranked tools with their `tool_id`, names, descriptions, parameter schemas, endpoints, and transports.
- **`axiolex_execute_tool`** — pass a `tool_id` (from discovery) and arguments, and AxioLex dispatches the call over the tool's transport, validates arguments against the current schema, and returns a normalized result envelope.

Claude also sees **`list_namespaces`** to discover available capability areas (e.g. `finance.market_data`, `retail.orders`) before searching for tools.

## Recommended: Streamable HTTP

This is the pattern that works for **both local development and enterprise deployment**. The AxioLex server runs as a persistent process (started via `make start` or Docker), loads its configuration and encrypted secrets, and serves MCP over HTTP. Claude Desktop connects to it with a URL — no secrets, no paths, no environment variables on the desktop.

### Local development

1. Clone and install the repo:

```bash
git clone https://github.com/vrraj/axiolex.git
cd axiolex
make install
```

2. Start Redis and the AxioLex servers:

```bash
make start
```

This starts Redis, loads the catalog, and runs the FastAPI server (port 9700) and the MCP HTTP server (port 9701).

3. Edit your Claude Desktop MCP configuration:

```bash
# macOS
open -a TextEdit ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

4. Add the AxioLex server using the `url` field:

```json
{
  "mcpServers": {
    "axiolex": {
      "url": "http://localhost:9701/mcp"
    }
  }
}
```

5. Save, quit, and restart Claude Desktop.

### Enterprise deployment

In an enterprise setting, AxioLex runs as a central service (Docker or host) with Redis. Each employee's Claude Desktop points at the shared URL:

```json
{
  "mcpServers": {
    "axiolex": {
      "url": "https://axiolex.internal.corp/mcp"
    }
  }
}
```

- The server holds the master key and encrypted secrets — **nothing secret lives on the desktop**.
- API key rotation happens on the server only; no desktop reconfiguration needed.
- See the [Docker deployment guide](technical_architecture.html#deployment) for running AxioLex as a central service.

### Why HTTP is recommended

| Concern | HTTP pattern |
|---|---|
| Secrets on desktop | None — server holds all credentials |
| API key rotation | One operation on the server, instant for all clients |
| Desktop config | Just a URL — no paths, no env vars, no secrets |
| Code path | Identical for local dev (`localhost`) and enterprise (`internal.corp`) |
| Process lifecycle | Server is always running; Claude connects on demand |

## Alternative: stdio (air-gapped / no persistent server)

The stdio transport spawns AxioLex as a subprocess directly from Claude Desktop. This is useful for air-gapped machines or environments where a persistent server is not possible.

> **Current limitation:** The stdio process inherits Claude Desktop's environment (CWD is `/`), so it cannot locate the project `.env` file or the encrypted secrets store by default. API keys must be available in the OS environment, or the [config-dir resolution work](https://github.com/vrraj/axiolex/blob/main/axiolex_to_do.md) must be completed first. For most use cases, the HTTP pattern above is simpler and more secure.

1. Clone, install, and start Redis + load the catalog:

```bash
git clone https://github.com/vrraj/axiolex.git
cd axiolex
make install
make redis-start
uv run -- axiolex-index refresh --tools-file source_files/tools_list.yaml --providers-file source_files/mcp_providers.yaml
```

2. Find the absolute path to the virtual environment's Python:

```bash
realpath .venv/bin/python
```

3. Add the AxioLex server to your Claude Desktop config:

```json
{
  "mcpServers": {
    "axiolex": {
      "command": "/ABSOLUTE/PATH/TO/axiolex/.venv/bin/python",
      "args": ["-m", "axiolex.mcp.server", "--transport", "stdio"]
    }
  }
}
```

4. Save, quit, and restart Claude Desktop.

## Try it

Once the hammer icon appears in Claude, try prompts like:

- "Discover the best tool for getting a stock quote."
- "What tools are available for finance research?"
- "Find the most relevant tool for placing a buy order."
- "Discover a tool that can search the web."

Claude will receive the ranked tool list from AxioLex, then call `axiolex_execute_tool` with the chosen `tool_id` and arguments to run the tool.

## Notes

- **The HTTP pattern requires `make start` to be running** (Redis + AxioLex servers on localhost:9701).
- **The stdio pattern requires a reachable Redis with the catalog already loaded**, but does not require the FastAPI server.
- For remote MCP clients other than Claude Desktop, run `axiolex-mcp-server --transport streamable-http --host 0.0.0.0 --port 9701`.
- See [setup-usage.html](setup-usage.html) for the full management and automation guide.
