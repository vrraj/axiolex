# Axiolex v1.0 — Tool Discovery and Retrieval Routing Architecture

## 1. Objective

Build **Axiolex**, a compact retrieval and tool-routing layer that sits between a user prompt and LLM inference, evaluating intent on the fly and dynamically injecting only the relevant tools, documents, or workflows into the prompt.

Axiolex keeps LLM context windows clean, preserves critical runtime metadata, and short-circuits heavyweight UI artifacts so rendered assets stay out of the LLM text path.

The core lifecycle is:

```text
Tool / Document Sources
   (YAML registries + MCP providers)
   ↓
Discovery & Normalization
   ↓
Redis Catalog (discovery + runtime data)
   ↓
Retrieval Index (BM25S in-process, optional ColBERT)
   ↓
Ranked Results (with runtime + artifact metadata)
   ↓
Host application / gateway decides what to execute
```

Axiolex is **not an LLM**, does not execute downstream tools itself, and does not train models. The shipped MCP discovery server is read-only. Execution, authentication, guardrails, and observability belong in the host application or a future `call_tool` gateway.

---

## 2. Architectural Principle

Tool-discovery and routing concerns must be separated from tool execution.

The shipped system deliberately stops at **selection**: rank the relevant tools and documents, then return the metadata a gateway needs to decide what happens next.

```text
             Sources
                ↓
        Redis Catalog (shared)
                ↓
       ┌────────┼────────┐
       ↓        ↓        ↓
   BM25S    ColBERT   MCP Server
   (lexical) (semantic) (discover_tools)
       │        │        │
       └────────┼────────┘
                ↓
        Ranked results + runtime metadata
                ↓
        Host gateway (execution, auth, policy)
```

The retrieval engine must not contain assumptions about specific providers, transports, or execution semantics. Provider-specific behavior lives in adapters and configuration, not in the core retriever.

---

## 3. Technology Stack

| Category | Technology | Role |
| --- | --- | --- |
| Runtime | Python (>=3.10) | Application and retrieval implementation |
| Web framework | FastAPI | REST APIs and static UI |
| ASGI | Uvicorn | Application runtime |
| Lexical retrieval | BM25S + PyStemmer | Fast, deterministic keyword search (default) |
| Semantic retrieval | ColBERT (fastembed / ONNX) | Optional late-interaction hybrid search |
| Cache / catalog | Redis 7 | Shared tool catalog and version tracking |
| MCP | Python MCP SDK | Tool discovery and the Axiolex MCP server |
| HTTP client | httpx | Outbound provider requests |
| Validation | Pydantic | API and config models |
| Secrets | cryptography (AES-256-GCM) | Encrypted secret store |
| Templating | Jinja2 | Web UI |
| Testing | pytest | Unit/integration/API tests |

The base install is lexical-only and does not download models. ColBERT is an optional extra (`axiolex[colbert]`).

Do not introduce PostgreSQL, Spark, Kafka, MLflow, vector databases, or agent frameworks for v1.0.

---

## 4. High-Level Architecture

```text
                         Web UI / REST Client
                                 │
                              FastAPI
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
   Retrieve API            Provider API            Document API
        │                        │                        │
        └────────────────────────┼────────────────────────┘
                                 ↓
                         AXIOLEX CORE
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
   Retrieval Engine        MCP Discovery            Indexing Service
   (BM25S / ColBERT)       (provider adapters)     (catalog builder)
        │                        │                        │
        └────────────────────────┼────────────────────────┘
                                 ↓
                          Redis Catalog
                          (shared, required)

                                 ▲
                                 │
                          MCP Server (read-only)
                                 │
                       External LLM Agent / Client
```

All interfaces (library, REST, MCP) ultimately query the same Redis-backed catalog and build the same in-process retrieval indexes.

---

## 5. Repository Structure

```text
axiolex/
├── axiolex/
│   ├── core/                 # Retrieval engine, Redis cache, configuration
│   ├── retrieval/            # Hybrid search, ColBERT, score fusion
│   ├── mcp/                  # MCP discovery, server, security, secret store
│   ├── api/                  # FastAPI routes, HTTP client, request/response models
│   ├── services/             # Catalog indexing, provider management, settings
│   ├── ui/                   # Web UI templates and static assets
│   ├── cli.py                # Server entry point
│   └── index_cli.py          # Catalog refresh entry point
├── source_files/
│   ├── tools_list.yaml       # Static tool catalog
│   ├── mcp_providers.yaml    # MCP provider configurations
│   └── documents.yaml        # Static document registry
├── stdio_servers/            # Local stdio MCP server examples
├── tests/
├── docs/
├── examples/
├── Makefile
├── pyproject.toml
└── README.md
```

---

## 6. Retrieval Engine

Axiolex supports two retrieval modes over the same catalog.

## Lexical Search (default)

BM25S + PyStemmer for fast, deterministic keyword matching. Works out of the box with no model downloads.

```text
User Query
   ↓
Tokenization (BM25S + PyStemmer)
   ↓
BM25S Score Calculation
   ↓
Softmax Normalization (with temperature)
   ↓
Cutoff Filtering (llm_tools_cutoff)
   ↓
Zero-Score Filtering (ignore_zero)
   ↓
Ranked Results (scores, rank, runtime metadata)
```

Tunable parameters:

```text
temperature        softmax temperature (0.1–1.5, default 0.5)
ignore_zero        filter zero-score results (default true)
llm_tools_cutoff   minimum softmax score percentage (default 10.0)
```

## Hybrid Search (optional)

Fuse BM25 lexical scores with ColBERT late-interaction semantic scores.

```text
User Query
   ↓
   ┌────────────┐    ┌────────────────┐
   │ BM25S      │    │ ColBERT        │
   │ (lexical)  │    │ (semantic)     │
   └─────┬──────┘    └───────┬────────┘
         │                   │
         └────────┬──────────┘
                  ↓
        Per-model softmax normalization
                  ↓
        Weighted blending (lexical weight / semantic weight)
                  ↓
        Fused ranked results
```

Install with `uv add "axiolex[colbert]"` and enable with `AXIOLEX_HYBRID_ENABLED=true`. ColBERT document embeddings are computed eagerly at index build time and kept in process memory. At query time only the query embedding is computed.

---

## 7. Redis Catalog and Index Lifecycle

Redis is a **hard requirement**. Axiolex is a shared service: multiple applications discover tools from a common catalog. The server fails fast at startup if Redis is unreachable or the catalog is empty.

## What Redis Contains

Redis stores three categories of data:

- **Discovery data** — searchable metadata per tool (title, description, params, category, provider)
- **Runtime data** — execution-ready JSON per tool (transport, endpoint, auth metadata, full parameter details)
- **Catalog version** — a version marker used by read-only consumers to detect full catalog refreshes

Redis does **not** contain the BM25 or ColBERT indexes. Those are derived from the catalog and live in the Python process serving queries.

## Index Lifecycle

```text
tools_list.yaml + mcp_providers.yaml
        │
        │  catalog refresh (CLI or API)
        ↓
Redis tool catalog  (atomic replacement + version bump)
        │
        ↓
AxioLex REST or MCP process
        │  builds BM25 in memory
        │  builds ColBERT in memory (when hybrid enabled)
        ↓
User query → ranked results
```

## Catalog Versioning

When tools are added, removed, or modified (via UI, API, or MCP discovery), the Redis catalog version is automatically bumped. All consumers detect the version change and reload their in-memory search index on the next request — no manual re-indexing or restart needed.

## TTL and Persistence

Per-entry Redis TTLs are environment-driven:

```bash
AXIOLEX_REDIS_DISCOVERY_TTL_SECONDS=3600
AXIOLEX_REDIS_RUNTIME_TTL_SECONDS=1800
```

Set either to `0` to keep keys until explicit refresh or invalidation. The full catalog refresh path writes the replacement catalog without per-key expirations. Redis persistence (AOF) is a deployment choice; Axiolex does not force it on or off.

---

## 8. MCP Provider Integration

Axiolex discovers tools from external MCP providers and merges them with static YAML tool definitions into one searchable catalog.

## Supported Transports

| Transport | Use case | Auth |
| --- | --- | --- |
| `streamable-http` | Remote MCP servers (Alpha Vantage, Tavily, etc.) | `api_key` (URL param), `bearer` (header), `none` |
| `stdio` | Local subprocess MCP servers (custom or pre-built via `uvx`/`npx`) | `none` |

## Provider Configuration

Providers are configured in `source_files/mcp_providers.yaml`:

```yaml
providers:
- id: alphavantage_finance
  name: Alpha Vantage MCP
  transport: streamable-http
  endpoint: https://mcp.alphavantage.co/mcp
  auth:
    type: api_key
    key_param: apikey
    secret_env: ALPHAVANTAGE_API_KEY
  enabled: true
  limits:
    max_results: 100
    max_requests_per_minute: 60
    timeout_seconds: 10
```

## Discovery Paths

- **Full catalog refresh**: The catalog refresh CLI loads YAML tools, discovers tools from every enabled provider, validates the merged set, atomically replaces Redis, and bumps the catalog version.
- **Single-provider discovery**: The per-provider discovery endpoint fetches tools from one provider and writes them to Redis. Useful for targeted discovery.

Adding or editing a provider through the UI or REST API updates the YAML config; it does not fetch tools by itself. Run a discovery path afterward.

## Stdio Servers

The `stdio_servers/` directory holds local MCP server implementations. Pre-built servers can be launched via `uvx` (Python) or `npx` (Node) with automatic dependency isolation, so they do not pollute the Axiolex venv.

---

## 9. Security

## Credential Handling

- API key **values** are never stored in provider YAML, source code, Redis, or the browser.
- `mcp_providers.yaml` stores only the environment variable name via `auth.secret_env`.
- Provider configuration models reject inline secret values, URLs containing credentials, and headers containing tokens.
- Secrets are resolved server-side at request time, checking the OS environment first, then the encrypted secret store.

## Encrypted Secret Store

- AES-256-GCM encryption. Secrets stored in `source_files/mcp_secrets.enc` (git-ignored, mode 0600).
- Master key from `AXIOLEX_SECRET_MASTER_KEY` env var.
- REST endpoints `POST/GET/DELETE /mcp-providers/{id}/secret` manage secrets. Secrets are never returned to the browser (only a masked `(encrypted)` indicator).

## Log Redaction

Outbound URLs are redacted before logging so `apikey`, `key`, `token`, and similar sensitive values appear as `REDACTED`.

## Transport-Specific Notes

- `http` transport: API key sent in `X-API-Key` header (or `Authorization: Bearer` for bearer auth).
- `streamable-http` with `api_key`: key appended as a URL query parameter (required by providers like Alpha Vantage). Residual log exposure risk exists; mitigated by URL redaction before logging.
- `streamable-http` with `bearer`: token sent in `Authorization` header, keeping it out of the URL.

---

## 10. REST API

```text
GET  /health

POST /retrieve                    Document/tool search
POST /index                       Build or rebuild BM25S index
GET  /settings  / POST /settings  BM25S settings
GET  /documents / POST /documents / DELETE /documents/{id}
POST /documents/reload            Reload documents from YAML
POST /documents/reindex-bm25s     Rebuild BM25S index
GET  /status                      Service health and document count

GET    /mcp-providers              List providers (with cached tool counts)
POST   /mcp-providers              Add provider
PUT    /mcp-providers/{id}         Update provider
DELETE /mcp-providers/{id}         Remove provider
GET    /mcp-providers/{id}/discover   Discover tools from one provider
POST   /mcp-providers/{id}/secret     Store encrypted secret
GET    /mcp-providers/{id}/secret     Check whether secret exists (never the value)
DELETE /mcp-providers/{id}/secret     Delete secret
```

Every UI action has a matching REST endpoint, enabling full automation via CI, scripts, or another agent.

---

## 11. MCP Discovery Server

Axiolex exposes its query-time tool selection as a Streamable HTTP MCP server.

```text
External LLM agent or client
        │
        │  MCP requests to http://axiolex-host:9700/mcp
        ↓
Axiolex MCP server (read-only Redis consumer)
        │
        ↓
Redis tool catalog
        ↑
Axiolex index CLI (admin: builds and refreshes the catalog)
```

The server advertises one MCP tool, `discover_tools`. Calling it returns the ranked downstream tools that the calling application can pass to its LLM and local tool executor.

The MCP server is deliberately read-only. It never discovers provider tools, loads YAML, or builds the cache. Build and refresh the Redis catalog through a separate administration process or CLI before starting the MCP server. Startup fails clearly if Redis is unavailable or the tool cache is empty.

The external client does **not** need Redis access, YAML files, or provider credentials.

The extension path is `call_tool`: accept the selected tool name and arguments, resolve the runtime record from the same catalog, enforce authentication and guardrails, execute the provider call, and record an audit trail.

---

## 12. Web UI

Keep the UI functional and lightweight.

## Demo Dashboard

- Test retrieval queries and inspect ranked results with scores
- Tune search parameters (temperature, cutoff, hybrid weights) in real time

## MCP Provider Management

- Add, edit, enable, disable, and remove providers
- Retrieve or delete cached tools per provider
- Live tool counts per provider
- API keys entered in masked fields with autocomplete disabled

## Document Management

- Add and inspect YAML-loaded tool definitions and documents

---

## 13. Deployment Patterns

## Pattern 1: Embedded Library

```text
Application
    ↓
Retrieval engine (in-process)
    ↓
Redis catalog
```

Install only the base package. Use the Python API to search the catalog. No FastAPI, no web UI.

## Pattern 2: Management Sidecar

```text
Application (uses axiolex library)     Admin UI (axiolex-server)
    ↓                                       ↓
    └──────────── Redis catalog ────────────┘
```

Run the FastAPI server separately for the admin UI and provider onboarding. The existing app stays unchanged and uses the same Redis catalog.

## Pattern 3: Standalone Platform

```text
make start  →  Redis + FastAPI server (:9700, REST + MCP at /mcp)
```

Run the full stack from a checkout. Redis is required; the server fails fast if Redis is down or the catalog is empty.

| Component | Default address | Purpose |
| --- | --- | --- |
| Axiolex REST service | `localhost:9700` | REST API and web UI |
| Axiolex MCP server | `localhost:9700/mcp` | MCP `discover_tools` endpoint |
| Redis (host) | `localhost:6380` | Shared tool catalog |

---

## 14. Extension Points

## Adding New MCP Providers

1. Add provider configuration to `mcp_providers.yaml` (or via the UI / REST API).
2. Implement a provider-specific adapter if the provider needs non-standard normalization.
3. Run a discovery path to fetch and cache tools.

## Adding New Retrieval Backends

1. Implement a new retriever alongside the existing lexical and hybrid engines.
2. Add configuration options for the new backend.
3. Wire it into the retrieval entry points so library, REST, and MCP paths all use it.

## Adding a `call_tool` Gateway

The shipped MCP server is read-only. A future `call_tool` gateway can sit beside `discover_tools`, use the same Redis runtime records, and own execution, authentication, guardrails, request logging, and observability.

---

## 15. Testing Strategy

## Retrieval Tests

Test:

```text
BM25S indexing
softmax normalization
cutoff and zero-score filtering
hybrid fusion (when ColBERT enabled)
stemming-aware tokenization
```

## Cache and Catalog Tests

Test:

```text
Redis discovery/runtime write and read
atomic catalog replacement
catalog version bump and reload detection
invalidation (tool, provider, all)
```

## MCP Discovery Tests

Test:

```text
provider config parsing
tool normalization
streamable-http and stdio transports
secret resolution and redaction
encrypted secret store round-trip
```

## API Tests

Test:

```text
retrieve endpoint
provider CRUD
single-provider discovery
secret management endpoints
settings update
```

## MCP Server Tests

Test:

```text
discover_tools returns ranked results
read-only behavior (no writes from MCP process)
startup failure on empty/unreachable Redis
```

---

## 16. Scope Boundary

For v1.0 implement:

```text
lexical retrieval (BM25S)
optional hybrid retrieval (ColBERT)
MCP provider discovery (streamable-http, stdio)
Redis-backed shared catalog with versioning
read-only MCP discovery server
encrypted secret store
REST API and web UI
```

Do not implement in v1.0:

```text
outbound tool execution (call_tool gateway)
LLM-based ranking or summarization
model training
PostgreSQL, Spark, Kafka, MLflow
vector databases
agent orchestration frameworks
```

The shipped `discover_tools` primitive returns execution-ready metadata. Execution, authentication, guardrails, and observability belong in the host application today, or in a future application-owned `call_tool` gateway that sits beside discovery and uses the same Redis runtime records.

---

## 17. Architectural Intent

Axiolex separates **selection** from **execution**.

```text
                    Tool / Document Catalog
                           │
          ┌────────────────┼─────────────────┐
          │                │                 │
          ▼                ▼                 ▼
       DISCOVER         RANK            RETURN METADATA

   MCP providers      BM25S / ColBERT   runtime + artifact
   YAML registries    softmax + cutoff   fields for gateway
```

The longer-term product direction is:

> **Discover the right tool or document for the current intent, return execution-ready metadata, and let a host gateway decide what happens next — keeping LLM context clean and execution concerns out of the retrieval layer.**
