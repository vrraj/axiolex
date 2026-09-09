# Release Notes

## Version 2.0.0 — Initial Public Release

### Overview

Axiolex is a centralized tool discovery and execution platform for **AI clients, coding tools, enterprise applications, copilots, and agents**.

Clients such as **Claude Desktop, Cursor, Codex, enterprise copilots, and custom agents** can discover and execute relevant tools without configuring every downstream provider, endpoint, credential, or execution mechanism directly.

---

### Architecture

* **Unified server process:** REST and MCP Streamable HTTP are served from a single FastAPI process on port 9700. MCP is available at `http://localhost:9700/mcp`.
* **Python SDK:** lightweight client (`pip install axiolex`) for namespace access, tool discovery, and execution.
* **`@axiolex/mcp-gateway`:** lightweight Node.js bridge for MCP clients requiring local stdio access. No local Axiolex Python, Redis, or retrieval dependencies are required.

### Core Capabilities

* **Unified catalog:** MCP tools, A2A agent skills, adapter-backed REST services, and local/internal tools indexed in one searchable catalog.
* **Intent-driven discovery:** ranked Top-K tool discovery using BM25S + ColBERT hybrid retrieval, with lexical-only retrieval available by disabling ColBERT.
* **Namespace scoping:** single-scope, multi-scope, and full-catalog discovery across business domains.
* **Normalized execution:** clients execute a selected `tool_id` through one Axiolex contract while provider transport, endpoint resolution, authentication, and protocol-specific execution remain server-side.
* **Provider interoperability:** MCP Streamable HTTP, MCP stdio, and A2A are supported directly; REST-only systems participate through adapters.
* **Flexible client access:** Python SDK, REST / OpenAPI, MCP Streamable HTTP, and the `@axiolex/mcp-gateway` stdio proxy.
* **Management dashboard:** Web UI for provider configuration, namespaces, catalog management, discovery testing, retrieval tuning, credentials, and system status.
* **Reference integrations:** native A2A Agent Card discovery and the `atlassian_rest_to_mcp` Jira adapter for REST-only enterprise systems.

### Discovery and Orchestration Boundary

Axiolex ranks the query and namespace scope it receives.

The AI client or application retains:

* query interpretation and expansion;
* decomposition of multi-step requests;
* namespace selection;
* tool selection;
* workflow sequencing and reasoning over results.

Axiolex provides:

* cataloging;
* namespace-scoped discovery;
* relevance ranking;
* normalized tool execution.

This supports workflows such as:

```text
reason → discover → select → execute → reason
```

### MCP Tools

Axiolex exposes three MCP tools to AI clients:

| Tool | Purpose |
| --- | --- |
| `list_namespaces` | List enabled tool domains and namespace descriptions |
| `axiolex_discover_tools` | Discover ranked tools relevant to a natural-language request |
| `axiolex_execute_tool` | Execute a discovered tool using its `tool_id` and arguments |

### Security

* **Two security boundaries:** client access to Axiolex and Axiolex access to downstream providers are handled separately.
* **Client authentication:** expected to be enforced at the enterprise deployment boundary using OAuth/OIDC, mTLS, API keys, reverse proxies, API gateways, or service meshes. Axiolex does not enforce client authentication directly in the current release.
* **Server-side provider credentials:** downstream credentials are resolved and injected by Axiolex and are not exposed to AI clients or applications.
* **AES-256-GCM encrypted secret storage** for provider credentials.
* **Environment-variable-first credential resolution** with encrypted-store fallback.
* **Credential redaction** from logs, REST payloads, and Redis metadata.
* **Audit metadata:** discovery and execution activity can capture query scope, ranked results, relevance scores, tool/provider identifiers, and execution latency.
* **Authorization extensibility:** RBAC, delegated user identity, and per-user credential propagation can be layered onto the current security boundaries without changing the core discovery and execution contracts.

### Compatibility

* Python 3.10+
* BM25S lexical retrieval
* ColBERT semantic retrieval for hybrid ranking
* Lexical-only mode available by disabling ColBERT
* Redis required for shared catalog state
* Node.js required only for clients using the `@axiolex/mcp-gateway` stdio proxy

### Installation

**Axiolex server:**

```bash
git clone https://github.com/vrraj/axiolex.git && cd axiolex
make install
make start
curl http://localhost:9700/status
```

**Client access:**

* **Python SDK:** `pip install axiolex`
* **MCP Streamable HTTP:** `http://localhost:9700/mcp`
* **MCP stdio:** `npx -y @axiolex/mcp-gateway --endpoint http://localhost:9700/mcp`
* **REST API:** `http://localhost:9700`

### Links

* [GitHub Repository](https://github.com/vrraj/axiolex)
* [PyPI Package](https://pypi.org/project/axiolex/)
* [npm: @axiolex/mcp-gateway](https://www.npmjs.com/package/@axiolex/mcp-gateway)
* [API Documentation](https://vrraj.github.io/axiolex/)
