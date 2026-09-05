# Release Notes

## Version 2.0.0 — Initial Public Release

### Overview

Axiolex is a centralized tool discovery and execution platform for **AI clients, coding tools, enterprise applications, copilots, and agents**. Clients such as **Claude Desktop, Cursor, Codex, enterprise copilots, and custom LLM agents** can dynamically discover and execute relevant capabilities without registering every downstream provider, endpoint, or credential directly.

---

### Architecture

* **Unified server process:** REST and MCP Streamable HTTP are served from a single FastAPI process on port 9700. MCP is available at `http://localhost:9700/mcp`.
* **Python SDK:** lightweight client (`pip install axiolex`) for programmatic namespace access, tool discovery, and execution over the Axiolex service.
* **`@axiolex/mcp-gateway` npx proxy:** lightweight Node.js bridge for stdio-only MCP clients such as Claude Desktop, Cursor, and Codex. No Python, Redis, or ML dependencies are required on the client.

### Core Capabilities

* **Unified catalog:** MCP tools, A2A skills, adapter-backed enterprise services, and local tool definitions indexed together in a single catalog.
* **Hybrid tool discovery:** intent-based retrieval (`axiolex_discover_tools`) using BM25S lexical and optional ColBERT semantic search.
* **Namespace-based discovery:** single-scope, multi-scope, and full-catalog discovery across business domains.
* **Normalized execution:** one execution path (`axiolex_execute_tool`) for MCP stdio, MCP Streamable HTTP, and A2A, with REST-only systems integrated through adapters.
* **Flexible integration surfaces:** Python SDK, REST API, MCP Streamable HTTP, and the `@axiolex/mcp-gateway` stdio proxy.
* **Management dashboard:** local web UI (`http://localhost:9700/`) for provider configuration, catalog management, discovery testing, retrieval tuning, and encrypted secret storage.
* **Built-in adapters & interop:** native A2A Agent Card discovery plus the `atlassian_rest_to_mcp` Jira adapter as a reference implementation for REST-only enterprise systems.

### MCP Tools

Axiolex exposes three MCP tools to AI clients:

| Tool | Purpose |
| --- | --- |
| `list_namespaces` | List all enabled tool domains |
| `axiolex_discover_tools` | Find tools relevant to a natural-language request, optionally filtered by namespace |
| `axiolex_execute_tool` | Execute a discovered tool by its `tool_id` with validated arguments |

### Security

* **Dual-boundary architecture:** client-to-Axiolex access is authenticated at the enterprise edge using mechanisms such as OAuth/OIDC, mTLS, or API keys; Axiolex-to-provider authentication is handled server-side.
* **AES-256-GCM encrypted secret store** for provider credentials (`mcp_secrets.enc`).
* **Environment-variable-first credential resolution** with encrypted-store fallback.
* **Zero credential leakage:** secrets are stripped from logs, REST payloads, and Redis metadata.
* **Discovery audit logging:** query intent, namespaces, ranked results, relevance scores, and execution latency are logged asynchronously.

### Compatibility

* Python 3.10+
* Base install: BM25S lexical retrieval with PyStemmer
* Optional ColBERT hybrid search via `axiolex[colbert]` and `AXIOLEX_HYBRID_ENABLED=true`
* Redis required for shared catalog state
* Node.js required only for MCP clients using the `npx @axiolex/mcp-gateway` stdio proxy

### Installation

**Axiolex server:**

```bash
git clone https://github.com/vrraj/axiolex.git && cd axiolex
make install
make colbert        # optional: add ColBERT hybrid search
make start
curl http://localhost:9700/status
```

**Client access:**

* **Python SDK:** `pip install axiolex`
* **MCP Streamable HTTP:** `http://localhost:9700/mcp`
* **MCP stdio:** `npx @axiolex/mcp-gateway --endpoint http://localhost:9700/mcp`
* **REST API:** `http://localhost:9700`

### Links

* [GitHub Repository](https://github.com/vrraj/axiolex)
* [PyPI Package](https://pypi.org/project/axiolex/)
* [npm: @axiolex/mcp-gateway](https://www.npmjs.com/package/@axiolex/mcp-gateway)
* [API Documentation](https://vrraj.github.io/axiolex/)
