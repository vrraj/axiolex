---
layout: default
title: "Connect Cursor to Axiolex via MCP | Axiolex"
description: "Connect Cursor to Axiolex for centralized tool discovery and execution over MCP."
---

# Connect Cursor to Axiolex via MCP

> **New to Axiolex?** Start with the [overview](index.md) or the [quick start guide](setup-usage.md).

Cursor connects to Axiolex through the **MCP Streamable HTTP** transport. Cursor can discover the most relevant tool for a request and execute it through Axiolex's dispatcher — without any secrets on the client.

## What Cursor sees

When connected, Cursor can call three MCP tools:

- **`list_namespaces`** — list enabled tool domains and namespace descriptions (e.g. `finance.market_data`, `retail.orders`).
- **`axiolex_discover_tools`** — pass a natural-language request, get back ranked tools with their `tool_id`, names, descriptions, parameter schemas, endpoints, and transports.
- **`axiolex_execute_tool`** — pass a `tool_id` (from discovery) and arguments; Axiolex dispatches the call over the tool's transport and returns a normalized result.

## Prerequisites

Start the Axiolex server:

```bash
git clone https://github.com/vrraj/axiolex.git && cd axiolex
make install
make start
```

MCP is served at `http://localhost:9700/mcp`.

## Recommended: Streamable HTTP

Edit your Cursor MCP configuration at `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "axiolex": {
      "url": "http://localhost:9700/mcp"
    }
  }
}
```

Restart Cursor after saving the config.

### Enterprise deployment

Point at the shared Axiolex URL:

```json
{
  "mcpServers": {
    "axiolex": {
      "url": "https://axiolex.internal.corp/mcp"
    }
  }
}
```

The server holds all provider credentials — nothing secret lives on the client.

## Alternative: stdio via npx proxy

If your Cursor configuration requires stdio transport, use the **@axiolex/mcp-gateway** proxy:

```json
{
  "mcpServers": {
    "axiolex": {
      "command": "npx",
      "args": ["-y", "@axiolex/mcp-gateway", "--endpoint", "http://localhost:9700/mcp"]
    }
  }
}
```

See [Connecting MCP Clients](mcp-clients.md) for the full comparison of npx proxy vs Python stdio.

## Test prompts

Once connected, try prompts in Cursor Agent mode like:

- "Discover the best tool for getting a stock quote."
- "What tools are available for finance research?"
- "Find the most relevant tool for placing a buy order."
- "Discover a tool that can search the web."
- "List all available namespaces."

Cursor will receive the ranked tool list from Axiolex, then call `axiolex_execute_tool` with the chosen `tool_id` and arguments to run the tool.

## Notes

- **Streamable HTTP requires `make start` to be running** (Redis + Axiolex server on localhost:9700).
- **The npx proxy also requires `make start`** — the proxy connects to the HTTP endpoint. Node.js 18+ is required.
- API key rotation happens on the server only; no client reconfiguration needed.
- See [Connecting MCP Clients](mcp-clients.md) for the generic connection architecture and other client setup guides.
