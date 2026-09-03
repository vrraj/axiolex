# API Reference

Reference for programmatic usage of Axiolex through the Python SDK, REST API, and MCP interface.

> **New here?** Start with the project overview: **[Axiolex docs home](https://vrraj.github.io/axiolex/)**.

---

## Integration Surfaces

Axiolex exposes three integration surfaces. All hit the same backend — same Redis catalog, same retrieval engine, same execution dispatcher.

| Surface | Best for | Package |
|---|---|---|
| **Python SDK** | Python applications | `pip install axiolex` (httpx + pydantic only) |
| **REST API** | Non-Python applications, curl, any HTTP client | Axiolex server on port 9700 |
| **MCP server** | AI clients (Claude Desktop, Cursor, custom LLM agents) | Axiolex MCP server on port 9701 |

### Operation mapping

| Capability | Python SDK | REST endpoint | MCP tool |
|---|---|---|---|
| Health check | `client.health()` | `GET /status` | — |
| List namespaces | `client.list_namespaces()` | `GET /capabilities` | `list_namespaces()` |
| Discover tools | `client.discover(...)` | `POST /discover` | `axiolex_discover_tools(...)` |
| Execute tool | `client.execute(...)` | `POST /execute` | `axiolex_execute_tool(...)` |
| Retrieve documents | `client.retrieve(...)` | `POST /retrieve` | — |

---

## Quick Start

### Python SDK

```python
from axiolex import Axiolex

client = Axiolex("http://localhost:9700")

# Discover tools
tools = client.discover("get stock earnings", top_k=5, namespaces=["finance"])

# Execute the top-ranked tool
result = client.execute(tools["tools"][0]["tool_id"], {"symbol": "AAPL"})

# List available namespaces
namespaces = client.list_namespaces()
```

### REST API

```bash
# Discover tools
curl -X POST http://localhost:9700/discover \
  -H "Content-Type: application/json" \
  -d '{"query": "get stock earnings", "top_k": 5, "namespaces": ["finance"]}'

# Execute a tool
curl -X POST http://localhost:9700/execute \
  -H "Content-Type: application/json" \
  -d '{"tool_id": "aina_markets:get_earnings_calendar", "arguments": {"symbol": "AAPL"}}'

# List namespaces
curl http://localhost:9700/capabilities
```

### MCP server

```json
// Claude Desktop config
"axiolex": { "url": "http://localhost:9701/mcp" }
```

The AI client sees `axiolex_discover_tools`, `axiolex_execute_tool`, and `list_namespaces` as callable tools.

---

## Python SDK Reference

### `Axiolex` class

```python
from axiolex import Axiolex

client = Axiolex(base_url="http://localhost:9700", timeout=30.0)
```

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `base_url` | `str` | `http://localhost:9700` | Axiolex server URL |
| `timeout` | `float` | `30.0` | Request timeout in seconds |

The SDK is a thin HTTP client — only requires `httpx` and `pydantic`. No Redis, ColBERT, or server-side dependencies.

### `discover()`

Discover tools relevant to a natural-language query.

```python
client.discover(
    query: str,
    top_k: Optional[int] = None,
    hybrid_search: Optional[bool] = None,
    temperature: Optional[float] = None,
    min_hybrid_score: Optional[float] = None,
    bm25_weight: Optional[float] = None,
    colbert_weight: Optional[float] = None,
    candidate_limit: Optional[int] = None,
    namespaces: Optional[List[str]] = None,
    max_tools: Optional[int] = None,  # deprecated alias for top_k
) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | `str` | required | Natural-language request |
| `top_k` | `int` | deployment default | Maximum number of tools to return |
| `hybrid_search` | `bool` | `None` (deployment default) | `True` = force hybrid, `False` = force lexical, `None` = deployment default |
| `temperature` | `float` | from settings | Softmax temperature for score fusion |
| `min_hybrid_score` | `float` | `0.0` | Minimum fused hybrid score |
| `bm25_weight` | `float` | `0.4` | BM25 blend weight (hybrid mode) |
| `colbert_weight` | `float` | `0.6` | ColBERT blend weight (hybrid mode) |
| `candidate_limit` | `int` | `100` | Per-model candidate count before fusion |
| `namespaces` | `List[str]` | `None` (all) | Restrict discovery to these namespaces |

**Returns:**

```python
{
    "query": str,
    "tools": List[Dict],
    "count": int,
    "search_mode": str,  # "lexical" or "hybrid"
}
```

Each tool in the `tools` list contains:

| Field | Type | Description |
|---|---|---|
| `tool_id` | `str` | Stable identifier (`{provider_id}:{tool_name}`) |
| `name` | `str` | Tool name |
| `description` | `str` | Tool description |
| `rank` | `int` | Rank position (1-based) |
| `relevance_score` | `float` | Normalized score (0.0-1.0) |
| `params` | `Dict` | Input schema |
| `inputSchema` | `Dict` | JSON Schema for tool arguments |
| `endpoint` | `str` or `Dict` | Provider endpoint |
| `transport` | `str` | `streamable-http`, `stdio`, or `a2a` |
| `provider` | `str` | Provider ID |
| `namespaces` | `List[str]` | Namespaces this tool belongs to |
| `bm25_score` | `float` | Raw BM25 score (lexical mode) |
| `softmax_score` | `float` | Softmax probability (lexical mode) |
| `colbert_score` | `float` | ColBERT score (hybrid mode) |
| `hybrid_score` | `float` | Fused hybrid score (hybrid mode) |

**Example:**

```python
result = client.discover("stock earnings calendar", top_k=3, namespaces=["finance"])

for tool in result["tools"]:
    print(f"#{tool['rank']} {tool['name']} (score={tool['relevance_score']:.3f})")
    print(f"  tool_id: {tool['tool_id']}")
    print(f"  transport: {tool['transport']}")
```

### `execute()`

Execute a discovered tool by `tool_id`.

```python
client.execute(
    tool_id: str,
    arguments: Dict[str, Any],
    idempotency_key: Optional[str] = None,
    timeout_ms: Optional[int] = None,
) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `tool_id` | `str` | required | Stable identifier from `discover()` |
| `arguments` | `Dict` | required | Arguments matching the tool's input schema |
| `idempotency_key` | `str` | `None` | Optional de-duplication key (logged, not enforced in Phase 1) |
| `timeout_ms` | `int` | `None` | Optional execution timeout in milliseconds |

**Returns (success):**

```python
{
    "status": "success",
    "tool_id": str,
    "execution_id": str,
    "result": Dict,
}
```

**Returns (error):**

```python
{
    "status": "error",
    "tool_id": str,
    "execution_id": str,
    "error": {
        "code": str,       # TOOL_NOT_FOUND, TOOL_UNAVAILABLE, INVALID_ARGUMENTS, UPSTREAM_TIMEOUT, UPSTREAM_ERROR, RATE_LIMITED, INTERNAL_ERROR
        "message": str,
        "retryable": bool,
    }
}
```

**Example:**

```python
result = client.execute("aina_markets:get_earnings_calendar", {"symbol": "AAPL"})

if result["status"] == "success":
    print(result["result"])
else:
    print(f"Error: {result['error']['code']} - {result['error']['message']}")
```

### `list_namespaces()`

Return the enterprise capability map — enabled namespaces with id, name, and description.

```python
client.list_namespaces() -> List[Dict[str, Any]]
```

**Returns:**

```python
[
    {"id": "finance.market_data", "name": "Market Data", "description": "..."},
    {"id": "finance.trading", "name": "Trading", "description": "..."},
]
```

### `retrieve()`

Retrieve ranked documents (lower-level than `discover()` — returns raw documents, not execution-ready tools).

```python
client.retrieve(
    query: str,
    top_k: Optional[int] = None,
    hybrid_search: Optional[bool] = None,
    temperature: Optional[float] = None,
    ignore_zero: Optional[bool] = None,
    llm_tools_cutoff: Optional[float] = None,
    bm25_weight: Optional[float] = None,
    colbert_weight: Optional[float] = None,
    candidate_limit: Optional[int] = None,
    min_hybrid_score: Optional[float] = None,
    namespaces: Optional[List[str]] = None,
    max_results: Optional[int] = None,  # deprecated alias for top_k
) -> Dict[str, Any]
```

**Returns:**

```python
{
    "success": bool,
    "message": str,
    "documents": List[Dict],
    "total_retrieved": int,
    "cutoff_percentage": float,
    "settings": Dict,
    "search_mode": str,
}
```

### `health()`

Check server health and retrieval status.

```python
client.health() -> Dict[str, Any]
```

**Returns:**

```python
{
    "status": "healthy",
    "document_count": int,
    "retriever_initialized": bool,
    "version": str,
    "hybrid_search": {
        "enabled": bool,
        "model": str,
        "available": bool,
        "index_ready": bool,
        "error": Optional[str],
    },
    "default_top_k": int,
}
```

### Error handling

The SDK raises `AxiolexError` on any non-2xx response from the server. The exception includes the server's error message and HTTP status code.

```python
from axiolex import Axiolex, AxiolexError

client = Axiolex("http://localhost:9700")

try:
    result = client.discover("test query", namespaces=["bad_namespace"])
except AxiolexError as e:
    print(f"Error: {e.message}")        # "Unknown namespace(s): bad_namespace"
    print(f"Status code: {e.status_code}")  # 400
```

`AxiolexError` attributes:

| Attribute | Type | Description |
|---|---|---|
| `message` | `str` | Human-readable error detail from the server |
| `status_code` | `int` | HTTP status code (400, 422, 500, etc.) |

Common error scenarios:

| Scenario | Status code | Example message |
|---|---|---|
| Unknown namespace | 400 | `Unknown namespace(s): bad_ns` |
| Invalid parameter value | 422 | `body > top_k: Input should be greater than or equal to 1` |
| Tool not found | 400 | `TOOL_NOT_FOUND: Tool 'bad:tool' not found in the current catalog` |
| Server error | 500 | `Internal server error` |

### Context manager

The SDK supports use as a context manager to ensure the HTTP client is properly closed:

```python
with Axiolex("http://localhost:9700") as client:
    tools = client.discover("stock earnings")
    result = client.execute(tools["tools"][0]["tool_id"], {"symbol": "AAPL"})
```

---

## REST API Reference

### Base URL

```
http://localhost:9700
```

### POST /discover

Discover execution-ready tools for a natural-language query.

**Request body:**

```json
{
    "query": "stock earnings calendar",
    "top_k": 5,
    "namespaces": ["finance"],
    "hybrid_search": null,
    "temperature": null,
    "bm25_weight": null,
    "colbert_weight": null,
    "candidate_limit": null,
    "min_hybrid_score": null
}
```

Only `query` is required. All other fields are optional.

**Response (200):**

```json
{
    "query": "stock earnings calendar",
    "tools": [...],
    "count": 3,
    "search_mode": "hybrid"
}
```

**Error responses:**

| Status | Body | Cause |
|---|---|---|
| 400 | `{"detail": "Unknown namespace(s): bad_ns"}` | Invalid namespace |
| 422 | `{"detail": [{...validation errors...}]}` | Invalid parameter values |
| 500 | `{"detail": "..."}` | Server error |

### POST /execute

Execute a tool by `tool_id`.

**Request body:**

```json
{
    "tool_id": "aina_markets:get_earnings_calendar",
    "arguments": {"symbol": "AAPL"},
    "idempotency_key": null,
    "timeout_ms": null
}
```

**Response (200):**

```json
{
    "status": "success",
    "tool_id": "aina_markets:get_earnings_calendar",
    "execution_id": "abc123...",
    "result": {...}
}
```

### GET /capabilities

List enabled namespaces (consumer-facing capability map).

**Response (200):**

```json
[
    {"id": "finance.market_data", "name": "Market Data", "description": "..."},
    {"id": "finance.trading", "name": "Trading", "description": "..."}
]
```

### GET /namespaces

List all registered namespaces (management endpoint — includes disabled).

### POST /retrieve

Retrieve ranked documents (lower-level than `/discover`).

**Request body:** Same as `/discover` plus `ignore_zero` and `llm_tools_cutoff`.

### GET /status

Server health and retrieval status.

**Response (200):**

```json
{
    "status": "healthy",
    "document_count": 62,
    "retriever_initialized": true,
    "version": "1.0.11",
    "hybrid_search": {
        "enabled": true,
        "model": "colbert-ir/colbertv2.0",
        "available": true,
        "index_ready": true,
        "error": null
    },
    "default_top_k": 7
}
```

### Management endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/mcp-providers` | List providers (MCP and A2A) |
| `POST` | `/mcp-providers` | Add a provider |
| `PUT` | `/mcp-providers/{id}` | Update a provider |
| `DELETE` | `/mcp-providers/{id}` | Remove a provider |
| `GET` | `/mcp-providers/{id}/discover` | Discover tools from a provider |
| `DELETE` | `/mcp-providers/{id}/tools` | Delete cached tools for a provider |
| `POST` | `/mcp-providers/{id}/secret` | Store an encrypted provider secret |
| `GET` | `/mcp-providers/{id}/secret` | Check whether a secret exists |
| `DELETE` | `/mcp-providers/{id}/secret` | Delete a provider secret |
| `POST` | `/namespaces` | Add a namespace |
| `PUT` | `/namespaces/{id}` | Update a namespace |
| `DELETE` | `/namespaces/{id}` | Delete a namespace |
| `POST` | `/index` | Build or rebuild the index |
| `GET` | `/settings` | Get current settings |
| `POST` | `/settings` | Update settings |
| `POST` | `/reload` | Reload catalog from Redis |

---

## MCP Interface Reference

The MCP server (port 9701) exposes three tools to AI clients:

### `axiolex_discover_tools(query, top_k?, hybrid_search?, namespaces?, ...)`

Find tools relevant to a natural-language request. Returns `tool_id`, name, parameter schema, endpoint, and transport.

**Key parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `query` | `str` | yes | Natural-language request |
| `top_k` | `int` | no | Maximum tools to return |
| `namespaces` | `List[str]` | no | Restrict to these namespaces |
| `hybrid_search` | `bool` | no | Force hybrid or lexical mode |

**Returns:** `DiscoverToolsResult` with `query`, `tools`, `count`, `search_mode`.

### `axiolex_execute_tool(tool_id, arguments, idempotency_key?, timeout_ms?)`

Execute a tool by `tool_id`. The dispatcher resolves the provider, validates arguments, and dispatches over the tool's transport.

**Returns:** `ExecuteToolResult` with `status`, `tool_id`, `execution_id`, `result` (on success) or `error` (on failure).

### `list_namespaces()`

List enabled namespaces with id, name, and description. Call this first to discover available capability areas.

**Returns:** `ListNamespacesResult` with `namespaces` list and `count`.

---

## A2A (Agent-to-Agent) Providers

Axiolex supports A2A agents alongside MCP providers. A2A agents expose their capabilities as **skills** via an agent card, and Axiolex maps each skill to a tool in the catalog. The caller never needs to know whether a tool is backed by MCP or A2A — both are discovered, ranked, and executed through the same `axiolex_execute_tool(tool_id, arguments)` contract.

### How A2A differs from MCP

| Aspect | MCP (streamable-http, stdio) | A2A |
|---|---|---|
| Discovery | `tools/list` over MCP session | GET `{endpoint}/.well-known/agent-card.json` |
| Tool unit | MCP tool with `inputSchema` | A2A skill with `id`, `name`, `description` |
| Execution | `tools/call` with `name` + `arguments` | `SendMessage` with `message.parts[].text` |
| Required header | `Mcp-Session-Id` | `A2A-Version: 1.0` |
| Session | Stateful (initialize handshake) | Stateless (no handshake) |
| Response | `CallToolResult` with `content[]` | `Task` with `artifacts[].parts[].text` |
| Arguments | Structured key-value matching `inputSchema` | Natural-language `prompt` sent as text part |

### Provider configuration

```yaml
providers:
  - id: veris_finance_a2a
    name: Veris Finance Research (A2A)
    transport: a2a
    endpoint: http://localhost:8100/agents/veris-finance-research-agent/
    auth:
      type: none
    enabled: true
    namespaces:
      - veris.research
```

### Discovery

Axiolex fetches the agent card at `{endpoint}/.well-known/agent-card.json` and maps each skill to a tool:

```text
agent card skill                     →  Axiolex catalog tool
────────────────────────────────────     ─────────────────────────────────────
id: "financial_research"               →  tool_id: veris_finance_a2a:financial_research
name: "Financial Research"             →  title: "Financial Research"
description: "Synthesizes sourced..."   →  description: "Synthesizes sourced..."
                                       →  params: {prompt: {type: string}}
                                       →  transport: a2a
```

### Execution

When `execute()` is called on an A2A tool, the A2A adapter sends a `SendMessage` JSON-RPC request:

```python
from axiolex import Axiolex

client = Axiolex("http://localhost:9700")

# Discover A2A agent skills
tools = client.discover("financial research on Nvidia", namespaces=["veris.research"])

# Execute — the A2A adapter sends SendMessage to the agent
result = client.execute(
    "veris_finance_a2a:financial_research",
    {"prompt": "What was Nvidia revenue in 2024?"}
)

# Result contains the agent's response in content[]
for item in result["result"]["content"]:
    print(item["text"])
```

If the tool's schema has a single `prompt` field, its value is sent as a text part. Otherwise, the arguments dict is JSON-encoded as a text part.

### A2A auth

A2A providers support the same auth options as MCP:

| Auth type | How it works |
|---|---|
| `none` | No authentication |
| `bearer` | Token sent in `Authorization: Bearer` header |
| `api_key` | Key appended as query parameter (`?api_key=...`) |

---

## Execution Error Codes

| Code | Meaning | Retryable |
|---|---|---|
| `TOOL_NOT_FOUND` | `tool_id` not in the current catalog | No |
| `TOOL_UNAVAILABLE` | Tool exists but transport is not supported | No |
| `INVALID_ARGUMENTS` | Arguments don't match the tool's schema | No |
| `UPSTREAM_TIMEOUT` | Provider did not respond within the timeout | Yes |
| `UPSTREAM_ERROR` | Provider returned an error | Depends |
| `RATE_LIMITED` | Provider rate-limited the request | Yes |
| `INTERNAL_ERROR` | Unexpected dispatcher error | No |

---

## Configuration

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `AXIOLEX_HYBRID_ENABLED` | `false` | Enable hybrid search at startup |
| `AXIOLEX_COLBERT_MODEL` | `colbert-ir/colbertv2.0` | HuggingFace model identifier |
| `AXIOLEX_COLBERT_CACHE_DIR` | FastEmbed default | Local cache directory for model weights |
| `AXIOLEX_COLBERT_BATCH_SIZE` | `32` | Encoding batch size |
| `AXIOLEX_HYBRID_CANDIDATE_LIMIT` | `100` | Per-model candidate count before fusion |
| `AXIOLEX_RRF_K` | `60` | Reciprocal Rank Fusion constant |
| `AXIOLEX_HYBRID_BM25_WEIGHT` | `0.4` | Default BM25 blend weight |
| `AXIOLEX_HYBRID_COLBERT_WEIGHT` | `0.6` | Default ColBERT blend weight |
| `AXIOLEX_EXECUTE_TIMEOUT_MS` | `30000` | Execution timeout ceiling |
| `AXIOLEX_SECRET_MASTER_KEY` | — | Master key for encrypted secret store |
| `BM25S_TEMPERATURE` | `0.5` | Softmax temperature |
| `BM25S_IGNORE_ZERO` | `true` | Filter zero-score results |
| `BM25S_CUTOFF` | `10.0` | Minimum softmax percentage |
| `BM25S_HOST` | `0.0.0.0` | Server host |
| `BM25S_PORT` | `9700` | Server port |
| `BM25S_LOG_LEVEL` | `info` | Log level |

### Hybrid search tuning

For temperature, cutoff, hybrid weights, and ColBERT model configuration, see the [Application Reference](app_reference.md#performance-tuning).

### settings.yaml

```yaml
bm25s:
  temperature: 0.5
  ignore_zero: true
  llm_tools_cutoff: 10.0

documents:
  source: "source_files/tools_list.yaml"
  auto_reload: true
  encoding: "utf-8"

server:
  host: "0.0.0.0"
  port: 9700
  reload: false
  log_level: "info"
```
