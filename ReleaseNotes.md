# Release Notes

## Version 2.0.0 - Unified Server Architecture

### Architecture

- **Merged MCP HTTP server into the API server process.** REST and MCP streamable HTTP are now served from a single FastAPI process on port 9700. MCP is available at `http://localhost:9700/mcp`. The separate MCP HTTP server on port 9701 has been removed.
- **Single retriever instance shared across REST and MCP.** Eliminates duplicate BM25S index and ColBERT model loads — memory reduced from ~4.4 GB (two processes) to ~1.86 GB (one process).
- **@axiolex/mcp-gateway npx proxy** for stdio-only clients (Claude Desktop, Cursor, Codex). A ~120-line Node.js proxy that bridges stdio to the Axiolex HTTP endpoint. No Python, Redis, or ML libraries needed on the client — only Node.js. Client memory: ~86 MB vs ~1.8 GB for the Python stdio server.

### Breaking Changes

- **Port 9701 removed.** The standalone MCP HTTP server no longer runs. External clients using `http://localhost:9701/mcp` must update to `http://localhost:9700/mcp`.
- **`make start` launches one process** instead of two. The `MCP_PORT` Makefile variable has been removed.
- **Claude Desktop / Cursor / Codex config** must point at `http://localhost:9700/mcp` (HTTP) or use the npx proxy for stdio.

### Improvements

- `make start` starts Redis, refreshes the catalog, and launches a single API server serving both REST and MCP.
- `make inspector` connects to port 9700 `/mcp` instead of the old port 9701.
- Docker Compose no longer includes a commented-out MCP container section.
- Documentation updated across README, claude-mcp, api-reference, architecture, app_reference, setup-usage, and product-specifications.
- All 123 tests pass.

### Migration

1. Update any MCP client configs from `localhost:9701/mcp` to `localhost:9700/mcp`.
2. For stdio clients, use the npx proxy: `npx -y @axiolex/mcp-gateway --endpoint http://localhost:9700/mcp`.
3. Run `make stop` to clear any old processes, then `make start`.

---

## Version 1.0.2 - Badge Fix

### Changes
- Fixed GitHub Release badge URL to use `/v/release` instead of `v-release`.
- No functional changes; badge display fix only.

---

## Version 1.0.0 - Initial Public Release

### Overview

`axiolex` is a lightweight retrieval and routing layer for agentic Python applications, REST services, LLM tool-selection flows, and MCP-based tool discovery.

This first public release focuses on selecting the right tools, documents, or workflow records before prompt assembly. It combines a fast lexical retrieval path with optional ColBERT semantic hybrid search, preserves runtime and artifact metadata, and exposes the same discovery surface through Python, REST, Web UI, and MCP entry points.

The complete API surface is documented in [docs/api-reference.md](https://vrraj.github.io/axiolex/api-reference.html).

---

## Core Capabilities

### Tool And Resource Routing
- Route natural-language requests to relevant tools, documents, or workflow records.
- Keep LLM context smaller by returning only the most relevant candidates.
- Preserve execution metadata such as provider, transport, endpoint, parameters, and artifact hints.
- Support static YAML catalogs, runtime-added documents, Redis-backed catalogs, and MCP-discovered tools.

### Retrieval Modes
- Default lexical retrieval for fast, deterministic matching without a vector database.
- Optional ColBERT hybrid search for deployments that need semantic recall alongside lexical precision.
- Request-time controls for temperature, result limits, lexical cutoff, hybrid score threshold, and hybrid weighting.
- Normalized score metadata across Python, REST, UI, and MCP discovery responses.

### MCP Discovery
- Streamable HTTP MCP server exposing a read-only `discover_tools` tool.
- Returns execution-ready downstream tool definitions with names, parameter schemas, endpoints, transports, and providers.
- Supports `max_tools`, lexical discovery, and optional hybrid discovery.
- Keeps execution, authentication, guardrails, and audit logging in the host application or a companion gateway.

### Catalog And Index Management
- Redis-backed tool catalog that separates searchable discovery data from runtime execution records.
- One-shot `axiolex-index refresh` command to rebuild the catalog from YAML tools and enabled MCP providers.
- `axiolex-index status` command for catalog inspection.
- Atomic catalog replacement, provider refresh handling, and validation for incomplete runtime metadata.

### REST Service And Demo UI
- FastAPI REST service for retrieval, indexing, document management, settings, and status.
- Demo Web UI for discovering tools, tuning retrieval parameters, inspecting result scores, and managing indexed tools.
- UI support for local tools, MCP tools, MCP provider configuration, document-file switching, reloads, reindexing, and service status.
- Hybrid-search availability is surfaced in settings, status, reindex responses, and the UI.

### Response And Metadata Contract
- Pydantic request and response models for type-safe integrations.
- Stable document shape with `metadata`, `runtime`, `artifact`, and `params` fields.
- Search responses include ranked documents, result counts, search mode, settings, and available score fields.
- Artifact-aware metadata lets host applications render charts, tables, or other UI payloads outside the LLM text path.

### Configuration
- YAML, environment-variable, and CLI-driven configuration paths.
- Runtime settings updates through the REST API.
- Optional Redis, MCP provider, and hybrid-search settings for deployed tool catalogs.

---

## Documentation Structure

- **[README.md](https://github.com/vrraj/axiolex#readme)** - Quick start, architecture, search behavior, MCP setup, and deployment notes.
- **[docs/api-reference.md](https://vrraj.github.io/axiolex/api-reference.html)** - Public API, REST endpoints, models, and examples.
- **[docs/architecture.md](https://vrraj.github.io/axiolex/architecture.html)** - Component ownership, Redis catalog lifecycle, and index refresh behavior.
- **[examples/](https://github.com/vrraj/axiolex/tree/main/examples)** - Python, REST, MCP, and provider integration examples.
- **[ReleaseNotes.md](https://github.com/vrraj/axiolex/blob/main/ReleaseNotes.md)** - Version history.

---

## Public API Surface

Stable Python entry points:
- `BM25SRetriever(settings, document_file)` - In-process retriever and router.
- `BM25SRetriever.add_documents(documents)` - Add documents or tool records.
- `BM25SRetriever.retrieve_documents(...)` - Retrieve ranked documents with lexical or optional hybrid search.
- `discover_tools(...)` - Return ranked, execution-ready tools for agentic routing.
- `BM25SClient(base_url)` - HTTP client for the REST service.

Stable REST workflows:
- `POST /retrieve` - Search documents or tools.
- `POST /index` - Build or rebuild an index from supplied records.
- `GET /documents`, `POST /documents`, `DELETE /documents/{id}` - Manage documents and tool records.
- `POST /documents/reload` - Reload documents from configured sources.
- `POST /documents/reindex-bm25s` - Rebuild enabled retrieval indexes.
- `GET /settings`, `POST /settings` - Read and update retrieval settings.
- `GET /status` - Inspect service and hybrid-search readiness.
- `GET /mcp-providers`, `POST /mcp-providers`, `PUT /mcp-providers/{id}`, `DELETE /mcp-providers/{id}` - Manage MCP provider configuration.
- `GET /mcp-providers/{id}/discover` - Discover tools from a configured provider.

Stable CLI workflows:
- `axiolex-server` - Start the REST service and Demo Web UI.
- `axiolex-index refresh` - Rebuild the Redis tool catalog from YAML and MCP providers.
- `axiolex-index status` - Inspect Redis catalog status.
- `axiolex-mcp-server` - Start the read-only MCP discovery server.

Stable response contracts:
- `Document` - Document or tool representation.
- `RetrieveRequest` and `RetrieveResponse` - Search request and result contract.
- `RetrievedDocument` - Ranked result with metadata and score fields.
- `BM25SSettings` and `SettingsResponse` - Retrieval and service settings.

---

## Compatibility

- Python 3.10+
- Base install supports lexical retrieval with BM25S and PyStemmer.
- Optional ColBERT hybrid search is available through the `axiolex[colbert]` extra and `AXIOLEX_HYBRID_ENABLED=true`.
- FastAPI, httpx, and Jinja2 support the REST service, client, and Demo Web UI.
- Redis is required for the shared MCP tool catalog and read-only MCP discovery server.

---

## Notes

This release establishes the stable 1.x API contract for `axiolex`.

The primary focus is progressive tool discovery and resource routing for agentic systems, especially where large tool catalogs, MCP providers, runtime metadata, or artifact-producing workflows need to be filtered before LLM prompt assembly.

Backward compatibility will be maintained within the 1.x series.
