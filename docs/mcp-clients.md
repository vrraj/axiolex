---
layout: default
title: "Connect MCP Clients | Axiolex"
description: "Connect Claude Desktop, Cursor, Codex, and other MCP clients to Axiolex for tool discovery and execution."
---

# Connecting MCP Clients to Axiolex

Axiolex exposes its tool catalog to MCP-compatible AI clients through the **MCP Streamable HTTP** transport. Clients discover the most relevant tool for a request and execute it through Axiolex's dispatcher — without any secrets on the client machine.

The core pattern is the same across all clients:

```text
client → Axiolex MCP endpoint → axiolex_discover_tools → axiolex_execute_tool
```

## How Axiolex appears to MCP clients

When connected, the AI client sees three MCP tools:

- **`list_namespaces`** — list enabled tool domains and namespace descriptions (e.g. `finance.market_data`, `retail.orders`).
- **`axiolex_discover_tools`** — pass a natural-language request, get back ranked tools with their `tool_id`, names, descriptions, parameter schemas, endpoints, and transports.
- **`axiolex_execute_tool`** — pass a `tool_id` (from discovery) and arguments; Axiolex dispatches the call over the tool's transport, validates arguments against the current schema, and returns a normalized result envelope.

## Prerequisites

Start the Axiolex server before connecting any client:

```bash
git clone https://github.com/vrraj/axiolex.git && cd axiolex
make install
make start
```

This starts Redis, loads the catalog, and runs the FastAPI server on port 9700. MCP is served at `http://localhost:9700/mcp`.

## Claude Desktop

Claude Desktop supports the **Streamable HTTP** transport directly — no proxy or local install needed.

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

## Cursor

Cursor uses an MCP server configuration file at `~/.cursor/mcp.json`.

### Streamable HTTP

```json
{
  "mcpServers": {
    "axiolex": {
      "url": "http://localhost:9700/mcp"
    }
  }
}
```

### stdio via npx proxy

For Cursor configurations that require stdio:

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

Restart Cursor after saving the config.

## Codex

Codex uses a TOML configuration file at `~/.codex/config.toml`. MCP servers are defined under `[mcp_servers.<name>]`.

```toml
[mcp_servers.axiolex]
command = "npx"
args = ["-y", "@axiolex/mcp-gateway", "--endpoint", "http://localhost:9700/mcp"]
```

Restart Codex after saving the config.

## stdio via @axiolex/mcp-gateway

Some MCP clients support stdio transport only — they spawn a local subprocess and communicate over stdin/stdout. For these clients, use the **@axiolex/mcp-gateway** npm package: a lightweight stdio-to-HTTP proxy that connects to the Axiolex server over HTTP.

The proxy requires only Node.js 18+ (no Python, no Redis, no ML libraries). It's ~86 MB in memory vs ~1.8 GB for the Python stdio server. IT can audit the entire source on [npm](https://www.npmjs.com/package/@axiolex/mcp-gateway) or [GitHub](https://github.com/vrraj/axiolex/tree/main/mcp-gateway).

### Setup

1. Start the Axiolex server (the proxy connects to it over HTTP):

```bash
make start
```

2. Add the proxy to your client's MCP config:

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

For a remote Axiolex server:

```json
{
  "mcpServers": {
    "axiolex": {
      "command": "npx",
      "args": ["-y", "@axiolex/mcp-gateway", "--endpoint", "https://axiolex.internal.corp/mcp"]
    }
  }
}
```

### Why the npx proxy over Python stdio

| Concern | npx proxy | Python stdio (`axiolex-mcp-server`) |
|---|---|---|
| Client needs | Node.js (already installed) | Python + axiolex package + all deps |
| Memory | ~86 MB | ~1.8 GB (loads BM25S + ColBERT) |
| Secrets on client | None — proxy is just a pipe | Requires `.env` and encrypted store on client |
| Setup | One config entry, zero install | Clone, install, configure paths |
| Enterprise IT | Auditable JS source on npm | Python environment + ML libraries to review |
| Update | `npx` auto-fetches latest | Manual `git pull && make install` |

### Legacy: Python stdio (advanced)

For air-gapped environments where Node.js is not available, the Python stdio server remains available:

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

This requires a full Axiolex installation (Python + all dependencies + Redis) on the client machine.

## Enterprise deployment

In an enterprise setting, Axiolex runs as a central service (Docker or host) with Redis. Each client points at the shared URL:

| Client | Config file | Pattern |
|---|---|---|
| Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json` | `"url": "https://axiolex.internal.corp/mcp"` |
| Cursor | `~/.cursor/mcp.json` | `"url": "https://axiolex.internal.corp/mcp"` |
| Codex | `~/.codex/config.toml` | npx proxy with `--endpoint https://axiolex.internal.corp/mcp` |

- The server holds the master key and encrypted secrets — nothing secret lives on the client.
- API key rotation happens on the server only; no client reconfiguration needed.
- See the [Docker deployment guide](technical_architecture.html#deployment) for running Axiolex as a central service.

## Test prompts and verification

Once the MCP tools appear in your client, try prompts like:

- "Discover the best tool for getting a stock quote."
- "What tools are available for finance research?"
- "Find the most relevant tool for placing a buy order."
- "Discover a tool that can search the web."
- "List all available namespaces."

The client will receive the ranked tool list from Axiolex, then call `axiolex_execute_tool` with the chosen `tool_id` and arguments to run the tool.

## Notes

- **Streamable HTTP requires `make start` to be running** (Redis + Axiolex server on localhost:9700). MCP is served at `http://localhost:9700/mcp`.
- **The npx proxy also requires `make start`** — the proxy connects to the HTTP endpoint. Node.js 18+ is required on the client.
- **The Python stdio pattern requires a reachable Redis with the catalog already loaded**, but does not require the FastAPI server. Full Axiolex installation needed on the client.
- For remote MCP clients, the MCP endpoint is available at `http://<host>:9700/mcp` on the running API server.
- See [setup-usage.html](setup-usage.html) for the full management and automation guide.
