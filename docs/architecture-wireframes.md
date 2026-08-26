# AxioLex architecture image brief

Create two clean, wide technical architecture diagrams for **AxioLex**, a fast lexical and hybrid retrieval runtime for agentic systems. Use a white background, thin dark-gray outlines, black text, minimal blue accents, simple line icons, and generous whitespace. The diagrams should read as technical documentation, not a marketing graphic. Use at most five or six major boxes per diagram. Avoid gradients, 3D elements, logos, dense paragraphs, or long feature lists.

## `axiolex-system-architecture.png`

**Title:** AxioLex System Architecture  
**Subtitle:** Shared catalog with add-on retrieval for agents and applications

Show a left-to-right / top-to-bottom deployment flow.

1. **Consumers and surfaces** (top row, four columns)

   - **Existing Python app** — uses the `axiolex` library directly.
   - **FastAPI management sidecar** — `axiolex-server` with the web UI and REST API.
   - **External MCP clients** — **Claude Desktop (stdio)** is the primary example; Cursor, Cline, and custom agents can also connect.
   - Add a small note: `axiolex-index` CLI also writes here.

2. **AxioLex runtime** (one central box)

   - `BM25SRetriever` (in-process lexical)
   - `HybridSearchEngine` (optional ColBERT)
   - FastAPI REST handlers
   - `axiolex-mcp-server` — exposes cached tools via `tools/list` and routes calls via `tools/call`

3. **Shared control plane** (one box beside or below the runtime)

   - **Redis**
     - `axiolex:idx:tool:{id}` — discovery fields
     - `axiolex:run:tool:{id}` — runtime JSON
     - `axiolex:catalog:version` — refresh marker
   - **Encrypted secret store** — AES-256-GCM for API keys, bearer tokens, and other provider secrets
   - **Runtime auth resolution**
     - API keys appended as URL query parameters (configurable param name)
     - Bearer tokens sent in the `Authorization` header
     - Environment variables as fallback
     - Secrets decrypted at call time; nothing stored in Redis or YAML

4. **Sources and administration** (bottom or left)

   - `source_files/tools_list.yaml`
   - `source_files/mcp_providers.yaml`
   - **MCP provider discovery**
     - **Streamable HTTP** — remote MCP servers over HTTP (e.g., Tavily, Alpha Vantage, custom hosted servers)
     - **stdio** — local subprocess servers via `npx`, `uvx`, or custom Python executables
   - FastAPI UI provider onboarding, secret storage, reindex

**Arrows:**

- Sources → Redis (administration writes the catalog).
- Management sidecar → Redis and secret store.
- All consumers → Redis (read catalog, build in-memory index locally).
- Runtime → ranked tool / document results back to consumers.

Draw a dotted perimeter around the runtime surfaces and Redis, with the label:

```text
Shared catalog across processes. In-memory BM25 / ColBERT index is per-process.
```

## `axiolex-index-lifecycle.png`

**Title:** AxioLex Index Lifecycle  
**Subtitle:** Catalog in Redis, indexes rebuilt in process memory

This is a left-to-right lifecycle diagram.

1. **Sources** (left)

   - `tools_list.yaml`
   - `mcp_providers.yaml`
   - MCP provider endpoints (Streamable HTTP / stdio)

2. **Administration / refresh** (one box)

   - `axiolex-index refresh` (full rebuild)
   - `POST /mcp-providers/{id}/discover` (per-provider)
   - FastAPI UI "Refresh Index"

   Include a small callout:

   ```text
   Full refresh replaces the catalog atomically
   and bumps axiolex:catalog:version.
   ```

3. **Redis catalog** (one box)

   - discovery hashes
   - runtime JSON
   - catalog version

4. **In-process indexes** (one box)

   - `BM25S` index (always)
   - `ColBERT` embeddings (when hybrid search is enabled)

5. **Query and results** (right)

   - user / agent query
   - tokenize → score → softmax → temperature → cutoff
   - ranked tool or document results
   - routing metadata returned to the caller

**Arrows:**

- Sources → Admin → Redis → In-process indexes.
- Query enters the in-process indexes box.
- Results exit to the right.

## Visual intent

The main message is that **Redis is the shared, durable catalog**, while the **BM25S and ColBERT indexes live in each process's memory**. Management and runtime are intentionally separated so an existing application can embed `axiolex` as a library while a sidecar FastAPI process handles provider onboarding, secret storage, and catalog refresh.
