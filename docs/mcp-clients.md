---
layout: default
title: "Connect MCP Clients | Axiolex"
description: "Connect any MCP-compatible client to Axiolex for centralized tool discovery and execution."
---

# Connecting MCP Clients to Axiolex

Axiolex exposes its tool catalog to any MCP-compatible AI client through the **MCP Streamable HTTP** transport. Clients discover the most relevant tool for a request and execute it through Axiolex's dispatcher — without any secrets on the client machine.

The core pattern is the same across all clients:

```text
client → Axiolex MCP endpoint → axiolex_discover_tools → axiolex_execute_tool
```

## What every MCP client sees

When connected, the AI client sees three MCP tools:

- **`list_namespaces`** — list enabled tool domains and namespace descriptions (e.g. `finance.market_data`, `retail.orders`).
- **`axiolex_discover_tools`** — pass a natural-language request, get back ranked tools with their `tool_id`, names, descriptions, parameter schemas, endpoints, and transports.
- **`axiolex_execute_tool`** — pass a `tool_id` (from discovery) and arguments; Axiolex dispatches the call over the tool's transport, validates arguments against the current schema, and returns a normalized result envelope.

## Connection patterns

### Streamable HTTP (recommended)

The Axiolex server runs as a persistent process and serves MCP over HTTP. Clients connect with a URL — no secrets, no paths, no environment variables on the client.

```json
{
  "mcpServers": {
    "axiolex": {
      "url": "http://localhost:9700/mcp"
    }
  }
}
```

For a remote Axiolex server:

```json
{
  "mcpServers": {
    "axiolex": {
      "url": "https://axiolex.internal.corp/mcp"
    }
  }
}
```

### stdio via @axiolex/mcp-gateway

Some MCP clients support stdio transport only — they spawn a local subprocess and communicate over stdin/stdout. For these clients, use the **@axiolex/mcp-gateway** npm package: a lightweight stdio-to-HTTP proxy that connects to the Axiolex server over HTTP.

The proxy requires only Node.js 18+ (no Python, no Redis, no ML libraries). It's ~86 MB in memory vs ~1.8 GB for the Python stdio server. IT can audit the entire source on [npm](https://www.npmjs.com/package/@axiolex/mcp-gateway) or [GitHub](https://github.com/vrraj/axiolex/tree/main/mcp-gateway).

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

### Why the npx proxy is preferred over Python stdio

| Concern | npx proxy | Python stdio (`axiolex-mcp-server`) |
|---|---|---|
| Client needs | Node.js (already installed) | Python + axiolex package + all deps |
| Memory | ~86 MB | ~1.8 GB (loads BM25S + ColBERT) |
| Secrets on client | None — proxy is just a pipe | Requires `.env` and encrypted store on client |
| Setup | One config entry, zero install | Clone, install, configure paths |
| Enterprise IT | Auditable JS source on npm | Python environment + ML libraries to review |
| Update | `npx` auto-fetches latest | Manual `git pull && make install` |

## Security model

- **Client credentials:** none required on the client. The Axiolex server holds all provider credentials in an AES-256-GCM encrypted secret store.
- **API key rotation:** happens on the server only; no client reconfiguration needed.
- **Enterprise boundary:** client authentication is enforced at the deployment edge (reverse proxy, API gateway, service mesh) using OAuth/OIDC, mTLS, or API keys.

See the [Security Overview](../README.md#security-overview) for the full dual-boundary architecture.

## Prerequisites

Start the Axiolex server before connecting any client:

```bash
git clone https://github.com/vrraj/axiolex.git && cd axiolex
make install
make start
```

This starts Redis, loads the catalog, and runs the FastAPI server on port 9700. MCP is served at `http://localhost:9700/mcp`.

## Client-specific setup guides

Each MCP client has a different configuration file location and format. See the dedicated setup guide for your client:

- [Connect Claude to Axiolex via MCP](claude-axiolex.md)
- [Connect Cursor to Axiolex via MCP](cursor-axiolex.md)
- [Connect Codex to Axiolex via MCP](codex-axiolex.md)

## Enterprise deployment

In an enterprise setting, Axiolex runs as a central service (Docker or host) with Redis. Each client points at the shared URL:

| Client | Config file | Pattern |
|---|---|---|
| Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json` | `"url": "https://axiolex.internal.corp/mcp"` |
| Cursor | `~/.cursor/mcp.json` | `"url": "https://axiolex.internal.corp/mcp"` |
| Codex | `~/.codex/config.toml` | npx proxy with `--endpoint https://axiolex.internal.corp/mcp` |

See the [Docker deployment guide](technical_architecture.html#deployment) for running Axiolex as a central service.

## Test prompts

Once the MCP tools appear in your client, try prompts like:

- "Discover the best tool for getting a stock quote."
- "What tools are available for finance research?"
- "Find the most relevant tool for placing a buy order."
- "Discover a tool that can search the web."
- "List all available namespaces."

The client will receive the ranked tool list from Axiolex, then call `axiolex_execute_tool` with the chosen `tool_id` and arguments to run the tool.
