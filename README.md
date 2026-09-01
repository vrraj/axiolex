# Axiolex

[![PyPI - Version](https://img.shields.io/pypi/v/axiolex?color=blue&logo=pypi&logoColor=white)](https://pypi.org/project/axiolex/)
[![GitHub Release](https://img.shields.io/github/v/release/vrraj/axiolex?label=github%20release&color=orange&logo=github)](https://github.com/vrraj/axiolex/releases)
![CI Status](https://github.com/vrraj/axiolex/actions/workflows/ci.yml/badge.svg)

> **Capability discovery for enterprise applications and AI clients**

Axiolex provides a searchable catalog of enterprise capabilities, including tools, MCP services, A2A endpoints, and internal services.

Core business capabilities become discoverable to AI clients and AI-enabled applications such as Claude, Cursor, enterprise copilots, and internal agentic applications without each user needing to know what exists, who owns it, or where it is deployed.

For each request, Axiolex can expose only the capabilities relevant to the user's intent—reducing tool confusion, limiting context and token overhead, and giving applications a controlled way to govern which capabilities are available.

## The problem, in numbers

An AI client connected to 20 MCP servers with 10 tools each may have 200 tool definitions available. If those schemas average 200–300 tokens each across names, descriptions, input schemas, and examples, tool definitions alone could consume roughly **40,000–60,000 tokens of context** before the user's question, conversation history, or retrieved data are added.

Anthropic has documented the same scaling problem, including a 58-tool example consuming approximately **55,000 tokens** before the conversation begins. [Source](https://www.anthropic.com/engineering/advanced-tool-use)

This creates four compounding effects:

- **Token cost.** Large tool catalogs consume model context before the user request, conversation history, or retrieved data are added.
- **Selection accuracy degrades with catalog size.** As more tools are added, the model has to distinguish among more plausible candidates, including tools with similar names, descriptions, or parameter schemas.
- **Governance has no natural point of enforcement.** When each client maintains its own tool inventory, capability visibility, updates, and scope have to be managed separately across those clients.
- **Client registries become stale.** Enterprises continuously add MCP servers and tools, retire capabilities, rename tools, change schemas and descriptions, or move capabilities between providers. Clients that maintain their own registered tool lists can fall out of sync with the current enterprise capability set.

Axiolex addresses this by separating **capability discovery** from **capability execution**, and by using the request intent to retrieve a small relevant set of capabilities within the applicable search scope rather than exposing an entire enterprise catalog to every client, every time.

## Enterprise Requests

Axiolex represents enterprise capabilities — tools, MCP services, A2A endpoints, and internal services — as a searchable catalog organized by business domain.

| User query | Search scope |
| --- | --- |
| "Show which business units have the largest variance between forecast and actual revenue." | Finance |
| "Check whether the Micron NDA covers product evaluation." | Legal |
| "Show engineering roles that have remained unfilled for more than 60 days." | HR Recruiting |
| "What health insurance options are available for dependents?" | HR Employee Services |
| "Explain what is driving the predicted supplier lead time up for `SAMSUNG_HBM3e_LINES`." | Supply Chain |
| "Which deals expected to close this quarter are still waiting for contract approval?" | Sales + Legal |

A calling application or AI client can use **single-scope discovery**, **multi-scope discovery**, or **full-catalog discovery**, depending on the request.

Axiolex represents these search scopes as **namespaces**, such as `finance`, `legal`, `sales`, `hr.recruiting`, `hr.employee_services`, and `supply_chain`.

A request can search one namespace, multiple namespaces, or `all`. When a namespace is supplied, it defines a hard search boundary; Axiolex retrieves and ranks capabilities only from that eligible scope.

## How Axiolex Is Used

Applications and AI clients use Axiolex to retrieve a small set of tools and capabilities matched to the **user's query intent**, within the applicable search scope.

Axiolex supports two common integration patterns.

### Purpose-Built Enterprise Applications

Applications that control their own orchestration can send the request intent and applicable namespace scope directly to Axiolex.

```text
User Request
     ↓
query intent + namespace scope
     ↓
Axiolex
     ↓
Intent-matched tools and capabilities
```

The namespace defines the eligible capability set. Axiolex uses the query intent to retrieve and rank the tools within that scope.

The application can then **orchestrate and execute the selected tool itself**, or use `axiolex_execute_tool` to execute it through Axiolex.

### General-Purpose AI Clients and Agents

AI clients such as Claude, Cursor, enterprise copilots, and other agents can discover the organization's available business scopes through `list_namespaces()`.

The namespace names and descriptions can remain available in the client's session context. For each user request, the client can use that context to select a **single scope, multiple scopes, or `all`** and pass the selected namespace(s) with the query to Axiolex.

```text
User Request
     ↓
AI client selects scope from namespace context
     ↓
Axiolex retrieves tools matching query intent
within that scope
```

The client does not need to call `list_namespaces()` again during the same session unless the namespace catalog needs to be refreshed.

For clients that cannot dynamically register a newly discovered downstream tool as callable during the active session, Axiolex provides a stable execution interface:

```text
axiolex_discover_tools(...)
        ↓
tool_id + tool contract
        ↓
axiolex_execute_tool(tool_id, arguments)
        ↓
underlying MCP / service capability
```

The client only needs Axiolex's discovery and execution tools registered ahead of time. Changes to downstream tools, providers, endpoints, and transports are resolved through the current Axiolex catalog rather than requiring those capabilities to be individually registered with the client.

**Full-catalog discovery.** Some clients or workflows may need to consider the full enterprise catalog.

```python
results = client.discover(
    query="find the capability that can analyze supplier lead-time risk",
    namespaces=["all"],
)
```

Axiolex still ranks results against the query intent; `all` removes the namespace boundary, not the relevance filter.

## Discovering Enterprise MCP Capabilities

Axiolex keeps a shared catalog of enterprise capabilities current as MCP servers, tools, schemas, and providers change.

```text
MCP Providers          Static Registries          Internal Services
     │                        │                         │
     └────────────────────────┼─────────────────────────┘
                              ↓
                         Axiolex Catalog
                              ↓
              Applications · AI Clients · Agents
```

Registered providers can be refreshed so new, changed, renamed, or retired capabilities are reflected centrally and become available to consumers on subsequent discovery calls.

For MCP-capable clients, Axiolex exposes a stable interface:

```text
list_namespaces()
axiolex_discover_tools(...)
axiolex_execute_tool(...)
```

## Namespace Model

Namespaces give applications and AI clients a deterministic way to limit which enterprise capabilities are eligible for a request before retrieval and ranking begin.

- **Single-scope discovery** searches one namespace.
- **Multi-scope discovery** searches the union of multiple namespaces.
- **Full-catalog discovery** uses `all` and searches across the complete catalog.

Each namespace includes a name and description so AI clients can understand the business area before selecting it.

| Namespace | Capability area |
| --- | --- |
| `finance` | Financial planning, forecasting, reporting, revenue, costs, and related finance capabilities |
| `legal` | Contracts, agreements, legal review, and related legal capabilities |
| `sales` | Opportunities, accounts, pipeline, and related sales capabilities |
| `hr.recruiting` | Recruiting, open roles, candidates, requisitions, and hiring workflows |
| `hr.employee_services` | Benefits, insurance, leave, compensation, payroll, and employee support |
| `supply_chain` | Suppliers, procurement, inventory, logistics, and related supply-chain capabilities |

A capability can belong to more than one namespace. A discovery request can search one namespace, multiple namespaces, or the full catalog. Unknown namespaces fail explicitly rather than widening the search scope.

A general-purpose client such as Claude or Cursor can use these definitions from `list_namespaces()` to determine whether a user request should be scoped to `legal`, another namespace, multiple namespaces, or `all`.

## How Axiolex Fits

Axiolex connects enterprise capabilities to applications and AI clients through a shared discovery layer and, when needed, a stable execution path.

```text
Enterprise Capabilities
MCP tools · A2A endpoints · Internal services
                │
                ▼
          Axiolex Catalog
                │
                ▼
axiolex_discover_tools(query, namespaces[])
                │
                ▼
 Intent-matched capabilities
      + tool_id + tool contract
                │
        ┌───────┴───────────────┐
        │                       │
        │                       │
        ▼                       ▼

Purpose-built app        Fixed-integration client
or orchestrator          such as Claude / Cursor

        │                       │
        │                       │
        │ direct                ▼
        │ execution     axiolex_execute_tool(
        │                   tool_id,
        │                   arguments
        │               )
        │                       │
        │                       │
        └───────────┬───────────┘
                    │
                    ▼
          Underlying MCP / service
```

A purpose-built application can orchestrate and execute the discovered capability itself.

A client that cannot dynamically register newly discovered tools can use:

```text
axiolex_execute_tool(tool_id, arguments)
```

Axiolex resolves the current provider, transport, endpoint, and tool contract from the catalog at execution time.

## Core Capabilities

Axiolex gives enterprise applications and AI clients a consistent way to discover, rank, and execute capabilities from a changing catalog without loading or managing the full tool inventory in every client.

- **Shared capability catalog** — maintains a current catalog of tools, MCP services, A2A endpoints, and internal services across registered providers.
- **Dynamic provider and tool discovery** — refreshes registered MCP providers so new, changed, renamed, or retired tools are reflected centrally.
- **Query-intent-based tool discovery** — `axiolex_discover_tools()` matches the request intent against eligible capabilities and returns a small ranked set of tools.
- **Scoped retrieval** — supports single-scope, multi-scope, and full-catalog discovery using namespaces.
- **Namespace discovery** — exposes available business scopes and descriptions through `list_namespaces()` for general-purpose AI clients.
- **Hybrid ranking** — combines BM25S lexical retrieval with optional ColBERT semantic retrieval.
- **Execution-ready contracts** — returns `tool_id`, tool schemas, parameters, provider metadata, and runtime information needed for orchestration or execution.
- **Multiple integration paths** — supports HTTP, the Python SDK, CLI, and the Axiolex MCP interface.
- **Request audit trail** — records request intent, search scope, ranked results, scores, and latency for evaluation and troubleshooting.

## Tool Discovery Flow

Axiolex narrows the enterprise catalog in two steps: **search scope defines which capabilities are eligible, and query intent determines which of those capabilities rank highest.**

```text
User request
     ↓
query intent + namespace scope
     ↓
eligible capability set
     ↓
BM25S + optional ColBERT
     ↓
ranked Top-K tools
     ↓
application / AI client
```

For multi-scope requests, Axiolex searches the union of the supplied namespaces. With `all`, the full catalog is eligible for retrieval.

`top_k` controls the maximum number of tools returned. The calling application or AI client decides which returned tools are used, injected into model context, or executed.

## Consumption Model

Applications and AI clients access Axiolex through stable interfaces while catalog management, retrieval, ranking, and provider resolution remain inside the Axiolex service.

- **Tool registry** — MCP providers, static registries, A2A endpoints, and internal services are normalized into the shared Axiolex catalog.
- **Access interfaces** — Python SDK, HTTP API, and MCP client interface.
- **Retrieval** — BM25S lexical retrieval with optional ColBERT hybrid ranking.
- **Execution** — purpose-built applications can orchestrate tools directly; fixed-integration clients can use `axiolex_execute_tool`.
- **Shared state** — Redis stores the current catalog and runtime metadata; consumers do not connect to Redis directly.

**Python SDK**

```python
from axiolex import Axiolex

client = Axiolex(base_url="http://localhost:9700")

tools = client.discover(
    query="contract approval status",
    namespaces=["legal"],
    top_k=7,
)

for tool in tools["tools"]:
    print(tool["name"], tool["relevance_score"])
```

The base PyPI package is a thin HTTP client. Applications do not connect directly to Redis, build indexes, load ColBERT, or discover MCP providers themselves.

**MCP interface**

```text
list_namespaces()
axiolex_discover_tools(...)
axiolex_execute_tool(...)
```

Consumers do not need to build retrieval indexes, manage MCP provider refresh, or maintain their own copy of the enterprise capability catalog.

## Provider and Catalog Management

Axiolex keeps the shared capability catalog current as providers and tools change.

- **Provider management** — add, edit, enable, disable, or remove MCP providers.
- **Catalog refresh** — retrieve current tool definitions from registered providers and update the shared catalog.
- **Namespace assignment** — map providers and capabilities to the business scopes used for discovery.
- **Change propagation** — additions, renames, schema changes, and retirements become available to consumers through subsequent discovery calls.
- **Catalog versioning** — catalog updates increment a shared version so Axiolex processes can rebuild their in-memory retrieval indexes from the latest state.
- **Management interfaces** — provider and catalog operations are available through the Axiolex Web UI and REST APIs.

This allows capability lifecycle changes to be managed centrally instead of separately in each consuming application or AI client.

## Retrieval and Ranking

Axiolex ranks the capabilities most likely to satisfy the request intent within the selected search scope.

- **Lexical retrieval** — BM25S matches tool names, descriptions, parameters, and domain terminology.
- **Optional semantic retrieval** — ColBERT adds semantic matching when lexical overlap alone is not sufficient.
- **Hybrid ranking** — lexical and semantic scores can be combined into a single ranked result set.
- **Unified relevance score** — consumers receive a consistent `relevance_score` regardless of retrieval mode.
- **Top-K results** — Axiolex returns only the highest-ranked capabilities requested by the caller.

```text
query intent
    ↓
eligible capabilities
    ↓
BM25S
 + optional ColBERT
    ↓
ranked Top-K tools
```

Retrieval mode and ranking weights are deployment settings; consuming applications do not need to manage the underlying search implementation. For tuning details (temperature, cutoff, hybrid weights, ColBERT model configuration), see the [Application Reference](docs/app_reference.md).

### Search Result Contract

Each discovery result returns the information a calling application or AI client needs to evaluate, present, orchestrate, or execute the capability.

Typical fields include:

- `tool_id` — stable Axiolex identifier for the capability.
- `name` and `description` — human- and model-readable tool definition.
- `parameters` — input schema for the capability.
- `namespace` — business scope associated with the result.
- `provider` — source provider or service.
- `relevance_score` — normalized ranking score from `0` to `1`.
- `bm25_score` — lexical retrieval score when available.
- `colbert_score` — semantic retrieval score when hybrid search is enabled.
- `transport` and runtime metadata — information required by an orchestrator or Axiolex execution layer.

```json
{
  "tool_id": "finance.market_data.get_quote",
  "name": "get_quote",
  "description": "Retrieve the latest market quote for a security",
  "namespace": "finance",
  "provider": "market-data-mcp",
  "relevance_score": 0.94,
  "parameters": {
    "type": "object",
    "properties": {
      "symbol": {
        "type": "string"
      }
    },
    "required": ["symbol"]
  }
}
```

The exact runtime location of the capability does not need to be embedded in the client. Axiolex resolves the current provider and execution details from the catalog when required. For full response schemas (discover and retrieve), see the [Application Reference](docs/app_reference.md).

## Tool Execution

Axiolex can execute a discovered capability by `tool_id` without requiring the client to know the provider endpoint or transport.

```text
axiolex_execute_tool(tool_id, arguments)
```

Axiolex resolves the current provider and tool contract from the catalog, validates the arguments, and invokes the underlying capability.

Execution supports registered MCP providers over Streamable HTTP and stdio.

Purpose-built applications can also execute discovered tools directly when they control their own orchestration.

### Request

```json
{
  "tool_id": "string, required — the stable identifier returned by axiolex_discover_tools",
  "arguments": "object, required — matches the input_schema returned by discovery for this tool_id",
  "idempotency_key": "string, optional",
  "timeout_ms": "integer, optional, default: dispatcher-configured ceiling"
}
```

- **`tool_id`** — the stable identifier `axiolex_discover_tools` returned, not the raw tool name (names are not guaranteed unique across providers). This is the only handle the caller needs; the dispatcher resolves endpoint, transport, and provider from the current catalog by `tool_id` at call time.
- **`arguments`** — validated against the tool's *current* schema at execution time, not a schema the caller may have cached from an earlier discovery call.
- **`idempotency_key`** — optional, caller-supplied. Recommended for any tool with side effects (order creation, record updates). See [Idempotency](#idempotency) below.
- **`timeout_ms`** — optional override of the default execution timeout. Clamped to the dispatcher ceiling (`AXIOLEX_EXECUTE_TIMEOUT_MS`, default 30000).

No `endpoint`, `method`, or transport details. The caller never supplies or needs to know how the tool is reached — the dispatcher resolves that from the catalog.

### Response

```json
{
  "status": "success | error",
  "result": "object — present when status = success, shape defined by the underlying tool",
  "error": {
    "code": "string",
    "message": "string — human-readable, safe to show the caller",
    "retryable": "boolean"
  },
  "tool_id": "string — echoed back for correlation",
  "execution_id": "string — unique per call, for tracing/audit"
}
```

`tool_id` and a fresh `execution_id` are always echoed back on both success and error paths.

### Error codes

| Code | Meaning | Retryable |
| --- | --- | --- |
| `TOOL_NOT_FOUND` | `tool_id` doesn't resolve in the current catalog | No |
| `TOOL_UNAVAILABLE` | Tool's transport is not supported by this dispatcher build | No |
| `INVALID_ARGUMENTS` | `arguments` fails schema validation against the current contract | No |
| `UPSTREAM_TIMEOUT` | Underlying call exceeded `timeout_ms` | Yes |
| `UPSTREAM_ERROR` | Underlying tool/transport returned an error | Depends |
| `RATE_LIMITED` | Dispatcher or upstream rate limit hit | Yes |
| `INTERNAL_ERROR` | Dispatcher-side failure, unrelated to the above | Yes |

### How it works

```text
axiolex_execute_tool(tool_id, arguments)
        │
        ▼
  Axiolex catalog lookup (Redis)
        │
        ▼
  resolve provider + transport + endpoint
        │
        ▼
  validate arguments against current schema
        │
        ▼
  execute through transport adapter
        (Streamable HTTP for remote providers,
         stdio for local subprocess providers)
        │
        ▼
  normalize result into response contract
```

Every call is fully self-contained — the dispatcher does not assume `axiolex_discover_tools` was called in the same session. `tool_id` is re-resolved fresh from the catalog on every call.

### Idempotency

The `idempotency_key` field is accepted and logged to the execution audit log, but **de-duplication is not enforced in Phase 1**. The field exists in the contract so callers can start sending it immediately without a schema change later. When the idempotency store is wired in, the dispatcher will short-circuit repeat calls with the same key within a bounded window (recommended: 24h) and return the original result rather than re-executing.

The downstream MCP providers do not see or participate in idempotency — it is an Axiolex-side concern. The MCP protocol's `tools/call` method takes only `name` and `arguments`; the dispatcher decides whether to send the call or return a cached result.

### Phase 1 boundary

Phase 1 does not implement user-level authorization or policy enforcement. The execution interface is intended for trusted environments. Authentication, authorization, and per-user capability governance can be added later as a separate execution-policy layer without changing the `execute_tool(tool_id, arguments)` contract.

### Python convenience function

```python
import asyncio
from axiolex import execute_tool

async def main():
    response = await execute_tool(
        tool_id="text_tools:extract_keywords",
        arguments={"text": "Axiolex routes requests to tools using hybrid retrieval", "max_keywords": 5},
    )
    print(response["status"])   # "success"
    print(response["result"]["content"][0]["text"])

asyncio.run(main())
```

## Artifact-Aware Capability Metadata

Capability definitions can include artifact metadata for tools that produce renderable output such as SVG charts.

```yaml
artifact:
  produces_artifact: true
  injection_mode: verbatim
  artifact_type: svg
  artifact_key: svg
  placeholder: "{{ARTIFACT:stock_chart_svg}}"
```

A consuming gateway can use this metadata to keep large rendered artifacts out of the model context while passing compact semantic results back to the LLM.

```text
Axiolex discovers artifact-producing tool
        │
        ▼
Host gateway executes tool
        │
        ├── rendered artifact → client UI
        │
        └── compact semantic result → LLM
```

## Discovery Audit Logging

Axiolex records each discovery request so teams can evaluate retrieval quality, troubleshoot routing, and understand how capabilities are being selected.

Each audit record includes:

- query
- namespace scope
- returned Top-K tools and relevance scores
- discovery latency
- caller identifier

```json
{
  "query": "contract approval status",
  "namespaces": ["legal"],
  "results": [
    {
      "tool_name": "get_contract_approval_status",
      "relevance_score": 0.87
    }
  ],
  "latency_ms": 24
}
```

Discovery logging is append-only and does not affect the discovery response if logging fails.

**Log location:** `logs/discovery_audit.jsonl` (override with `AXIOLEX_LOG_DIR`). The file rotates at 10 MB with 5 backups.

## Install and Quick Start

Install the thin Python SDK:

```bash
uv add axiolex
```

or:

```bash
pip install axiolex
```

Optional extras:

| Extra | Command | Purpose |
| --- | --- | --- |
| `server` | `pip install "axiolex[server]"` | FastAPI, Uvicorn, BM25S, PyStemmer, Redis, MCP SDK, cryptography, and server dependencies |
| `colbert` | `pip install "axiolex[colbert]"` | FastEmbed, ONNX Runtime, NumPy, and ColBERT hybrid retrieval |
| `dev` | `pip install "axiolex[dev]"` | pytest, black, ruff |

For a full server with hybrid retrieval:

```bash
pip install "axiolex[server,colbert]"
```

### Deployment

Axiolex runs as a shared FastAPI service with Redis-backed catalog state.

Typical deployment components are:

- **Axiolex server** — REST and MCP interfaces.
- **Redis** — shared capability catalog and runtime metadata.
- **Registered MCP providers** — Streamable HTTP or stdio.
- **Optional ColBERT runtime** — for hybrid semantic retrieval.

Docker can be used to run the Axiolex server and Redis together.

### Python SDK

```python
from axiolex import Axiolex

client = Axiolex(base_url="http://localhost:9700")

results = client.discover(
    query="contract approval status",
    namespaces=["legal"],
    top_k=7,
)
```

### REST API

```bash
curl -X POST http://localhost:9700/discover \
  -H "Content-Type: application/json" \
  -d '{
        "query": "contract approval status",
        "namespaces": ["legal"],
        "max_tools": 7
      }'
```

### List Namespaces

```python
namespaces = client.list_namespaces()

for namespace in namespaces:
    print(namespace["id"], namespace["description"])
```

A purpose-built application can use configured namespaces directly. A general-purpose client can call `list_namespaces()` to discover the enterprise capability map before selecting a search scope.

**Links:** [PyPI](https://pypi.org/project/axiolex/) · [GitHub](https://github.com/vrraj/axiolex) · [API Documentation](https://vrraj.github.io/axiolex/)

## Provider Transports and Authentication

Axiolex can connect to registered MCP providers using:

- **Streamable HTTP** — for remote MCP servers.
- **stdio** — for locally launched MCP servers.

Provider credentials remain server-side and can be supplied through configured environment variables or provider-specific secret references.

The consuming application or AI client does not need direct access to downstream provider credentials.

### Encrypted secret store

Providers can be onboarded entirely from the web UI without backend `.env` access. When a user pastes an API key or token into the masked "API Key / Token" field in the Add/Edit MCP Provider form, Axiolex encrypts it with AES-256-GCM and writes it to `source_files/mcp_secrets.enc` (git-ignored, file mode `0600`). The encryption key is a single master key in `.env`:

```bash
# Generate once and add to .env:
openssl rand -hex 32
# AXIOLEX_SECRET_MASTER_KEY=<the generated hex string>
```

Secret resolution order at discovery time:

1. **OS environment** — the variable named in `auth.secret_env` (`.env` path). Checked first so existing setups keep working unchanged.
2. **Encrypted secret store** — keyed by provider ID (frontend-onboarded path).
3. **`None`** — discovery fails with a clear error.

Both paths coexist without migration. A provider can use `.env` only, the encrypted store only, or both (env takes precedence). The encrypted store is opt-in per provider — leave the "API Key / Token" field blank to keep using the environment variable.

### Security properties

- Provider YAML (`source_files/mcp_providers.yaml`) stores only the environment variable **name** (`auth.secret_env`) and the query-parameter name (`auth.key_param`), never the secret value.
- `MCPProviderConfig` rejects inline `secret_value`, credentials embedded in URLs, and credentials in headers.
- The REST endpoints (`/mcp-providers`, `/mcp-providers/{id}/discover`) and the Redis runtime cache expose only `auth.type`, `auth.secret_env`, and `auth.key_param`, never the key value.
- Outbound URLs are redacted before logging via `redact_url()` so `apikey`, `key`, `token`, `tavilyapikey`, and similar values appear as `REDACTED`.

### Provider configuration fields

| Field | Required | Description |
| --- | --- | --- |
| `id` | Yes | Stable unique identifier (lowercase, underscores). Used in tool IDs and Redis cache keys. |
| `name` | Yes | Human-readable display name shown in the UI. |
| `transport` | Yes | `streamable-http` (default, for remote MCP servers) or `stdio` (for local subprocesses). |
| `endpoint` | For HTTP/Streamable-HTTP | Full URL of the provider's MCP server. Do not embed credentials here. |
| `command` | For stdio | Executable to launch a local MCP subprocess (e.g. `python`, `node`). |
| `args` | For stdio | Comma-separated command-line arguments passed to `command`. |
| `auth.type` | No | `none`, `bearer`, or `api_key`. |
| `auth.secret_env` | For authenticated providers | Name of the environment variable holding the secret (fallback to encrypted store if not set). |
| `auth.key_param` | No | Query-parameter name for API Key auth with HTTP/Streamable-HTTP transport. Defaults to `api_key`. Override for providers like Tavily (`tavilyApiKey`). Ignored for Bearer and stdio. |
| `enabled` | No | Whether the provider participates in discovery (default `true`). |

**Example: API Key provider (Alpha Vantage, Streamable-HTTP)**

```yaml
providers:
  - id: alphavantage_finance
    name: Alpha Vantage MCP
    transport: streamable-http
    endpoint: https://mcp.alphavantage.co/mcp
    auth:
      type: api_key
      secret_env: ALPHAVANTAGE_API_KEY
    enabled: true
```

**Example: Stdio provider (local subprocess)**

```yaml
providers:
  - id: local_stdio_provider
    name: Local Stdio MCP
    transport: stdio
    command: python
    args: ["/path/to/server.py"]
    auth:
      type: none
    enabled: true
```

For custom stdio server templates, pre-built MCP servers (Fetch, Time, Git, SQLite), and the stdio discovery workflow, see the [Application Reference](docs/app_reference.md). For full configuration reference (`settings.yaml`, `namespaces.yaml`, environment variables), see the [Technical Architecture](docs/technical_architecture.md).

## API Reference

### SDK API (thin client — `pip install axiolex`)

- `Axiolex(base_url)` — Create an HTTP client (only needs httpx + pydantic)
- `client.discover(query, top_k=, namespaces=, hybrid_search=, ...) -> Dict` — Discover execution-ready tools with rank + relevance_score
- `client.retrieve(query, max_results=, namespaces=, hybrid_search=, ...) -> Dict` — Retrieve ranked documents
- `client.execute(tool_id, arguments, ...) -> Dict` — Execute a discovered tool by `tool_id`
- `client.health() -> Dict` — Check server status
- `client.list_namespaces() -> List[Dict]` — List registered namespaces

### REST endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/discover` | Discover tools (returns rank + relevance_score + tool definitions) |
| `POST` | `/retrieve` | Retrieve ranked documents |
| `POST` | `/execute` | Execute a discovered capability by `tool_id` |
| `GET` | `/capabilities` | List enabled namespaces (consumer-facing capability map) |
| `GET` | `/namespaces` | List all namespaces (management — includes disabled) |
| `POST` | `/namespaces` | Add a namespace |
| `PUT` | `/namespaces/{id}` | Update a namespace |
| `DELETE` | `/namespaces/{id}` | Delete a namespace |
| `GET` | `/status` | Server health and metrics |
| `GET` | `/mcp-providers` | List MCP providers |
| `POST` | `/mcp-providers` | Add a provider |
| `PUT` | `/mcp-providers/{id}` | Update a provider |
| `DELETE` | `/mcp-providers/{id}` | Remove a provider |
| `POST` | `/mcp-providers/{id}/secret` | Store an encrypted provider secret |
| `GET` | `/mcp-providers/{id}/secret` | Check whether a secret exists |
| `DELETE` | `/mcp-providers/{id}/secret` | Remove a stored secret |

For complete method signatures, response schemas, and CLI reference, see the [Application Reference](docs/app_reference.md). Interactive OpenAPI documentation is available from the running Axiolex server.

## Web UI

Axiolex includes a Web UI for managing providers, inspecting the capability catalog, and testing discovery behavior.

The UI can be used to:

- add, edit, enable, disable, and refresh providers
- inspect discovered tools and namespace assignments
- run discovery queries and review ranked results
- validate retrieval scores and search behavior
- test catalog changes without writing client code

The Web UI uses the same Axiolex service and catalog as the REST, Python SDK, and MCP interfaces.

![Axiolex Web UI](images/axiolex-interactive-ui.png)

Run locally:

```bash
git clone https://github.com/vrraj/axiolex.git
cd axiolex
make install   # base + server + dev tooling (BM25 lexical search)
make colbert   # optional: add ColBERT for semantic/hybrid search
make start     # host mode: Redis container + servers on host
# — or —
make docker-up # docker mode: Axiolex + Redis in containers (prod-like)
```

Open:

```text
http://localhost:9700/
```

## Development

For local development, run Axiolex with Redis and install the development dependencies.

```bash
git clone https://github.com/vrraj/axiolex.git
cd axiolex
make install
make start
```

Optional ColBERT support:

```bash
make colbert
```

> **ColBERT / hybrid search is optional.** `make install` gives you a fully working app with BM25 lexical search. Run `make colbert` to add the ColBERT extra (`fastembed`, `huggingface-hub`, `onnxruntime`), then set `AXIOLEX_HYBRID_ENABLED=true` in `.env` to enable semantic/hybrid ranking. If you edit `pyproject.toml` to add a base dependency, re-run `make install` (or `make colbert` if you had colbert installed) rather than a bare `uv sync`, since `uv sync` reconciles the `.venv` to exactly what is requested and will prune the colbert packages if `--extra colbert` is not included.

Common Makefile targets:

| Target | Purpose |
| --- | --- |
| `make install` | Install Axiolex server and development dependencies with BM25 lexical retrieval |
| `make colbert` | Add optional ColBERT hybrid retrieval dependencies |
| `make start` | Start Redis, refresh the catalog, and run the Axiolex services |
| `make stop` | Stop local services |
| `make index-refresh` | Rebuild the Redis catalog from configured sources |
| `make test` | Run the test suite |
| `make format` | Format code and run lint fixes |
| `make type-check` | Run static type checks |
| `make build` | Build Python package artifacts |
| `make clean` | Remove local build and Python cache artifacts |

### Docker deployment

Docker Compose runs Axiolex and Redis together. Redis is internal to the compose network — consumers connect only to the Axiolex HTTP port (9700). Redis is not exposed to the host.

```bash
make docker-up
# Uses the same .env file as host-mode development.
# If you don't have .env yet, it's auto-created from .env.example.
```

Verify the server is healthy:

```bash
curl http://localhost:9700/status
```

Stop:

```bash
make docker-down
```

Other Docker targets:

```bash
make docker-logs          # tail Axiolex container logs
make docker-restart       # restart Axiolex (e.g. after editing source_files/*.yaml)
make docker-build         # rebuild image without cache
make docker-down-volumes  # stop + wipe volumes (full reset)
```

For full Docker configuration details, Redis placement options, and environment variables, see the [Technical Architecture](docs/technical_architecture.md).

## Discovery and Orchestration Boundaries

Axiolex keeps tool discovery separate from request expansion, decomposition, and execution orchestration.

- **Multi-scope requests** have one intent that requires capabilities from multiple domains. The caller can search multiple namespaces together, such as `["sales", "legal"]`.

  Example:  
  *"Which deals expected to close this quarter are still waiting for contract approval?"*

  This is one business question requiring both Sales and Legal capabilities.

- **Compound requests** contain multiple independently answerable intents. The calling LLM or orchestrator should **decompose the request into focused sub-queries before tool discovery**, rather than send the blended request to retrieval as one query.

  Example:

  ```text
  User request:
  "Show open engineering roles and summarize Q3 revenue variance."

          ↓ LLM / orchestrator decomposition

  "Show open engineering roles"
      → namespace: hr.recruiting
      → axiolex_discover_tools(...)

  "Summarize Q3 revenue variance"
      → namespace: finance
      → axiolex_discover_tools(...)
  ```

  This gives Axiolex a cleaner intent for each retrieval call and avoids unrelated vocabulary from one part of the request weakening tool matches for the other.

- **Query expansion is also a caller responsibility.** The LLM can translate conversational requests into more retrieval-specific intent before calling Axiolex.

  For example:

  ```text
  "How is Apple doing lately?"
          ↓
  "Apple AAPL recent stock price performance and market data"
          ↓
  axiolex_discover_tools(...)
  ```

  Axiolex ranks tools against the query it receives; it does not rewrite, expand, or decompose the request itself.

- **Namespace scope is a hard boundary.** A supplied namespace limits which capabilities are eligible; multiple namespaces search their union, while `all` searches the full catalog.

- **Execution sequencing belongs to the caller.** Independent work can be discovered upfront. Workflows with data dependencies can use `discover → execute → discover`.

- **Catalog currency belongs to Axiolex.** MCP `tools/list_changed` can signal tool changes for a server the client is already connected to, but it does not solve discovery of newly deployed MCP servers.

  Even within an existing connection, `list_changed` depends on both sides implementing it correctly:
  - **Client support varies** — clients differ in whether and when they refresh tool definitions.
  - **Servers must emit the notification** — if a server does not implement `listChanged`, the client receives no update.
  - **Active conversations may still contain stale tool context** — refreshing the tool list does not automatically replace tool descriptions or parameter assumptions already present in the conversation.

  Axiolex maintains the enterprise capability catalog centrally, so newly registered providers and refreshed tool definitions become available on subsequent discovery calls.

- **Discovery quality and namespace selection can be evaluated separately.** Tool retrieval accuracy measures whether the correct capability ranks highly; namespace-selection accuracy measures whether the caller selected the correct search scope.

Axiolex's contract remains narrow: **given a focused query and an optional search scope, return the current capabilities most relevant to that intent and provide a stable execution path when needed.**

## Documentation and License

### Documentation

- [GitHub Repository](https://github.com/vrraj/axiolex)
- [PyPI Package](https://pypi.org/project/axiolex/)
- [API Documentation](https://vrraj.github.io/axiolex/)
- [Technical Architecture](docs/technical_architecture.md) — system layers, request lifecycle, subsystems, module reference, deployment
- [Application Reference](docs/app_reference.md) — install, SDK API, REST endpoints, CLI, configuration, MCP integration
- [Claude Desktop Setup](docs/claude-mcp.md) — connecting Claude to the Axiolex MCP server
- [Medium: Context Engineering for Tool-Heavy Agents](https://medium.com/@vr.rajkumar99/context-engineering-for-tool-heavy-agents-lexical-routing-c1b0ebad7495)

### Third-Party Model Notice

Optional hybrid retrieval downloads the pinned [`colbert-ir/colbertv2.0`](https://huggingface.co/colbert-ir/colbertv2.0) checkpoint through FastEmbed.

The model is not included in the repository or Axiolex package. Its model card declares the [MIT License](https://opensource.org/license/mit); see the [upstream model card](https://huggingface.co/colbert-ir/colbertv2.0) for the model and its current metadata.

### License

This project is licensed under the **GNU General Public License v3.0 (GPLv3)**.

- Feel free to clone, modify, run locally, and use it for personal, educational, or open-source projects.
- If you modify, bundle, or distribute `axiolex` code as part of a commercial application, GPLv3 requires you to open-source your entire application under the same license.

#### Commercial Licensing

If you want to integrate Axiolex into a closed-source proprietary system, or require a custom enterprise domain setup, a commercial license is available.

Interested in a commercial license? Contact `ai0musings99@gmail.com`.
