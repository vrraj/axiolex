# AxioLex Architecture

## Overview

AxioLex is a multi-modal retrieval primitive for agentic infrastructure, currently powered by BM25S + PyStemmer for fast, deterministic lexical retrieval. It provides a routing layer for LLM tools, documents, and hybrid RAG systems.

The architecture is designed around three primary usage patterns:
1. **YAML-based static registries** - Pre-defined tool catalogs and document collections
2. **Runtime document/tool injection** - Dynamic addition of MCP-discovered tools and internal registries
3. **Remote service-oriented architecture** - Standalone HTTP service for multi-application environments

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Application Layer                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │   Python     │  │   REST API   │  │   MCP Server │           │
│  │   Library    │  │   Service    │  │   Endpoint   │           │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘           │
└─────────┼─────────────────┼─────────────────┼──────────────────┘
          │                 │                 │
          └─────────────────┼─────────────────┘
                            │
┌───────────────────────────┼─────────────────────────────────────┐
│                    Core Retrieval Layer                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              BM25SRetriever (axiolex/core/)               │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐                │   │
│  │  │ Config   │  │ Retriever│  │  Cache   │                │   │
│  │  │ Manager  │  │ Engine   │  │ Manager  │                │   │
│  │  └──────────┘  └──────────┘  └──────────┘                │   │
│  └──────────────────────────────────────────────────────────┘   │
└───────────────────────────┼─────────────────────────────────────┘
                            │
┌───────────────────────────┼─────────────────────────────────────┐
│                   Data Sources & Services                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ YAML Files   │  │ MCP Providers│  │   Redis      │           │
│  │ (tools_list) │  │  Discovery   │  │   Cache      │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

## Component Ownership and Index Lifecycle

AxioLex separates the durable tool catalog from the in-process retrieval indexes.
Redis stores tool metadata and runtime routing records. BM25 and ColBERT indexes
are derived from that catalog and live in the Python process that serves
queries.

```text
tools_list.yaml + mcp_providers.yaml
        |
        | axiolex-index refresh
        v
Redis tool catalog
        |  axiolex:idx:tool:{id}  searchable discovery fields
        |  axiolex:run:tool:{id}  runtime JSON for execution/routing
        |  axiolex:catalog:version
        v
AxioLex REST or MCP process
        |  builds BM25 in memory
        |  builds ColBERT in memory when hybrid search is enabled
        v
User query -> ranked tool/document results
```

### What Redis Contains

Redis is the shared catalog/control-plane store. It contains:

- `axiolex:idx:tool:{tool_id}`: title, description, tool name, params, category,
  provider, and source.
- `axiolex:run:tool:{tool_id}`: runtime JSON with transport, endpoint, provider,
  auth metadata, tool name, and full parameter details.
- `axiolex:catalog:version`: a version marker used by read-only cache consumers
  to detect full catalog refreshes.

Redis does **not** contain the BM25 index or the ColBERT index. The ColBERT
index includes token-level embedding matrices and is kept in process memory as
`ColBERTIndex.documents` plus `_doc_embeddings`.

### How Indexes Are Created

Lexical mode:

1. The process loads documents/tools from Redis or local YAML.
2. It builds a text corpus from title, content, and keywords.
3. BM25S tokenizes the corpus with PyStemmer and builds an in-memory BM25 index.
4. Queries tokenize the user request, score the BM25 index, softmax-normalize
   scores, then apply cutoff and zero-score filtering.

Hybrid mode:

1. Hybrid search must be enabled and the optional ColBERT dependencies installed.
2. During the same rebuild as BM25, AxioLex converts each document/tool into
   semantic text.
3. ColBERT document embeddings are computed eagerly and kept in memory.
4. At query time, AxioLex computes only the query embedding, scores it against
   the in-memory ColBERT document embeddings, and fuses those results with BM25.

### How Provider Changes Flow

There are two provider-refresh paths:

- Full catalog refresh: `axiolex-index refresh` or `make index-refresh` loads
  YAML tools, discovers tools from **every enabled MCP provider**, validates the
  merged set, atomically replaces Redis, and bumps `axiolex:catalog:version`.
  The read-only MCP server detects that version change on the next
  `discover_tools` call and rebuilds its in-memory BM25/ColBERT indexes.
- Single-provider discovery: the REST/UI endpoint
  `GET /mcp-providers/{provider_id}/discover` fetches tools only from that
  provider and writes those entries to Redis with the per-entry cache methods.
  This is useful for targeted discovery, but it is not the same as the full
  atomic indexer path and does not perform a catalog-wide provider fetch.

Adding a provider through the UI or `POST /mcp-providers` updates
`source_files/mcp_providers.yaml`; it does not fetch tools by itself. After
adding or editing a provider, run one of the discovery paths above, then rebuild
the running REST/UI retrieval indexes with `POST /documents/reindex-bm25s` when
that process needs to see the new entries immediately. For the read-only MCP
server, prefer the full catalog refresh path because it bumps the catalog
version used for automatic reload detection.

### TTL and Redis Persistence

Per-entry Redis TTLs are environment-driven:

```bash
AXIOLEX_REDIS_DISCOVERY_TTL_SECONDS=3600
AXIOLEX_REDIS_RUNTIME_TTL_SECONDS=1800
```

Set either value to `0` to keep those keys in Redis until an explicit refresh,
Redis eviction, or provider/tool invalidation. This is usually the preferred
mode when the available tools are stable and should not require periodic
rediscovery. The full `replace_all_tools()` catalog refresh path writes the
replacement catalog without per-key expirations.

Redis persistence is a deployment choice. The default local `make redis-start`
container starts `redis:7` without AOF. AOF can be enabled when you run Redis,
for example with `redis-server --appendonly yes`, or by using a managed Redis
configuration that provides the durability policy you want. AxioLex does not
force AOF on or off.

## Module Structure

### Core Layer (`axiolex/core/`)

The core layer contains the fundamental retrieval and configuration logic.

#### `config.py`
- **Purpose**: Configuration management for the entire system
- **Key Classes**:
  - `BM25SSettings`: BM25S retrieval parameters (temperature, ignore_zero, llm_tools_cutoff)
  - `DocumentConfig`: Document source configuration
  - `MCPConfig`: MCP provider configuration
  - `ServerConfig`: FastAPI server configuration
  - `Config`: Complete configuration container
- **Functions**:
  - `load_config()`: Load from YAML file or environment variables
  - `save_config()`: Persist configuration to YAML

#### `retriever.py`
- **Purpose**: BM25S-based document retrieval engine
- **Key Classes**:
  - `Document`: Document representation with id, title, content, keywords, metadata, runtime, artifact, params
  - `BM25SRetriever`: Main retrieval engine with BM25S indexing and softmax scoring
- **Key Methods**:
  - `retrieve_documents()`: Search with BM25S scoring, softmax normalization, and cutoff filtering
  - `add_documents()`: Dynamically add documents to index
  - `rebuild_index()`: Rebuild BM25S index from documents
  - `refresh_local_yaml_cache()`: Sync YAML documents to Redis
  - `reload_cache_if_changed()`: Reload in-memory index when Redis catalog version changes
- **Global Functions**:
  - `get_retriever()`: Get global retriever instance
  - `get_tool_discovery_retriever()`: Get read-only Redis cache consumer
  - `retrieve_documents()`: Convenience function for one-off retrieval

#### `cache.py`
- **Purpose**: Redis cache manager for tool discovery and runtime execution
- **Key Classes**:
  - `RedisConfig`: Redis connection configuration
  - `ToolCacheManager`: Redis operations for discovery and runtime data
- **Cache Structure**:
  - Discovery keys: `axiolex:idx:tool:{tool_id}` - Searchable metadata
  - Runtime keys: `axiolex:run:tool:{tool_id}` - Execution specifications
  - Catalog version: `axiolex:catalog:version` - Version tracking for cache reloads
- **Key Methods**:
  - `cache_discovery()` / `get_discovery()`: Individual tool discovery data
  - `cache_runtime()` / `get_runtime()`: Individual tool runtime data
  - `cache_all_discovery()` / `cache_all_runtime()`: Batch operations
  - `replace_all_tools()`: Atomic catalog replacement with version bump
  - `get_catalog_version()`: Retrieve current catalog version
  - `invalidate_tool()` / `invalidate_provider()` / `invalidate_all()`: Cache invalidation

### API Layer (`axiolex/api/`)

The API layer provides REST endpoints for remote access and a Python HTTP client.

#### `routes.py`
- **Purpose**: FastAPI route definitions for the REST service
- **Key Endpoints**:
  - `POST /retrieve`: Document search with configurable parameters
  - `POST /index`: Build or rebuild BM25S index
  - `GET /settings` / `POST /settings`: Retrieve and update BM25S settings
  - `GET /documents` / `POST /documents` / `DELETE /documents/{id}`: Document management
  - `POST /documents/reload`: Reload documents from YAML
  - `POST /documents/reindex-bm25s`: Rebuild BM25S index
  - `GET /status`: Service health and document count
  - `POST /reload`: Reload retriever instance
  - `GET /document-files` / `POST /switch-document-file`: Document file management
  - MCP provider endpoints: `/mcp-providers` (GET, POST, PUT, DELETE), `/mcp-providers/{id}/discover`

#### `client.py`
- **Purpose**: Python HTTP client for remote AxioLex service
- **Key Class**: `BM25SClient`
- **Key Methods**:
  - `retrieve()`: Search documents remotely
  - `add_document()`: Add document remotely
  - `get_documents()`: List all documents
  - `delete_document()`: Delete document by ID
  - `get_settings()` / `update_settings()`: Remote settings management

#### `models.py`
- **Purpose**: Pydantic models for API request/response validation
- **Key Models**:
  - `Document`: Document data model
  - `RetrieveRequest` / `RetrieveResponse`: Search request/response
  - `IndexRequest` / `IndexResponse`: Index building request/response
  - `SettingsResponse`: Settings response
  - `RetrievedDocument`: Retrieved document with scores
  - `BM25SSettings`: BM25S settings model

### MCP Integration (`axiolex/mcp/`)

The MCP layer handles Model Context Protocol tool discovery and server functionality.

#### `discovery.py`
- **Purpose**: MCP tool discovery from multiple providers
- **Key Classes**:
  - `MCPProvider`: Provider identifier enum
  - `MCPProviderAuth`: Authentication configuration (bearer, api_key, none)
  - `MCPLimits`: Rate limiting and performance limits
  - `MCPProviderFeatures`: Feature flags (streaming support)
  - `MCPProviderConfig`: Complete provider configuration
  - `MCPDiscovery`: Multi-provider tool discovery engine
- **Key Methods**:
  - `load_from_yaml()` / `save_to_yaml()`: Provider configuration persistence
  - `discover_all()`: Discover tools from all enabled providers
  - `discover_from_config()`: Discover tools from specific provider
  - `_discover_http()`: HTTP JSON-RPC discovery
  - `_discover_streamable_http()`: Streamable HTTP transport discovery
  - `_normalize_tool()` / `_normalize_tool_from_mcp()`: Tool format normalization
  - `get_tool_schema()`: Retrieve detailed tool schema

#### `alphavantage_adapter.py`
- **Purpose**: Alpha Vantage-specific MCP adapter
- **Key Class**: `AlphaVantageAdapter`
- **Key Methods**:
  - `discover_tools()`: Discover Alpha Vantage financial tools
  - Provider-specific tool normalization and schema extraction

#### `server.py`
- **Purpose**: AxioLex MCP server implementation
- **Key Functionality**:
  - Exposes `discover_tools` as a single MCP tool
  - Returns ranked downstream tools for LLM context assembly
  - Read-only Redis cache consumer
  - Automatic cache reload on catalog version change

#### `client.py`
- **Purpose**: MCP client for connecting to AxioLex MCP server
- **Key Functionality**:
  - Streamable HTTP transport support
  - Tool discovery and execution

#### `merger.py`
- **Purpose**: Tool merger for combining tools from multiple sources
- **Key Functionality**:
  - Deduplication
  - Conflict resolution
  - Schema merging

### Services Layer (`axiolex/services/`)

The services layer contains business logic for specific domains.

#### `indexing_service.py`
- **Purpose**: Build and maintain the Redis tool catalog
- **Key Classes**:
  - `IndexingResult`: Summary of catalog refresh (yaml_tools, mcp_tools, provider_count, total_tools)
  - `ToolIndexingService`: Catalog management with write access
- **Key Methods**:
  - `refresh()`: Build and atomically replace complete Redis catalog
  - `status()`: Return catalog status without modification
  - `_load_yaml_tools()`: Load tools from YAML file
  - `_discover_mcp_tools()`: Discover tools from enabled MCP providers
  - `_deduplicate()`: Remove duplicate tools by ID
  - `_validate_tools()`: Ensure tools have required runtime metadata
- **Usage**: Called by `axiolex-index` CLI for catalog refresh

#### `mcp_service.py`
- **Purpose**: MCP provider management for REST API
- **Key Functions**:
  - `get_all_providers()`: List all configured providers
  - `add_provider()`: Add new provider configuration
  - `update_provider()`: Update existing provider
  - `disable_provider()`: Disable provider and clear cached tools
  - `discover_provider_tools()`: Discover tools from specific provider and cache to Redis

#### `tool_discovery_service.py`
- **Purpose**: High-level tool discovery interface
- **Key Classes**:
  - `ToolDiscoveryService`: Tool discovery with BM25S filtering
- **Key Methods**:
  - `discover_tools()`: Discover and rank tools by query
- **Global Function**:
  - `discover_tools()`: Convenience function for tool discovery

#### `settings_service.py`
- **Purpose**: BM25S settings management for REST API
- **Key Functions**:
  - `get_settings()`: Retrieve current settings
  - `update_settings()`: Update BM25S parameters

#### `document_service.py`
- **Purpose**: Document management for REST API
- **Key Functions**:
  - `switch_document_file()`: Switch between different YAML document files

### Database Layer (`axiolex/db/`)

#### `document_service.py`
- **Purpose**: Document database operations
- **Key Functions**:
  - `get_documents_from_cache()`: Retrieve all documents from Redis cache

### UI Layer (`axiolex/ui/`)

#### `templates/`
- **Purpose**: Jinja2 templates for web UI
- **Key Template**: `tool-router.html` - Main interactive UI for testing retrieval

#### `static/`
- **Purpose**: Static assets (CSS, JavaScript) for web UI

### Utilities (`axiolex/utils/`)

#### `file_utils.py`
- **Purpose**: File operation utilities
- **Key Functions**:
  - `is_source_entry_enabled()`: Check if document/tool entry is enabled
  - `get_available_document_files()`: List available YAML document files

### CLI Entry Points

#### `cli.py`
- **Purpose**: Main CLI entry point for AxioLex
- **Key Commands**:
  - Server startup and management

#### `index_cli.py`
- **Purpose**: Index management CLI for Redis catalog
- **Key Commands**:
  - `axiolex-index refresh`: Build/refresh Redis catalog from YAML and MCP providers
  - `axiolex-index status`: Inspect current Redis catalog status

## Data Flow

### Document Ingestion Flow

```
YAML File / MCP Discovery
    ↓
Document Objects (id, title, content, keywords, metadata, runtime, artifact, params)
    ↓
BM25SRetriever.add_documents()
    ↓
Redis Cache (optional)
    ├─ Discovery Index: axiolex:idx:tool:{id}
    └─ Runtime Data: axiolex:run:tool:{id}
    ↓
BM25S Index Building
    ├─ Tokenization with PyStemmer
    ├─ Corpus construction (title + content + keywords)
    └─ BM25S indexing
    ↓
In-Memory BM25S Index
```

### Retrieval Flow

```
User Query
    ↓
BM25SRetriever.retrieve_documents()
    ↓
Query Tokenization (BM25S + PyStemmer)
    ↓
BM25S Score Calculation
    ↓
Softmax Normalization (with temperature)
    ↓
Cutoff Filtering (llm_tools_cutoff)
    ↓
Zero-Score Filtering (ignore_zero)
    ↓
Ranked Results with:
    ├─ bm25_score
    ├─ softmax_score
    ├─ score_percentage
    ├─ rank
    └─ metadata (for client routing)
```

### MCP Tool Discovery Flow

```
MCP Providers Configuration (YAML)
    ↓
MCPDiscovery.discover_all()
    ↓
For Each Enabled Provider:
    ├─ HTTP JSON-RPC or Streamable HTTP
    ├─ Tool List Retrieval
    ├─ Tool Normalization
    └─ Runtime Metadata Attachment
    ↓
ToolIndexingService.refresh()
    ├─ Load YAML Tools
    ├─ Discover MCP Tools
    ├─ Deduplicate by ID
    ├─ Validate Runtime Metadata
    └─ Atomic Redis Replacement
    ↓
Catalog Version Bump
    ↓
MCP Server Reload Detection
    ↓
In-Memory Index Refresh
```

## Configuration Architecture

### Configuration Hierarchy

1. **Default values** (in code)
2. **YAML configuration file** (`settings.yaml`)
3. **Environment variables** (override YAML)

### Key Configuration Sections

#### BM25S Settings
- `temperature`: Softmax temperature (0.1-1.5, default 0.5)
- `ignore_zero`: Filter zero-score results (default true)
- `llm_tools_cutoff`: Minimum softmax score percentage (default 10.0)

#### Document Settings
- `source`: Path to YAML document file
- `auto_reload`: Auto-reload on file changes
- `encoding`: File encoding (default utf-8)

#### MCP Settings
- `providers_file`: Path to MCP providers YAML
- `auto_discover`: Auto-discover tools on startup
- `cache_ttl`: Cache time-to-live in seconds

#### Server Settings
- `host`: Server bind address (default 0.0.0.0)
- `port`: Server port (default 8000)
- `reload`: Auto-reload on code changes
- `log_level`: Logging level

## Deployment Patterns

### Pattern 1: In-Process Library
```
Application
    ↓
BM25SRetriever (in-process)
    ↓
YAML Files
```

### Pattern 2: Remote Service
```
Application
    ↓
BM25SClient (HTTP)
    ↓
AxioLex REST Service
    ↓
BM25SRetriever + Redis
```

### Pattern 3: MCP Discovery Server
```
External LLM Agent
    ↓
MCP Client (streamable-http)
    ↓
Axiolex MCP Server (port 9701)
    ↓
BM25SRetriever (read-only Redis consumer)
    ↓
Redis Tool Catalog
    ↑
Axiolex Index CLI (admin)
    ↓
YAML + MCP Providers
```

## Key Design Decisions

### 1. Separation of Discovery and Runtime Data
- **Discovery data**: Searchable metadata (title, description, category) for BM25S indexing
- **Runtime data**: Execution specifications (transport, endpoint, auth) for tool execution
- **Benefit**: Enables read-only MCP server while keeping admin write access separate

### 2. Atomic Catalog Replacement
- **Implementation**: Redis transaction with version key
- **Benefit**: Prevents partial catalog states during refresh

### 3. Cache Version Tracking
- **Implementation**: UUID-based catalog version key
- **Benefit**: Enables automatic index reload without server restart

### 4. Softmax Scoring with Temperature
- **Implementation**: Temperature-scaled softmax over BM25S scores
- **Benefit**: Tunable retrieval selectivity

### 5. Stemming-Aware Tokenization
- **Implementation**: PyStemmer with BM25S tokenization
- **Benefit**: Improved lexical recall across word forms

### 6. Enabled/Disabled Entry Filtering
- **Implementation**: `enabled` flag in metadata with runtime filtering
- **Benefit**: Easy tool/document toggling without file deletion

## Extension Points

### Adding New MCP Providers
1. Add provider configuration to `mcp_providers.yaml`
2. Implement provider-specific adapter (if needed) in `axiolex/mcp/`
3. Add normalization logic in `MCPDiscovery._normalize_tool()`

### Adding New Retrieval Backends
1. Implement new retriever class in `axiolex/core/`
2. Add configuration options in `axiolex/core/config.py`
3. Update `BM25SRetriever` or create parallel retriever

### Adding New Cache Backends
1. Implement cache manager interface in `axiolex/core/cache.py`
2. Add configuration options
3. Update `ToolCacheManager` or create parallel implementation

## Performance Considerations

### Indexing Performance
- Small collections (<100 docs): sub-second
- Medium collections (100-1,000 docs): 1-3 seconds
- Large collections (1,000+ docs): 3-10 seconds

### Search Performance
- In-memory BM25S: typically <100ms
- Redis cache lookup: <10ms per tool
- Softmax calculation: O(n) where n = number of results

### Memory Usage
- BM25S index: O(corpus_size)
- Document storage: O(document_count * avg_document_size)
- Redis cache: Configurable via TTL

## Troubleshooting

### Verify Redis TTL Settings

Use this check when cached tools should remain in Redis without expiring. A TTL
result of `-1` means the key exists and has no expiration.

```bash
make redis-start

AXIOLEX_REDIS_DISCOVERY_TTL_SECONDS=0 \
AXIOLEX_REDIS_RUNTIME_TTL_SECONDS=0 \
venv/bin/python -c "from axiolex.core.cache import RedisConfig, ToolCacheManager; m=ToolCacheManager(RedisConfig.from_env()); m.cache_discovery('ttl-test', {'title':'TTL Test'}); m.cache_runtime('ttl-test', {'tool_name':'ttl_test'}); print('done')"

docker exec axiolex-redis redis-cli TTL axiolex:idx:tool:ttl-test
docker exec axiolex-redis redis-cli TTL axiolex:run:tool:ttl-test
```

## Security Considerations

### Redis Security
- Redis should not be publicly exposed
- Use password authentication in production
- Network isolation between Axiolex and external clients

### MCP Provider Security
- API key values are stored only in the process environment (e.g. `.env` or exported shell variables), never in provider YAML or source code.
- `source_files/mcp_providers.yaml` only references the environment variable name via `auth.secret_env` (e.g. `ALPHAVANTAGE_API_KEY`).
- `MCPProviderConfig` and `MCPProviderAuth` reject inline `secret_value`, URLs containing credentials, and headers containing tokens.
- The actual key is resolved server-side by `resolve_secret()` in `axiolex/mcp/security.py` and used only in outbound provider requests. For the `http` transport it is sent in the `X-API-Key` header (or `Authorization: Bearer` for bearer auth). For the `streamable-http` transport, `api_key` auth appends an `?apikey=` query parameter over HTTPS (required by providers like Alpha Vantage), while `bearer` auth sends the token in the `Authorization` header via a custom `httpx.AsyncClient`, keeping it out of the URL. Note that URL query parameters can still be recorded in server or proxy access logs, which is why `redact_url()` is applied before any URL is logged.
- The REST endpoints (`/mcp-providers`, `/mcp-providers/{id}/discover`) and the Redis runtime cache expose only `auth.type` and `auth.secret_env`, never the key value.
- Outbound URLs are redacted before logging via `redact_url()` so `apikey`, `key`, `token`, and similar sensitive values appear as `REDACTED`.

### API Security
- Consider adding authentication for REST service
- Rate limiting for public endpoints
- Input validation via Pydantic models
