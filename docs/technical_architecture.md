# Axiolex Technical Architecture

This document describes Axiolex from the top down. Each section adds more detail than the one above it, so a reader can stop at any level and still have a coherent picture.

- **Level 1 — Executive summary**: what Axiolex is and the problem it solves.
- **Level 2 — System overview**: the layers, the shared catalog, and the consumption surfaces.
- **Level 3 — Request lifecycle**: what happens during a `discover` call, end to end.
- **Level 4 — Subsystems**: retrieval, namespaces, MCP provider discovery, security, auditing.
- **Level 5 — Module reference**: file-by-file breakdown of `axiolex/`.
- **Level 6 — Deployment, configuration, and extension points**.

For the outcome-focused narrative and quick-start examples, see the [README](../README.md). For REST endpoint signatures, see the [API reference](api-reference.md).

---

## Level 1 — Executive summary

Axiolex is a **capability discovery service**. It maintains a searchable catalog of enterprise capabilities — MCP tools, A2A endpoints, internal services, and YAML-defined tools — and returns the small subset of capabilities relevant to a given request.

The problem it solves: AI clients and applications are increasingly pointed at large tool registries. Passing every tool definition into the model context wastes tokens, adds latency, and degrades tool selection. Axiolex narrows the candidate set **before** prompt assembly, scoped to the business area the request actually concerns.

Two design decisions shape everything below:

1. **Discovery is separated from execution.** Axiolex finds and ranks capabilities; the consuming application or gateway executes them. The shipped MCP server is read-only with respect to the catalog.
2. **The catalog is shared state; the search indexes are derived state.** Redis holds the canonical catalog. Each process builds its own in-memory BM25S (and optional ColBERT) index from that catalog and rebuilds it when the catalog version changes.

---

## Level 2 — System overview

### Layers

```text
┌─────────────────────────────────────────────────────────────────┐
│                       Consumption surfaces                       │
│   Python SDK · REST API · MCP discovery server · CLI             │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────┴──────────────────────────────────┐
│                         Service layer                            │
│   ToolDiscoveryService · IndexingService · NamespaceService      │
│   McpService · SettingsService · DocumentService                 │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────┴──────────────────────────────────┐
│                       Retrieval engine                           │
│   BM25SRetriever (lexical) · HybridSearchEngine (ColBERT)        │
│   Fusion · Semantic text · Model integrity                       │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────┴──────────────────────────────────┐
│                      Catalog and sources                         │
│   ToolCacheManager (Redis) · MCPDiscovery · YAML registries      │
│   SecretStore · Security utils                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Consumption surfaces

| Surface | Module | What it does |
| --- | --- | --- |
| Python SDK | `axiolex/sdk.py` | Thin HTTP client (`Axiolex`). Only needs `httpx` + `pydantic`. Always importable from the base package. |
| REST API | `axiolex/api/routes.py` | FastAPI app exposing `/discover`, `/retrieve`, `/namespaces`, `/capabilities`, `/mcp-providers`, and secret management endpoints. |
| MCP server | `axiolex/mcp/server.py` | FastMCP server exposing `axiolex_discover_tools`, `axiolex_execute_tool`, and `list_namespaces` tools over stdio or Streamable HTTP. Redis consumer (read for discovery, read+dispatch for execution). |
| CLI | `axiolex/cli.py`, `axiolex/index_cli.py` | `axiolex-server` runs the REST/UI app; `axiolex-index` builds and refreshes the Redis catalog; `axiolex-mcp-server` runs the MCP server. |

The base PyPI package installs only the SDK. Server, ColBERT, and dev dependencies are optional extras (`[server]`, `[colbert]`, `[dev]`). `axiolex/__init__.py` uses conditional imports so the SDK works even when server extras are absent.

### Shared catalog vs. per-process indexes

```text
                   SOURCE DEFINITIONS
        tools_list.yaml · mcp_providers.yaml · namespaces.yaml
                         │
                         ▼
                 catalog refresh (CLI/API/UI)
                         │
                         ▼
                ┌─────────────────┐
                │      REDIS      │
                │ shared catalog  │
                │                 │
                │ discovery data  │  searchable fields per tool
                │ runtime data    │  execution fields per tool
                │ catalog version │  single key, bumped on refresh
                └────────┬────────┘
                         │
              each process reads from here
                         │
           ┌─────────────┼─────────────┐
           ▼             ▼             ▼
      REST server    MCP server    Embedded library
           │             │             │
           ▼             ▼             ▼
      ┌─────────────────────────────────────┐
      │        IN-PROCESS MEMORY            │
      │        (per process, rebuilt)       │
      │                                     │
      │  BM25S index                        │
      │  ColBERT index (optional)           │
      │  namespace → doc-id mapping         │
      └─────────────────────────────────────┘
```

Redis is the source of truth for *what tools exist*. BM25S and ColBERT indexes are *derived* — rebuilt from Redis when the catalog version changes. If a process crashes, its index is lost but Redis is untouched; on restart the index is rebuilt from Redis.

The catalog version key is the bridge: each process checks it before every query (a single `GET`, ~1ms) and rebuilds its in-memory indexes only when the version has changed.

---

## Level 3 — Request lifecycle

This traces an `axiolex_discover_tools` call from the MCP server (or equivalently `client.discover()` from the SDK, or `POST /discover` from REST). All three surfaces converge on the same path.

### Step-by-step

```text
1. Client call
   └─ SDK.discover() / POST /discover / MCP axiolex_discover_tools
        query, namespaces, top_k, hybrid_search, tuning params

2. Surface layer
   └─ routes.py / sdk.py / mcp/server.py
        validate inputs, resolve hybrid_search default from env

3. Service layer
   └─ ToolDiscoveryService.discover_tools()
        validate namespace IDs against the registry (fail on unknown)
        delegate to retriever

4. Retrieval engine
   └─ BM25SRetriever.retrieve_documents()
        a. reload_cache_if_changed()  → check Redis catalog version
                                        rebuild BM25S+ColBERT if changed
        b. build namespace weight mask / eligible doc-id set
        c. tokenize query (BM25S + PyStemmer)
        d. BM25S score over eligible docs
        e. if hybrid: HybridSearchEngine.search()
              ColBERT score over eligible docs
              softmax_score_fusion() blends BM25 + ColBERT
        f. softmax normalization (lexical) or fused score (hybrid)
        g. cutoff / min_hybrid_score filtering
        h. sort, assign rank, limit to top_k

5. Service layer (continued)
   └─ ToolDiscoveryService._to_tool_definition()
        merge retrieval result with runtime metadata from Redis
        attach endpoint, transport, provider, params, inputSchema

6. Audit
   └─ _write_audit_record()
        JSONL entry: timestamp, caller, query, namespaces, top-K, latency

7. Response
   └─ tools[] with name, rank, relevance_score, params, endpoint, ...
```

### Two retriever modes

| Mode | Factory | Redis | Use case |
| --- | --- | --- | --- |
| Default (read-write) | `get_retriever()` | Required, fail-fast | REST/UI server. Can refresh local YAML into Redis. |
| Read-only cache consumer | `get_tool_discovery_retriever()` | Required, fail-fast | MCP server. Never writes to Redis; only detects version changes and rebuilds. |

Both require Redis. The server fails fast at startup if Redis is unreachable or the catalog is empty. There is no in-memory cache backend; Redis is a hard requirement for the shared-service architecture.

### Catalog refresh paths

| Path | Trigger | Scope | Version bump? |
| --- | --- | --- | --- |
| Full refresh | `axiolex-index refresh` / `make index-refresh` | All YAML tools + all enabled MCP providers | Yes — atomic `replace_all_tools()` |
| Single-provider discovery | `GET /mcp-providers/{id}/discover` (UI "Retrieve Tools") | One provider's tools | Yes — `cache_all_discovery()` bumps version |
| Local YAML sync | `refresh_local_yaml_cache()` (server startup) | YAML entries only | No (per-entry writes) |

After any version bump, every running process detects the change on its next query and rebuilds its in-memory indexes automatically. No restart needed.

---

## Level 4 — Subsystems

### 4.1 Retrieval engine

The retrieval engine lives in `axiolex/core/retriever.py` (lexical) and `axiolex/retrieval/` (hybrid).

#### Lexical path (BM25S)

`BM25SRetriever` builds a text corpus from each document's `title`, `content`, and `keywords`, tokenizes with PyStemmer, and indexes with `bm25s.BM25(method="lucene")`. At query time it tokenizes the query, scores against the index, applies a weight mask for namespace filtering, then:

1. Optionally filters zero-score results (`ignore_zero`).
2. Converts BM25 scores to softmax probabilities with `temperature`.
3. Filters by `llm_tools_cutoff` (minimum softmax percentage).
4. Sorts descending, assigns 1-based `rank`, limits to `top_k`/`max_results`.
5. Sets `relevance_score = softmax_score`.

#### Hybrid path (BM25S + ColBERT)

When `hybrid_search=True` and ColBERT is installed and enabled, `HybridSearchEngine` runs alongside BM25S:

1. BM25S produces positive-score lexical candidates.
2. `ColBERTIndex` (backed by `fastembed.LateInteractionTextEmbedding`) scores the eligible document set with late-interaction max-sim.
3. `softmax_score_fusion()` normalizes each model's scores independently with softmax, then blends with configurable `bm25_weight` / `colbert_weight`.
4. `min_hybrid_score` optionally removes weak fused results.
5. Results are sorted by `hybrid_score`, ranked, and limited.
6. `relevance_score = hybrid_score`.

ColBERT document embeddings are built eagerly during index rebuild (alongside BM25S). Queries only compute the query embedding and score against the pre-built document index.

**Score-scale mismatch is the reason for independent softmax.** BM25 and ColBERT raw scores live on different numeric scales. Fusing by rank alone throws away the confidence signal. Axiolex turns each model's candidates into its own probability distribution, then blends probabilities.

**Guardrail:** softmax is applied only to bounded candidate lists (positive BM25 candidates and top ColBERT candidates capped by `candidate_limit`), not the whole database. A large zero-score tail would make the distribution noisy.

If hybrid is requested but unavailable (ColBERT not installed, model not initialized), the request **fails clearly** — it does not silently fall back to lexical.

#### Model integrity

`retrieval/model_integrity.py` pins the default `colbert-ir/colbertv2.0` model to a specific Hugging Face commit and verifies SHA-256 and file size before FastEmbed loads it. `axiolex model-ensure` downloads and verifies explicitly. Setting `AXIOLEX_COLBERT_MODEL` to another model selects a user-managed model (no integrity guarantee).

#### Unified relevance contract

Every result — lexical or hybrid — carries:

- `rank` (1-based, assigned after final sort + limit)
- `relevance_score` (0.0–1.0: `softmax_score` in lexical mode, `hybrid_score` in hybrid mode)

Consumers filter on `relevance_score` without knowing which mode ran. Detailed component scores (`bm25_score`, `colbert_score`, etc.) are included for diagnostics.

### 4.2 Namespace scoping

Namespaces are Axiolex's lightweight capability map. They define the search scope *before* retrieval — not a post-filter.

**Registry:** `source_files/namespaces.yaml`, managed by `services/namespace_service.py` (CRUD over YAML). Each namespace has `id`, `name`, `description`, `enabled`.

**Assignment:** Tools inherit namespaces from their MCP provider config or YAML metadata. A tool can belong to multiple namespaces.

**Filtering mechanism:**

- **BM25S**: a numpy weight mask zeroes out ineligible documents before scoring (`_build_weight_mask`). This is a hard constraint — ineligible docs never enter the candidate set.
- **ColBERT**: an `eligible_doc_ids` set restricts which documents are scored (`ColBERTIndex.search` accepts it).

Multiple namespaces use **union semantics** — the eligible set is the union of documents in any of the requested namespaces. `namespaces=["all"]` or omitting namespaces searches everything.

**Unknown namespaces fail explicitly.** Passing a namespace ID not in the registry returns a validation error rather than silently widening the search.

**Consumer-facing surface:** `GET /capabilities` and `list_namespaces()` (MCP) return only enabled namespaces with `id`, `name`, `description` — the clean capability map for applications and LLMs.

### 4.3 MCP provider discovery

`axiolex/mcp/discovery.py` discovers tools from configured MCP providers and normalizes them into the shared catalog format.

#### Transports

| Transport | Method | Use case |
| --- | --- | --- |
| Streamable HTTP | `_discover_streamable_http()` | Remote MCP servers (Alpha Vantage, Tavily). Uses MCP SDK `streamable_http_client`. |
| stdio | `_discover_stdio()` | Local subprocess servers. Spawns `command` + `args`, speaks MCP over stdin/stdout, calls `tools/list`, terminates on completion. |

#### Normalization

`_normalize_tool()` and `_normalize_tool_from_mcp()` convert raw provider tool definitions into Axiolex's canonical shape: `id`, `title`, `description`, `tool_name`, `params`, `provider`, `source`, `namespaces`, plus runtime metadata (`transport`, `endpoint` or `command`/`args`, auth metadata).

#### Provider config

`MCPProviderConfig` (Pydantic) holds `id`, `name`, `transport`, `endpoint`/`command`+`args`, `auth`, `namespaces`, `enabled`, `features`, `limits`. It rejects inline `secret_value`, credentials in URLs, and credentials in headers at validation time.

`load_namespaces()` and `validate_provider_namespaces()` ensure provider-assigned namespaces exist in the registry before discovery proceeds.

#### Indexing pipeline

`services/indexing_service.py` (`ToolIndexingService`) orchestrates the full refresh:

1. Load enabled YAML tools from `tools_list.yaml`.
2. Discover tools from all enabled MCP providers via `MCPDiscovery.discover_all()`.
3. Deduplicate by tool ID.
4. Validate that every tool has complete runtime metadata (`tool_name`, `transport`, `endpoint` or `command`).
5. Atomically replace the Redis catalog via `ToolCacheManager.replace_all_tools()`.
6. Bump the catalog version.

`--allow-partial` skips the abort-on-empty-provider behavior for intentional partial catalogs.

### 4.4 Security

#### Credential resolution

`mcp/security.py` provides `resolve_secret()`, the single entry point for credential resolution:

1. **OS environment** — the variable named in `auth.secret_env` (`.env` path). Checked first.
2. **Encrypted secret store** — `mcp/secret_store.py`, keyed by provider ID.
3. **`None`** — discovery fails with a clear error.

Both paths coexist without migration. A provider can use `.env` only, the encrypted store only, or both (env takes precedence).

#### Encrypted secret store

`mcp/secret_store.py` (`SecretStore`) encrypts credentials with AES-256-GCM and stores them in `source_files/mcp_secrets.enc` (git-ignored, file mode `0600`). The master key is `AXIOLEX_SECRET_MASTER_KEY` in `.env` (generate with `openssl rand -hex 32`).

REST API (secrets are never returned, only their existence):

- `POST /mcp-providers/{id}/secret` — encrypt and store.
- `GET /mcp-providers/{id}/secret` — returns `{"has_secret": true/false}`.
- `DELETE /mcp-providers/{id}/secret` — remove.

#### What is never exposed

- Provider YAML stores only `auth.secret_env` (env var name) and `auth.key_param` (query-param name), never the secret value.
- REST endpoints (`/mcp-providers`, `/mcp-providers/{id}/discover`) and the Redis runtime cache expose only `auth.type`, `auth.secret_env`, `auth.key_param`.
- `redact_url()` replaces `apikey`, `key`, `token`, `tavilyApiKey`, and similar query parameters with `REDACTED` before any URL is logged.

#### Transport-specific credential handling

- **Bearer auth (Streamable HTTP)**: token sent in `Authorization: Bearer` header via a custom `httpx.AsyncClient` — kept out of the URL.
- **API key auth (Streamable HTTP)**: appended as a URL query parameter (required by providers like Alpha Vantage). `redact_url()` mitigates log exposure.
- **stdio**: no credential injection; subprocess receives credentials through its own environment.

### 4.5 Discovery audit logging

`services/tool_discovery_service.py` writes one JSONL record per `discover`/`axiolex_discover_tools` call after retrieval completes.

**Logged:** timestamp (UTC, ms), caller, query, namespaces, top-K tool names + `relevance_score`, total latency in ms.

**Not logged:** raw BM25/ColBERT/fusion internals, tool parameters, endpoints, request headers, caller IP.

**Properties:** logging does not change discovery behavior; a logging failure does not fail an otherwise successful discovery; file rotates at 10 MB with 5 backups; `caller` is reserved for future authenticated identity.

**Location:** `logs/discovery_audit.jsonl` (override with `AXIOLEX_LOG_DIR`).

---

## Level 5 — Module reference

### `axiolex/` (package root)

| File | Purpose |
| --- | --- |
| `__init__.py` | Conditional imports: SDK always available; server classes only with `[server]` extra. `__version__` from package metadata. |
| `sdk.py` | `Axiolex` — thin HTTP client. `discover()`, `retrieve()`, `health()`, `list_namespaces()`. Only needs `httpx` + `pydantic`. |
| `cli.py` | `axiolex-server` entry point — runs the FastAPI app. |
| `index_cli.py` | `axiolex-index` entry point — `refresh` and `status` subcommands for the Redis catalog. |

### `axiolex/core/`

| File | Key classes | Purpose |
| --- | --- | --- |
| `config.py` | `BM25SSettings`, `DocumentConfig`, `MCPConfig`, `ServerConfig`, `Config`, `load_config()`, `save_config()` | Configuration management. Loads from YAML or env vars. |
| `retriever.py` | `Document`, `BM25SRetriever`, `get_retriever()`, `get_tool_discovery_retriever()`, `retrieve_documents()` | Core retrieval engine. BM25S indexing, softmax scoring, namespace weight masks, cache reload detection, hybrid search delegation. |
| `cache.py` | `RedisConfig`, `ToolCacheManager`, `get_cache_manager()` | Redis operations. Discovery keys (`axiolex:idx:tool:{id}`), runtime keys (`axiolex:run:tool:{id}`), catalog version, atomic `replace_all_tools()`, invalidation. |

### `axiolex/retrieval/`

| File | Key classes | Purpose |
| --- | --- | --- |
| `config.py` | `HybridSearchSettings` | Env-driven hybrid config (`AXIOLEX_HYBRID_*`). |
| `colbert.py` | `ColBERTModelConfig`, `ColBERTDocument`, `ColBERTSearchResult`, `ColBERTIndex` | Pure-Python ColBERT index via `fastembed`. Embed, search, rerank. |
| `hybrid.py` | `HybridSearchEngine` | Orchestrates BM25 + ColBERT fusion. Owns the `ColBERTIndex`. |
| `fusion.py` | `softmax_score_fusion()`, `reciprocal_rank_fusion()` | Score blending. Independent softmax per model, then weighted blend. |
| `semantic_text.py` | `documents_to_colbert()`, `document_semantic_text()` | Converts canonical documents into ColBERT-ready text. |
| `indexing.py` | `load_documents_from_yaml()`, `build_colbert_index_from_yaml()` | YAML → ColBERT index convenience path. |
| `model_integrity.py` | `ModelArtifact`, `ensure_default_colbert_model()`, `verify_model_artifacts()` | Pinned, SHA-256-verified ColBERT model download. |

### `axiolex/mcp/`

| File | Key classes | Purpose |
| --- | --- | --- |
| `discovery.py` | `MCPProvider`, `MCPProviderAuth`, `MCPProviderConfig`, `MCPDiscovery` | Multi-provider tool discovery (HTTP, streamable-http, stdio), normalization, YAML persistence. |
| `server.py` | `DiscoveredTool`, `DiscoverToolsResult`, `NamespaceInfo`, `ExecuteToolResult`, `create_mcp_server()`, `main()` | FastMCP server exposing `axiolex_discover_tools`, `axiolex_execute_tool`, and `list_namespaces`. |
| `security.py` | `resolve_secret()`, `append_api_key()`, `contains_inline_credential()`, `redact_url()` | Credential resolution, URL-safe key injection, log redaction. |
| `secret_store.py` | `SecretStore`, `get_secret_store()` | AES-256-GCM encrypted credential store. |
| `client.py` | — | MCP client for connecting to Axiolex's MCP server. |
| `merger.py` | — | Tool merger: deduplication, conflict resolution, schema merging. |
| `alphavantage_adapter.py` | `AlphaVantageAdapter` | Alpha Vantage-specific MCP adapter. |

### `axiolex/mcp/execution/`

| File | Key classes | Purpose |
| --- | --- | --- |
| `errors.py` | `ExecutionError`, error code constants | Phase 1 error taxonomy: `TOOL_NOT_FOUND`, `TOOL_UNAVAILABLE`, `INVALID_ARGUMENTS`, `UPSTREAM_TIMEOUT`, `UPSTREAM_ERROR`, `RATE_LIMITED`, `INTERNAL_ERROR`. |
| `adapters.py` | `TransportAdapter`, `StreamableHttpAdapter`, `StdioAdapter`, `get_adapter()` | Transport adapter layer. Each adapter calls `ClientSession.call_tool()` (JSON-RPC 2.0) over its transport and normalizes the result. New transports are added behind this boundary. |
| `service.py` | `ToolExecutionService`, `execute_tool()` | Dispatcher core: resolve `tool_id` from catalog → validate arguments against current schema → dispatch via adapter → enforce timeout → normalize result → emit `execution_id` + audit log. Phase 1: no auth/security enforcement. |

### `axiolex/services/`

| File | Key classes | Purpose |
| --- | --- | --- |
| `tool_discovery_service.py` | `ToolDiscoveryService`, `discover_tools()` | Application-facing discovery. Validates namespaces, calls retriever, maps to tool definitions, writes audit log. |
| `indexing_service.py` | `IndexingResult`, `ToolIndexingService` | Builds and atomically replaces the Redis catalog from YAML + MCP providers. |
| `namespace_service.py` | `list_namespaces()`, `list_consumable_namespaces()`, `add_namespace()`, `update_namespace()`, `delete_namespace()` | CRUD over `namespaces.yaml`. Path resolution: env var → CWD → package. |
| `mcp_service.py` | `get_all_providers()`, `add_provider()`, `update_provider()`, `discover_provider_tools()` | MCP provider management for the REST API. |
| `settings_service.py` | `get_settings()`, `update_settings()` | BM25S settings management. |
| `document_service.py` | `switch_document_file()` | Document file switching. |

### `axiolex/api/`

| File | Key classes | Purpose |
| --- | --- | --- |
| `routes.py` | `create_app()`, `SwitchFileRequest`, `FileInfo` | FastAPI app. All REST endpoints: `/discover`, `/retrieve`, `/namespaces`, `/capabilities`, `/mcp-providers`, `/documents`, `/settings`, `/status`, secret management. |
| `client.py` | `BM25SClient` | Python HTTP client for the REST service (legacy, pre-SDK). |
| `models.py` | `RetrieveRequest`, `RetrieveResponse`, `RetrievedDocument`, `BM25SSettings` | Pydantic request/response models. |

### `axiolex/db/`

| File | Purpose |
| --- | --- |
| `document_service.py` | `get_documents_from_cache()` — retrieves documents from Redis. |

### `axiolex/ui/`

| Path | Purpose |
| --- | --- |
| `templates/tool-router.html` | Jinja2 template for the demo web UI. |
| `static/` | CSS and JS assets for the UI. |

### `axiolex/utils/`

| File | Purpose |
| --- | --- |
| `file_utils.py` | `is_source_entry_enabled()`, `get_available_document_files()` — enabled-flag filtering and file discovery. |

---

## Level 6 — Deployment, configuration, and extension

### Deployment patterns

| Pattern | What runs | Redis | Best for |
| --- | --- | --- | --- |
| Thin SDK consumer | Application + `axiolex` SDK | Remote (managed) | Applications that only call `discover()` |
| Management sidecar | `axiolex-server` (REST/UI) + application with SDK | Local or remote | Admin UI + provider onboarding alongside an existing app |
| Standalone platform | `make start` (Redis + REST/UI + MCP server) | Local Docker | Full local stack |
| Docker Compose | Axiolex + Redis containers | Internal to compose | Production-like, Redis not exposed |
| Embedded library | `BM25SRetriever` in-process | Not required | Direct Python usage with local YAML (no shared catalog) |

### Client connection patterns (Claude Desktop and other MCP clients)

MCP clients connect to Axiolex over one of two transports. The choice has security implications:

| Pattern | Transport | Secrets on client | Best for |
| --- | --- | --- | --- |
| **HTTP (recommended)** | `streamable-http` | None — server holds master key + encrypted store | Local dev, enterprise, any multi-user deployment |
| **stdio** | `stdio` | Depends on OS env or config-dir resolution | Air-gapped machines, no persistent server possible |

**HTTP pattern:** The AxioLex server runs as a persistent process (`make start` or Docker), loads `.env` (master key + Redis config), and decrypts provider API keys from `source_files/mcp_secrets.enc` into process memory at runtime. The client config contains only a URL — no secrets, no paths, no environment variables. API key rotation is a single operation on the server; no client reconfiguration needed.

**stdio pattern:** Claude Desktop spawns Axiolex as a subprocess with CWD set to `/` and no access to the project `.env` file. The subprocess cannot locate the encrypted secrets store by default. This pattern currently requires API keys in the OS environment or completion of the [config-dir resolution work](../axiolex_to_do.md). For most deployments, the HTTP pattern is simpler and more secure.

See [Claude MCP integration](claude-mcp.md) for setup instructions for both patterns.

### Where Redis can run

Redis is required for the shared catalog but does not need to run in Docker or inside the package. All Axiolex processes sharing a catalog must use the same Redis host/port/db.

```bash
export AXIOLEX_REDIS_HOST=localhost
export AXIOLEX_REDIS_PORT=6380
export AXIOLEX_REDIS_DB=0
```

Do not expose Redis publicly. External clients connect to the Axiolex MCP/REST endpoint and do not need Redis access.

### Redis key layout

| Key pattern | Contents |
| --- | --- |
| `axiolex:idx:tool:{tool_id}` | Discovery metadata: title, description, tool_name, params, category, provider, source, namespaces |
| `axiolex:run:tool:{tool_id}` | Runtime metadata: transport, endpoint or command+args, auth metadata, full param schema |
| `axiolex:catalog:version` | Version marker (UUID). Bumped on `replace_all_tools()` and per-provider discovery. |

Per-entry TTLs are env-driven (`AXIOLEX_REDIS_DISCOVERY_TTL_SECONDS`, `AXIOLEX_REDIS_RUNTIME_TTL_SECONDS`). Set to `0` for keys that persist until explicit refresh or invalidation.

### Configuration hierarchy

1. **Default values** (in code)
2. **`settings.yaml`** (YAML file)
3. **Environment variables** (override YAML)

### Key environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `BM25S_HOST` / `BM25S_PORT` | `0.0.0.0` / `9700` | REST server bind |
| `BM25S_TEMPERATURE` | `0.5` | Softmax temperature |
| `BM25S_IGNORE_ZERO` | `true` | Filter zero-score results |
| `BM25S_CUTOFF` | `10.0` | Minimum softmax percentage |
| `AXIOLEX_HYBRID_ENABLED` | `false` | Enable ColBERT hybrid search |
| `AXIOLEX_COLBERT_MODEL` | `colbert-ir/colbertv2.0` | ColBERT model ID |
| `AXIOLEX_COLBERT_CACHE_DIR` | `~/.cache/axiolex/fastembed` | Model cache directory |
| `AXIOLEX_HYBRID_BM25_WEIGHT` | `0.4` | BM25 blend weight |
| `AXIOLEX_HYBRID_COLBERT_WEIGHT` | `0.6` | ColBERT blend weight |
| `AXIOLEX_HYBRID_CANDIDATE_LIMIT` | `100` | Per-model candidate cap before fusion |
| `AXIOLEX_REDIS_HOST` / `AXIOLEX_REDIS_PORT` / `AXIOLEX_REDIS_DB` | `localhost` / `6380` / `0` | Redis connection |
| `AXIOLEX_SECRET_MASTER_KEY` | — | AES-256-GCM master key for the encrypted secret store |
| `AXIOLEX_LOG_DIR` | `logs` | Audit log directory |

### Extension points

**Add an MCP provider:** Add config to `mcp_providers.yaml` (or via UI/REST). Assign namespaces. Run `make index-refresh` or click "Retrieve Tools". No code changes needed for standard transports.

**Add a custom stdio server:** Place a Python MCP server in `stdio_servers/`, register in `mcp_providers.yaml` with `transport: stdio`, `command: python`, `args: ["stdio_servers/my_tools/server.py"]`.

**Add a pre-built server:** Use `uvx` or `npx` as the command. Pin `mcp` version with `--with mcp==x.y.z` if the server is incompatible with the latest MCP SDK.

**Add a new retrieval backend:** Implement a new retriever class in `axiolex/core/` or `axiolex/retrieval/`, add configuration in `config.py`, and wire it into `BM25SRetriever` or create a parallel retriever.

**Add a new cache backend:** Implement the `ToolCacheManager` interface in `axiolex/core/cache.py` or create a parallel implementation. Currently Redis is the only backend.

### Performance characteristics

| Collection size | Indexing | Lexical search |
| --- | --- | --- |
| <100 tools | sub-second | near-instant |
| 100–1,000 tools | low seconds | typically <100ms |
| 1,000+ tools | depends on size/content | 100–500ms (lexical); hybrid adds query embedding cost |

BM25S and ColBERT indexes are held in process memory. The only per-query Redis call is a single `GET` on the catalog version key (~1ms) when the version is unchanged.

---

## Cross-references

- [README](../README.md) — outcome-focused narrative, quick start, install
- [API reference](api-reference.md) — REST endpoint signatures and response schemas
- [Setup & usage](setup-usage.md) — deployment and operations guide
- [MCP providers guide](mcp_providers.md) — provider configuration in depth
- [Architecture wireframes](architecture-wireframes.md) — UI wireframes
- [Claude MCP integration](claude-mcp.md) — Claude Desktop setup
