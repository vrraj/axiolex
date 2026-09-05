# Release Notes

## Version 2.0.0 — Initial Public Release

### Overview

Axiolex is a centralized tool discovery and execution platform for AI clients and enterprise agents. It lets AI clients (Claude Desktop, Cursor, enterprise copilots, custom LLM agents) dynamically discover and execute tools without registering every MCP endpoint, A2A agent, or internal service directly in the client.

This is the first public release.

---

### Architecture

- **Unified server process.** REST and MCP Streamable HTTP are served from a single FastAPI process on port 9700. MCP is available at `http://localhost:9700/mcp`.
- **Single retriever instance.** One BM25S index and one ColBERT model load shared across REST and MCP — no duplicate process memory.
- **`@axiolex/mcp-gateway` npx proxy** for stdio-only clients (Claude Desktop, Cursor, Codex). A lightweight Node.js proxy that bridges stdio to the Axiolex HTTP endpoint. No Python, Redis, or ML libraries needed on the client.

### Core Capabilities

- **Unified catalog:** MCP tools, A2A skills, REST APIs, and local Python tools indexed together in a single catalog.
- **Hybrid tool discovery:** intent-based retrieval (`axiolex_discover_tools`) using BM25S lexical and ColBERT semantic search, with optional namespace filtering.
- **Normalized execution:** single execution path (`axiolex_execute_tool`) handling stdio, HTTP, A2A, and REST transports server-side with zero client-side credential exposure.
- **Flexible integration surfaces:**
  - Python SDK (`pip install axiolex`)
  - MCP gateway proxy (`npx @axiolex/mcp-gateway`) for Claude Desktop and Cursor
  - REST API for custom agents and copilot backends
- **Management dashboard:** local web UI (`http://localhost:9700/`) for provider configuration, index management, visual query testing, and encrypted secret storage.
- **Built-in adapters & interop:** native A2A agent card discovery and Jira REST-to-MCP adapter (`atlassian_rest_to_mcp`) included as an example.

### MCP Tools

Axiolex exposes three MCP tools to AI clients:

| Tool | Purpose |
| --- | --- |
| `list_namespaces` | List all enabled tool domains |
| `axiolex_discover_tools` | Find tools relevant to a natural-language request, optionally filtered by namespace |
| `axiolex_execute_tool` | Execute a discovered tool by its `tool_id` with validated arguments |

### Security

- **Dual-boundary architecture:** client-to-Axiolex boundary authenticated at the enterprise edge (OAuth/OIDC, mTLS, API keys); Axiolex-to-provider boundary handled server-side.
- **AES-256-GCM encrypted secret store** for provider credentials (`mcp_secrets.enc`).
- **Environment-variable-first resolution** with encrypted-store fallback.
- **Zero credential leakage:** secrets stripped from logs, REST payloads, and Redis metadata.
- **Discovery audit logging:** query intent, namespaces, ranked scores, and execution latency logged asynchronously.

### Compatibility

- Python 3.10+
- Base install: BM25S lexical retrieval with PyStemmer
- Optional ColBERT hybrid search via `axiolex[colbert]` extra and `AXIOLEX_HYBRID_ENABLED=true`
- Redis required for shared tool catalog
- Node.js required only for stdio proxy (`npx @axiolex/mcp-gateway`)

### Installation

```bash
git clone https://github.com/vrraj/axiolex.git && cd axiolex
make install
make colbert        # optional: add ColBERT hybrid search
make start
curl http://localhost:9700/status
```

Or via PyPI:

```bash
pip install axiolex
```

### Links

- [GitHub Repository](https://github.com/vrraj/axiolex)
- [PyPI Package](https://pypi.org/project/axiolex/)
- [npm: @axiolex/mcp-gateway](https://www.npmjs.com/package/@axiolex/mcp-gateway)
- [API Documentation](https://vrraj.github.io/axiolex/)
