---
layout: default
title: "Connect Codex to Axiolex via MCP | Axiolex"
description: "Connect Codex to Axiolex for centralized tool discovery and execution over MCP."
---

# Connect Codex to Axiolex via MCP

> **New to Axiolex?** Start with the [overview](index.md) or the [quick start guide](setup-usage.md).

Codex connects to Axiolex through the **@axiolex/mcp-gateway** stdio proxy, which bridges Codex's stdio MCP transport to Axiolex's Streamable HTTP endpoint. Codex can discover the most relevant tool for a request and execute it through Axiolex's dispatcher — without any secrets on the client.

## What Codex sees

When connected, Codex can call three MCP tools:

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

## Setup via npx proxy

Codex uses a TOML configuration file at `~/.codex/config.toml`. MCP servers are defined under `[mcp_servers.<name>]`.

Add the Axiolex gateway:

```toml
[mcp_servers.axiolex]
command = "npx"
args = ["-y", "@axiolex/mcp-gateway", "--endpoint", "http://localhost:9700/mcp"]
```

Restart Codex after saving the config.

### Enterprise deployment

Point the proxy at the shared Axiolex URL:

```toml
[mcp_servers.axiolex]
command = "npx"
args = ["-y", "@axiolex/mcp-gateway", "--endpoint", "https://axiolex.internal.corp/mcp"]
```

The server holds all provider credentials — nothing secret lives on the client.

## Example prompts

Once connected, try prompts like:

- "List available namespaces in Axiolex."
- "Create a task in Jira for fixing the login timeout bug."
- "Research the web for analyst recommendations on NVDA."
- "What tools are available for predicting supply risk for DDR4 memory?"
- "Get the latest stock price for AAPL."

These are example prompts we tested with based on the tools configured in our Axiolex deployment. Connect your own MCP servers, A2A agents, and local tools, then run queries relevant to your catalog.

## Notes

- **Requires `make start` to be running** (Redis + Axiolex server on localhost:9700). The proxy connects to the HTTP endpoint.
- **Node.js 18+ is required** on the client for the npx proxy.
- API key rotation happens on the server only; no client reconfiguration needed.
- See [Connecting MCP Clients](mcp-clients.md) for the generic connection architecture and other client setup guides.
