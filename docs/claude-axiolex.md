---
layout: default
title: "Connect Claude to Axiolex via MCP | Axiolex"
description: "Connect Claude Desktop to Axiolex for centralized tool discovery and execution over MCP Streamable HTTP."
---

# Connect Claude to Axiolex via MCP

> **New to Axiolex?** Start with the [overview](index.md) or the [quick start guide](setup-usage.md).

Claude Desktop connects to Axiolex through the **MCP Streamable HTTP** transport. Claude can discover the most relevant tool for a request and execute it through Axiolex's dispatcher — without any secrets on the desktop.

## What Claude sees

When connected, Claude can call three MCP tools:

- **`list_namespaces`** — list enabled tool domains and namespace descriptions (e.g. `finance.market_data`, `retail.orders`).
- **`axiolex_discover_tools`** — pass a natural-language request, get back ranked tools with their `tool_id`, names, descriptions, parameter schemas, endpoints, and transports.
- **`axiolex_execute_tool`** — the client selects a `tool_id` from discovery and passes arguments. Axiolex resolves the provider, transport, endpoint, and credentials server-side and returns a normalized result. The client never needs to know whether the tool is backed by MCP, A2A, an adapter, or an internal service.

## Prerequisites

Start the Axiolex server:

```bash
git clone https://github.com/vrraj/axiolex.git && cd axiolex
make install
make start
```

MCP is served at `http://localhost:9700/mcp`.

## Recommended: Streamable HTTP

This is the pattern that works for both local development and enterprise deployment. Claude Desktop connects with a URL — no secrets, no paths, no environment variables on the desktop.

### Local development

Edit your Claude Desktop MCP configuration:

```bash
# macOS
open -a TextEdit ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

Add the Axiolex server using the `url` field:

```json
{
  "mcpServers": {
    "axiolex": {
      "url": "http://localhost:9700/mcp"
    }
  }
}
```

Save, quit, and restart Claude Desktop.

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

The server holds the master key and encrypted secrets — nothing secret lives on the desktop.

## Alternative: stdio via npx proxy

If your Claude Desktop configuration requires stdio transport, use the **@axiolex/mcp-gateway** proxy:

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

## Example prompts

Once the MCP tools appear in Claude, try prompts like:

- "List available namespaces in Axiolex."
- "Create a task in Jira for fixing the login timeout bug."
- "Research the web for analyst recommendations on NVDA."
- "What tools are available for predicting supply risk for DDR4 memory?"
- "Get the latest stock price for AAPL."

These are example prompts we tested with based on the tools configured in our Axiolex deployment. Connect your own MCP servers, A2A agents, and local tools, then run queries relevant to your catalog.

## Notes

- **Streamable HTTP requires `make start` to be running** (Redis + Axiolex server on localhost:9700).
- **The npx proxy also requires `make start`** — the proxy connects to the HTTP endpoint. Node.js 18+ is required.
- API key rotation happens on the server only; no desktop reconfiguration needed.
- See [Connecting MCP Clients](mcp-clients.md) for the generic connection architecture and other client setup guides.
