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

This starts Redis, loads the catalog, and runs the FastAPI server (port 9700) which serves both REST and MCP at `/mcp`.

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
      "url": "http://localhost:9700/mcp"
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

## Alternative: stdio via npx proxy (for clients that require stdio)

Some MCP clients (including Claude Desktop) support stdio transport only — they spawn a local subprocess and communicate over stdin/stdout. For these clients, use the **@axiolex/mcp-gateway** npm package: a ~120-line stdio-to-HTTP proxy that connects to the Axiolex server over HTTP.

The proxy requires only Node.js (no Python, no Redis, no ML libraries). It's ~86 MB in memory vs ~1.8 GB for the Python stdio server. IT can audit the entire source on [npm](https://www.npmjs.com/package/@axiolex/mcp-gateway) or [GitHub](https://github.com/vrraj/axiolex/tree/main/mcp-gateway).

### Setup

1. Start the Axiolex server (the proxy connects to it over HTTP):

```bash
make start
```

2. Add the proxy to your Claude Desktop config:

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

3. Save, quit, and restart Claude Desktop.

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

### Why the npx proxy is preferred over Python stdio

| Concern | npx proxy | Python stdio (`axiolex-mcp-server`) |
|---|---|---|
| Client needs | Node.js (already installed) | Python + axiolex package + all deps |
| Memory | ~86 MB | ~1.8 GB (loads BM25S + ColBERT) |
| Secrets on desktop | None — proxy is just a pipe | Requires `.env` and encrypted store on client |
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

## Try it

Once the hammer icon appears in Claude, try prompts like:

- "Discover the best tool for getting a stock quote."
- "What tools are available for finance research?"
- "Find the most relevant tool for placing a buy order."
- "Discover a tool that can search the web."

Claude will receive the ranked tool list from AxioLex, then call `axiolex_execute_tool` with the chosen `tool_id` and arguments to run the tool.

## Notes

- **The HTTP pattern requires `make start` to be running** (Redis + AxioLex server on localhost:9700). MCP is served at `http://localhost:9700/mcp`.
- **The npx proxy pattern also requires `make start`** — the proxy connects to the HTTP endpoint. Node.js 18+ is required on the client.
- **The Python stdio pattern requires a reachable Redis with the catalog already loaded**, but does not require the FastAPI server. Full Axiolex installation needed on the client.
- For remote MCP clients other than Claude Desktop, the MCP endpoint is available at `http://<host>:9700/mcp` on the running API server.
- See [setup-usage.html](setup-usage.html) for the full management and automation guide.
