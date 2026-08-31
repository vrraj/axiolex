# Axiolex

[![PyPI - Version](https://img.shields.io/pypi/v/axiolex?color=blue&logo=pypi&logoColor=white)](https://pypi.org/project/axiolex/)
[![GitHub Release](https://img.shields.io/github/v/release/vrraj/axiolex?label=github%20release&color=orange&logo=github)](https://github.com/vrraj/axiolex/releases)
![CI Status](https://github.com/vrraj/axiolex/actions/workflows/ci.yml/badge.svg)

> **Capability discovery for enterprise applications and AI clients**

Axiolex provides a searchable catalog of enterprise capabilities, including tools, MCP services, A2A endpoints, and internal services.

Core business capabilities become discoverable to AI clients and AI-enabled applications such as Claude, Cursor, enterprise copilots, and internal agentic applications without each user needing to know what exists, who owns it, or where it is deployed.

For each request, Axiolex can expose only the capabilities relevant to the user's intent—reducing tool confusion, limiting context and token overhead, and giving applications a controlled way to govern which capabilities are available.

## Enterprise Requests

End users ask normal business questions across Finance, Legal, HR, Sales, Supply Chain, and other business areas.

> **"Show which business units have the largest variance between forecast and actual revenue."**  
> Search scope: Finance

> **"Check whether the Micron NDA covers product evaluation."**  
> Search scope: Legal

> **"Show engineering roles that have remained unfilled for more than 60 days."**  
> Search scope: HR Recruiting

> **"What health insurance options are available for dependents?"**  
> Search scope: HR Employee Services

> **"Explain what is driving the predicted supplier lead time up for `SAMSUNG_HBM3e_LINES`."**  
> Search scope: Supply Chain

> **"Which deals expected to close this quarter are still waiting for contract approval?"**  
> Search scope: Sales + Legal

A calling application or AI client can use **single-scope discovery**, **multi-scope discovery**, or **full-catalog discovery**, depending on the request.

Axiolex represents these search scopes as **namespaces**, such as `finance`, `legal`, `sales`, `hr.recruiting`, `hr.employee_services`, and `supply_chain`. A request can search one namespace, multiple namespaces, or `all`.

## How Axiolex Is Used

### Domain and Enterprise Applications

A purpose-built application can be configured with the business areas it is allowed to search.

An HR application might use:

```text
hr.recruiting
hr.employee_services
```

A sales application might use:

```text
sales
finance
legal
```

For each request, the application selects the relevant search scope and asks Axiolex to discover matching capabilities.

```text
User
  │
  │ "What health insurance options are available for dependents?"
  ▼
HR Application
  │
  │ namespace: hr.employee_services
  ▼
Axiolex
  │
  ▼
Relevant enterprise capabilities
```

A business request can span more than one area:

```text
User
  │
  │ "Which deals expected to close this quarter
  │  are still waiting for contract approval?"
  ▼
Sales Application
  │
  │ namespaces: sales + legal
  ▼
Axiolex
  │
  ▼
Relevant enterprise capabilities
```

### General-Purpose AI Clients and Agents

A general-purpose AI client may not know the organization's capability map in advance.

Axiolex exposes that map through `list_namespaces()`. The client can use the returned names and descriptions to determine the relevant search scope, then call `axiolex_discover_tools()`.

```text
User
  │
  │ "What health insurance options are available for dependents?"
  ▼
AI Client / Agent
  │
  ├── list_namespaces()
  │       finance
  │       legal
  │       sales
  │       hr.recruiting
  │       hr.employee_services
  │       supply_chain
  │
  ├── selects: hr.employee_services
  │
  └── axiolex_discover_tools(
          query="health insurance options for dependents",
          namespaces=["hr.employee_services"]
      )
          │
          ▼
     Relevant enterprise capabilities
```

Clients can cache the namespace catalog rather than retrieving it for every request.

### Full-Catalog Discovery

Some clients or workflows may need to consider the full enterprise catalog.

```python
results = client.discover(
    query="find the capability that can analyze supplier lead-time risk",
    namespaces=["all"],
)
```

This preserves the same discovery interface while allowing the calling application to choose between **single-scope**, **multi-scope**, and **full-catalog** search.

## Discovering Enterprise MCP Capabilities

Enterprise MCP servers may be deployed by different teams using stdio or Streamable HTTP. Developers and employees using MCP-capable clients may not know which servers exist, which capabilities they provide, or when new services become available.

Axiolex maintains a shared searchable catalog of capabilities discovered from registered MCP providers and configured internal sources.

```text
MCP Providers          Static Registries          Internal Services
     │                        │                         │
     └────────────────────────┼─────────────────────────┘
                              ▼
                         Axiolex Catalog
                              │
                    Searchable capability map
                              │
                ┌─────────────┴─────────────┐
                ▼                           ▼
        Enterprise Apps              AI Clients / Agents
```

When a registered MCP provider is refreshed, its discovered tools are normalized into the shared catalog and become available through Axiolex discovery.

A client connected to the Axiolex MCP discovery server can use:

```text
list_namespaces()
axiolex_discover_tools(query, namespaces[])
```

The discovery interface gives AI clients a consistent way to find capabilities across registered MCP providers. Downstream tool execution remains with the consuming application or execution layer.

## Namespace Model

Namespaces define the capability scope Axiolex searches. They are application and agent concepts; end users do not need to include them in their questions.

Example namespace catalog:

| Namespace | Capability area |
| --- | --- |
| `finance` | Financial planning, forecasting, reporting, revenue, costs, and related finance capabilities |
| `legal` | Contracts, agreements, legal review, and related legal capabilities |
| `sales` | Opportunities, accounts, pipeline, and related sales capabilities |
| `hr.recruiting` | Recruiting, open roles, candidates, requisitions, and hiring workflows |
| `hr.employee_services` | Benefits, insurance, leave, compensation, payroll, and employee support |
| `supply_chain` | Suppliers, procurement, inventory, logistics, and related supply-chain capabilities |

A capability can belong to more than one namespace. A discovery request can search one namespace, multiple namespaces, or the full catalog.

Unknown namespaces fail explicitly rather than widening the search scope.

## How Axiolex Fits

```text
                    ENTERPRISE CAPABILITIES

      MCP tools · A2A endpoints · Internal services · Registries
                              │
                              ▼
                         ┌─────────┐
                         │ Axiolex │
                         └────┬────┘
                              │
                  Shared capability catalog
                              │
                Search scope / namespaces
                              │
                  Retrieval and ranking
                              │
                              ▼
             Applications · AI Clients · Agents
                              │
                              ▼
                 LLM / workflow / execution
```

The calling application determines the business intent and search scope. Axiolex searches the eligible capability set and returns the most relevant results.

Execution, authentication, authorization, workflow logic, and application-specific guardrails remain with the consuming application or execution layer.

## Core Capabilities

- **Shared capability catalog** — normalize MCP-discovered and configured capabilities into a common searchable catalog.
- **Dynamic MCP discovery** — connect to configured MCP providers and ingest their tool definitions.
- **Namespace discovery** — expose available business capability areas and descriptions through `list_namespaces`.
- **Single-scope discovery** — search within one namespace.
- **Multi-scope discovery** — search across multiple namespaces for cross-functional requests.
- **Full-catalog discovery** — search across all eligible capabilities when broader discovery is appropriate.
- **Hybrid retrieval** — combine BM25S lexical retrieval with optional ColBERT semantic retrieval.
- **Execution-ready metadata** — return tool definitions, parameter schemas, provider metadata, and runtime information to consuming applications.
- **Multiple interfaces** — consume discovery through HTTP, the thin Python SDK, CLI, or the Axiolex MCP discovery server.
- **Discovery auditing** — record discovery queries, namespace scope, ranked results, scores, and latency.

## Discovery Flow

```text
User request
     │
     ▼
Calling application / AI client
     │
     ├── determines request intent
     └── selects namespace scope
                 │
                 ▼
              Axiolex
                 │
       validate namespace scope
                 │
       resolve eligible capabilities
                 │
      ┌──────────┴──────────┐
      ▼                     ▼
    BM25S              ColBERT
                         optional
      └──────────┬──────────┘
                 ▼
             score fusion
                 ▼
             ranked Top-K
                 ▼
      application / AI client
```

Namespaces are applied before retrieval. With multiple namespaces, Axiolex searches the union of capabilities eligible for those namespaces.

`top_k` controls the maximum number of candidates returned by Axiolex. The calling application decides which results, if any, are placed into LLM context.

## Consumption Model

Axiolex is designed as a shared discovery service with thin consumers.

```text
YAML / MCP Providers / Internal Registries
                    │
                    ▼
               Redis Catalog
                    │
                    ▼
              Axiolex Service
          BM25S + optional ColBERT
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
       HTTP API          MCP Discovery
          │                   │
          ▼                   ▼
    Python SDK          AI Clients / Agents
```

### Python SDK

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

### General-Purpose Agent Pattern

```text
list_namespaces()
        │
        ▼
select relevant namespace(s)
        │
        ▼
axiolex_discover_tools(query, namespaces[])
```

### Configured Application Pattern

A purpose-built application can skip namespace discovery when its allowed scope is already known:

```python
tools = client.discover(
    query="open engineering roles older than 60 days",
    namespaces=["hr.recruiting"],
    top_k=7,
)
```

### Multi-Scope Pattern

```python
tools = client.discover(
    query="deals expected to close this quarter still waiting for contract approval",
    namespaces=["sales", "legal"],
    top_k=7,
)
```

### Full-Catalog Pattern

```python
tools = client.discover(
    query="find the enterprise capability for this request",
    namespaces=["all"],
    top_k=7,
)
```

## Capability Sources

Axiolex can build its catalog from multiple sources.

### MCP Providers

Configured MCP providers can be discovered over:

- **Streamable HTTP** — remote or independently deployed MCP services.
- **stdio** — local MCP servers and subprocess-based integrations.

Provider refresh retrieves the provider's current tool definitions, normalizes them, and updates the shared catalog.

### Static Registries

YAML-backed definitions support version-controlled tools and internal capability records.

```yaml
documents:
  - id: get_customer_profile
    title: Get Customer Profile
    content: Lookup customer account details
    keywords:
      - customer
      - profile
      - account
    namespaces:
      - sales
```

### Internal Services and Endpoints

Internal services, A2A endpoints, and other enterprise capabilities can be represented through the same normalized discovery metadata when they are registered with Axiolex.

## Provider and Catalog Management

Axiolex includes management interfaces for maintaining the capability catalog.

- Add, edit, enable, disable, and remove MCP providers.
- Assign namespaces to providers.
- Retrieve or refresh tools from individual providers.
- Remove stale provider tools before replacing them with refreshed definitions.
- Manage namespaces and namespace descriptions.
- Inspect cached tool counts.
- Load static capability definitions from YAML.
- Refresh the shared catalog without restarting consuming applications.

Catalog changes increment a shared catalog version. Axiolex processes detect the change and rebuild their in-memory retrieval indexes from the updated Redis catalog.

## Retrieval

### Lexical Search

BM25S with PyStemmer provides the base retrieval path.

Lexical search is useful for:

- tool and command names,
- enterprise terminology,
- domain-specific vocabulary,
- exact workflow language,
- deterministic low-latency retrieval.

The base install does not require a model download.

### Optional Hybrid Search

Axiolex can combine BM25S lexical retrieval with ColBERT late-interaction semantic retrieval.

```text
Query
  │
  ├── BM25S lexical candidates
  │
  └── ColBERT semantic candidates
          │
          ▼
    normalized score fusion
          │
          ▼
      ranked results
```

BM25S and ColBERT operate only on the capability set eligible for the supplied namespaces.

Axiolex normalizes each model's candidate scores independently before weighted fusion because raw BM25 and ColBERT scores use different numeric scales.

Conceptually:

```text
P_bm25(doc)   = softmax(BM25 scores / temperature)
P_colbert(doc)= softmax(ColBERT scores / temperature)

hybrid_score(doc) =
    normalized_bm25_weight   * P_bm25(doc)
  + normalized_colbert_weight * P_colbert(doc)
```

The deployment controls the default retrieval mode:

```bash
AXIOLEX_HYBRID_ENABLED=true
```

When hybrid search is unavailable, an explicit hybrid request fails clearly rather than silently falling back to lexical search.

Install the optional ColBERT extra:

```bash
uv add "axiolex[colbert]"
export AXIOLEX_HYBRID_ENABLED=true
```

The first startup with hybrid enabled downloads the pinned ColBERT ONNX model (~436MB) to `AXIOLEX_COLBERT_CACHE_DIR`. Download or verify the default model explicitly:

```bash
axiolex model-ensure --cache-dir ~/.cache/axiolex/fastembed
```

The default integrity guarantee applies only to `colbert-ir/colbertv2.0`. Setting `AXIOLEX_COLBERT_MODEL` to another model selects a user-managed model.

Optional hybrid tuning:

```bash
export AXIOLEX_COLBERT_MODEL=colbert-ir/colbertv2.0
export AXIOLEX_COLBERT_CACHE_DIR=~/.cache/axiolex/fastembed
export AXIOLEX_COLBERT_BATCH_SIZE=32
export AXIOLEX_HYBRID_CANDIDATE_LIMIT=100
export AXIOLEX_HYBRID_BM25_WEIGHT=0.4
export AXIOLEX_HYBRID_COLBERT_WEIGHT=0.6
```

### Search Result Contract

Consumers receive a unified `relevance_score`.

- In lexical mode, `relevance_score` reflects the normalized lexical ranking score.
- In hybrid mode, `relevance_score` reflects the fused hybrid ranking score.

The score is intended for ranking and approximate filtering within the current result set. It is not a probability of correctness and should not be compared as an absolute score across unrelated queries.

Internal component scores can be returned for diagnostics and tuning.

## Data Architecture

Axiolex separates the shared capability catalog from per-process search indexes.

```text
                   SOURCE DEFINITIONS
        tools_list.yaml · mcp_providers.yaml
                · namespaces.yaml
                         │
                         ▼
                 catalog refresh
                         │
                         ▼
                ┌─────────────────┐
                │      REDIS      │
                │ shared catalog  │
                │                 │
                │ discovery data  │
                │ runtime data    │
                │ catalog version │
                └────────┬────────┘
                         │
                         ▼
                Axiolex process
                         │
                ┌────────┴────────┐
                │ in-process      │
                │ search indexes  │
                │                 │
                │ BM25S           │
                │ ColBERT optional│
                └─────────────────┘
```

Redis stores shared catalog state. BM25S and ColBERT indexes are derived data held in process memory and rebuilt from Redis when the catalog version changes.

Raw MCP provider responses are transient. Axiolex normalizes discovered capabilities before storing them in the shared catalog.

## Catalog Data

Axiolex separates searchable discovery metadata from execution-oriented runtime metadata.

### Discovery Metadata

Typical searchable fields include:

- capability name and title,
- description,
- keywords,
- provider,
- source,
- namespaces,
- parameter summaries.

### Runtime Metadata

Execution-oriented fields can include:

- transport,
- endpoint,
- provider,
- command and arguments,
- authentication metadata,
- full parameter schema,
- artifact metadata.

This lets Axiolex return execution-ready capability definitions while keeping downstream execution outside the discovery service.

## MCP Discovery Server

Axiolex exposes a read-only MCP discovery interface for external AI clients and MCP hosts.

The interface exposes three tools:

```text
list_namespaces
axiolex_discover_tools
axiolex_execute_tool
```

### `list_namespaces`

Returns the configured namespace catalog with descriptions.

Example:

```json
[
  {
    "id": "finance",
    "name": "Finance",
    "description": "Financial planning, forecasting, reporting, revenue, costs and related finance capabilities"
  },
  {
    "id": "hr.employee_services",
    "name": "HR Employee Services",
    "description": "Employee benefits, insurance, leave, compensation, payroll and HR support"
  }
]
```

### `axiolex_discover_tools`

Searches the capability catalog within the supplied namespace scope and returns ranked downstream tools.

Conceptual request:

```json
{
  "query": "health insurance options for dependents",
  "namespaces": ["hr.employee_services"],
  "top_k": 7
}
```

Each returned tool includes a `tool_id` — the stable identifier to pass to `axiolex_execute_tool` to run the tool. See [Executing Tools](#executing-tools-axiolex_execute_tool) below.

### Connecting an MCP client

```python
import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main():
    async with streamable_http_client("http://localhost:9701/mcp") as streams:
        async with ClientSession(*streams[:2]) as session:
            await session.initialize()

            # tools/list exposes Axiolex's axiolex_discover_tools function.
            print(await session.list_tools())

            # tools/call returns selected downstream tool definitions.
            result = await session.call_tool(
                "axiolex_discover_tools",
                {"query": "get stock price history", "max_tools": 5},
            )
            print(result.structuredContent)


asyncio.run(main())
```

Each returned downstream tool includes:

- `tool_id`: stable identifier for passing to `axiolex_execute_tool`
- `name`: exact tool name for execution
- `description`: tool purpose
- `params` and `inputSchema`: parameter definitions
- `endpoint`: HTTP, MCP, or provider-specific endpoint configuration
- `transport`: execution transport
- `provider`: provider identifier, when available

## Executing Tools (`axiolex_execute_tool`)

`axiolex_execute_tool` is a generic dispatcher that executes a tool previously returned by `axiolex_discover_tools`. It exists for callers that cannot dynamically register a newly discovered tool as a directly callable function in their own runtime — fixed-integration clients such as Claude and Cursor.

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

### Testing with the MCP Inspector

```bash
make inspector
```

Starts the MCP server (if not running) and launches the MCP Inspector UI in your browser. Connect, then call `axiolex_execute_tool` with a `tool_id` from `axiolex_discover_tools` and the arguments the model produced.

## Artifact-Aware Capability Metadata

Capability definitions can include artifact metadata for tools that produce renderable output such as SVG charts.

Example:

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

Axiolex can record one JSONL audit entry per discovery request.

Typical fields include:

- timestamp,
- caller,
- query,
- namespaces,
- returned Top-K capability names and relevance scores,
- total discovery latency.

Example:

```json
{
  "timestamp": "2026-08-30T18:10:12.425Z",
  "caller": "default",
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

Raw BM25S, ColBERT, fusion internals, tool parameters, endpoints, request headers, and caller IP are not part of the Phase 1 discovery audit record.

A logging failure does not change an otherwise successful discovery result.

**Log location:** `logs/discovery_audit.jsonl` (override with `AXIOLEX_LOG_DIR`). The file rotates at 10 MB with 5 backups.

## Install

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

Links:

- **PyPI:** https://pypi.org/project/axiolex/
- **GitHub:** https://github.com/vrraj/axiolex
- **API documentation:** https://vrraj.github.io/axiolex/

## Quick Start

### Use the SDK Against a Running Axiolex Service

```python
from axiolex import Axiolex

client = Axiolex(base_url="http://localhost:9700")

results = client.discover(
    query="contract approval status",
    namespaces=["legal"],
    top_k=7,
)
```

### Use the REST API

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

## Authentication for MCP Providers

MCP providers that require authentication can resolve credentials from environment variables or the encrypted server-side secret store.

Provider configuration references the environment variable name; secret values are not stored in provider YAML.

Example:

```bash
TAVILY_API_KEY=...
ALPHAVANTAGE_API_KEY=...
```

The web UI can also store provider credentials in the encrypted secret store using AES-256-GCM.

Environment variables are checked first, followed by the encrypted store.

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

REST API for secret management (secrets are never returned, only their existence):

- `POST /mcp-providers/{id}/secret` — encrypt and store a secret (`{"secret": "..."}`).
- `GET /mcp-providers/{id}/secret` — returns `{"has_secret": true/false}`.
- `DELETE /mcp-providers/{id}/secret` — removes the stored secret.

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

**Example: Bearer Token provider (Streamable-HTTP)**

```yaml
providers:
  - id: my_bearer_provider
    name: My Bearer Provider
    transport: streamable-http
    endpoint: https://api.example.com/mcp
    auth:
      type: bearer
      secret_env: MY_PROVIDER_TOKEN
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

## Configuration

### `settings.yaml`

```yaml
bm25s:
  temperature: 0.5
  ignore_zero: true
  llm_tools_cutoff: 10.0

documents:
  source: "source_files/tools_list.yaml"
  auto_reload: true

server:
  host: "0.0.0.0"
  port: 9700
  reload: false
```

### `namespaces.yaml`

Namespaces define the business capability areas available for scoped discovery.

Conceptual example:

```yaml
namespaces:
  - id: finance
    name: Finance
    description: Financial planning, forecasting, reporting, revenue, costs and related finance capabilities

  - id: legal
    name: Legal
    description: Contracts, agreements, legal review and related legal capabilities

  - id: sales
    name: Sales
    description: Opportunities, accounts, pipeline and related sales capabilities

  - id: hr.recruiting
    name: HR Recruiting
    description: Recruiting, hiring, open roles, candidates and requisitions

  - id: hr.employee_services
    name: HR Employee Services
    description: Employee benefits, insurance, leave, compensation, payroll and HR support

  - id: supply_chain
    name: Supply Chain
    description: Suppliers, procurement, inventory, logistics and related supply-chain capabilities
```

### Provider Configuration

Providers can be assigned to one or more namespaces. Discovered tools inherit the provider's namespace membership.

Conceptual example:

```yaml
providers:
  - id: hr-services
    transport: streamable_http
    url: https://hr-tools.example.com/mcp
    namespaces:
      - hr.recruiting
      - hr.employee_services
```

A capability can also be registered in multiple namespaces when it legitimately serves multiple business areas.

### Environment Variables

```bash
BM25S_HOST=0.0.0.0
BM25S_PORT=9700
BM25S_RELOAD=false

BM25S_DOCUMENTS_PATH=./source_files/tools_list.yaml
BM25S_AUTO_RELOAD=true

BM25S_TEMPERATURE=0.5
BM25S_IGNORE_ZERO=true
BM25S_CUTOFF=10.0

AXIOLEX_HYBRID_ENABLED=false
AXIOLEX_COLBERT_MODEL=colbert-ir/colbertv2.0
AXIOLEX_COLBERT_CACHE_DIR=~/.cache/axiolex/fastembed
AXIOLEX_COLBERT_BATCH_SIZE=32
AXIOLEX_HYBRID_CANDIDATE_LIMIT=100
AXIOLEX_HYBRID_BM25_WEIGHT=0.4
AXIOLEX_HYBRID_COLBERT_WEIGHT=0.6
```

## Provider Transports

### Streamable HTTP

Use Streamable HTTP for remotely deployed MCP providers and independently operated enterprise services.

### stdio

Use stdio for local MCP servers, development workflows, subprocess-based integrations, and compatible packaged servers.

Axiolex supports local command-based servers as well as package-based launchers such as `uvx` and `npx`.

#### Custom MCP servers

Write your own tool server using the MCP Python SDK and place it in the `stdio_servers/` directory:

```
stdio_servers/
  README.md                      # how-to guide with templates
  text_tools/
    server.py                    # example: word count, slug generator, keyword extraction
```

Minimal server template:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("my-tools")

@mcp.tool()
def my_tool(param: str) -> str:
    """Description of what the tool does."""
    return f"Result for {param}"

if __name__ == "__main__":
    mcp.run()
```

Register it in `mcp_providers.yaml`:

```yaml
providers:
  - id: my_tools
    name: My Tools
    transport: stdio
    command: python
    args: ["stdio_servers/my_tools/server.py"]
    auth:
      type: none
    enabled: true
```

#### Pre-built MCP servers

Run published packages from PyPI or npm directly with `uvx` or `npx`. No code to write; packages are auto-downloaded on first run and cached thereafter.

| Server | Command | What it does |
| --- | --- | --- |
| Fetch | `uvx --with mcp==1.29.0 mcp-server-fetch` | Fetches web pages and converts to markdown for LLM consumption |
| Time | `uvx mcp-server-time` | Timezone conversion and current time |
| Sequential Thinking | `npx -y @modelcontextprotocol/server-sequentialthinking` | Structured reasoning through thought sequences |
| Git | `uvx mcp-server-git --repository /path/to/repo` | Read git repo status, logs, diffs |
| SQLite | `uvx mcp-server-sqlite --db-path /path/to/db` | Query a local SQLite database |

Example YAML for a pre-built server:

```yaml
providers:
  - id: mcp_fetch
    name: Fetch Server
    transport: stdio
    command: uvx
    args: ["--with", "mcp==1.29.0", "mcp-server-fetch"]
    auth:
      type: none
    enabled: true
```

> **Note on `--with mcp==1.29.0`:** Some pre-built servers depend on a `mcp` SDK version that is incompatible with the latest release. The `--with` flag pins the `mcp` version inside the `uvx` ephemeral environment so the server starts correctly. This does not affect Axiolex's own environment. Remove the pin if the server is compatible with the latest `mcp` release.

**How stdio discovery works:**

1. Axiolex spawns the subprocess using `command` + `args` from the provider config.
2. The MCP SDK communicates over stdin/stdout.
3. Axiolex calls `tools/list` to discover available tools.
4. The subprocess is terminated when discovery completes.
5. Tools are cached in Redis with `command` and `args` in the runtime metadata (instead of `endpoint`).

**Prerequisites:** `python` on the PATH for custom Python servers; `uvx` (bundled with `uv`) for PyPI-based pre-built servers; `npx` (bundled with Node.js) for npm-based pre-built servers. `uvx` and `npx` run each server in an isolated ephemeral environment — packages are downloaded once and cached and do not pollute the Axiolex virtual environment.

## API Reference

### SDK API (thin client — `pip install axiolex`)

- `Axiolex(base_url)` — Create an HTTP client (only needs httpx + pydantic)
- `client.discover(query, top_k=, namespaces=, hybrid_search=, ...) -> Dict` — Discover execution-ready tools with rank + relevance_score
- `client.retrieve(query, max_results=, namespaces=, hybrid_search=, ...) -> Dict` — Retrieve ranked documents
- `client.health() -> Dict` — Check server status
- `client.list_namespaces() -> List[Dict]` — List registered namespaces

### REST endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/discover` | Discover tools (returns rank + relevance_score + tool definitions) |
| `POST` | `/retrieve` | Retrieve ranked documents |
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

For complete method signatures and response details, see the [API Reference](https://vrraj.github.io/axiolex/api-reference.html).

### Discover response schema

The `/discover` endpoint (and SDK `discover()`) returns execution-ready tool definitions:

```python
{
    "query": str,
    "count": int,
    "search_mode": "lexical" | "hybrid",
    "tools": [
        {
            "name": str,
            "rank": int,                  # 1-based
            "relevance_score": float,     # 0.0–1.0
            "description": str,
            "params": dict,
            "inputSchema": dict,
            "endpoint": dict | str | None,
            "transport": str | None,
            "provider": str | None,
            "namespaces": list[str],
            # detailed retrieval scores (for debugging):
            "bm25_score": float | None,
            "softmax_score": float | None,
            "hybrid_score": float | None,
            "colbert_score": float | None,
            ...
        }
    ],
}
```

Axiolex decides relevance and ranking. The consuming application decides context injection — which of these tools enter the LLM context and at what threshold.

### Retrieve response schema

Every retrieved document includes a unified `rank` (1-based) and `relevance_score` (0.0–1.0) regardless of search mode. In lexical mode `relevance_score` equals `softmax_score`; in hybrid mode it equals `hybrid_score`.

```python
{
    "success": bool,
    "message": str,
    "documents": [
        {
            "id": str,
            "title": str,
            "content": str,
            "keywords": list[str],
            "metadata": dict,             # includes "namespaces": list[str]
            "runtime": dict,
            "artifact": dict,
            "params": dict,
            "rank": int,                  # unified: 1-based rank after final sort
            "relevance_score": float,     # unified: 0.0–1.0 (softmax or hybrid)
            "bm25_score": float,
            "softmax_score": float,        # lexical search
            "bm25_rank": int | None,       # hybrid search
            "bm25_softmax_score": float | None,    # hybrid search
            "colbert_score": float | None, # hybrid search
            "colbert_rank": int | None,    # hybrid search
            "colbert_softmax_score": float | None, # hybrid search
            "hybrid_score": float | None,  # hybrid search
        }
    ],
    "total_retrieved": int,
    "cutoff_percentage": float,
    "settings": {
        "temperature": float,
        "ignore_zero": bool,
        "llm_tools_cutoff": float,
    },
    "search_mode": "lexical" | "hybrid",
}
```

## Search Tuning

The default final result limit is designed to keep the returned capability set small. Calling applications can override the limit when needed.

Common controls include:

- `top_k` / `max_tools`,
- temperature,
- lexical cutoff,
- BM25 weight,
- ColBERT weight,
- hybrid candidate limit,
- minimum hybrid score.

Retrieval tuning belongs to the Axiolex deployment. Consumers can use the deployment default without understanding the retrieval implementation.

### Temperature

- `0.1 - 0.5`: More focused and selective
- `0.5 - 1.5`: Balanced retrieval
- `1.5+`: Broader retrieval

Default: `0.5`. Tune based on your data and use case.

### Cutoff percentage

- `5 - 15%`: Typical range
- Lower values return more results
- Higher values return only stronger matches

Default: `10.0`. Tune based on your desired selectivity.

## Performance Notes

Approximate guidance from the current implementation:

- **Small collections (<100 capabilities):** sub-second indexing and near-instant lexical search.
- **Medium collections (100–1,000 capabilities):** indexing in the low seconds and typically sub-100 ms lexical search.
- **Larger collections (1,000+ capabilities):** indexing and query latency depend on catalog size, content length, and hybrid configuration.

BM25S and optional ColBERT indexes are held in process memory for query-time retrieval. Redis remains the shared source of catalog state.

## Demo Web UI

The GitHub repository includes a FastAPI-powered demo UI for testing retrieval behavior, inspecting ranked results, adding documents, and tuning search parameters.

It also acts as an interactive tuning environment. You can load your own YAML documents or tool definitions, inject additional documents or tools through the API, test retrieval parameters such as temperature, softmax cutoff thresholds, keywords, and content/tool descriptions, and iteratively refine routing behavior using the included UI.

![BM25S Retriever Web Interface](images/axiolex-interactive-ui.png)

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

The UI provides:

- **Discover dashboard** — test retrieval queries, inspect ranked results with rank + relevance score, and tune search parameters in real time. Namespace chip selector filters discovery to selected domains.
- **MCP provider management** — add, edit, enable, disable, and remove providers. Assign namespaces to providers via multi-select chips. Retrieve or delete cached tools per provider. API keys entered in masked fields with autocomplete disabled.
- **Namespace management** — create, edit, enable/disable, and delete namespaces from a dedicated tab. Changes propagate to the Discover chip selector and provider modal automatically.
- **Document management** — add and inspect YAML-loaded tool definitions and documents.

## Development

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

**What the compose setup provides:**

| Component | Details |
| --- | --- |
| Redis | `redis:7-alpine`, internal only, health-checked, data on named volume `redis-data` |
| Axiolex | Built from `Dockerfile`, depends on Redis health, port 9700 exposed |
| Audit logs | Persisted on volume `axiolex-logs` at `/app/logs` |
| ColBERT models | Persisted on volume `axiolex-models` at `/app/models` |
| Catalog YAML | Mounted read-only from `./source_files` — edit on host, restart to apply |
| Settings | Mounted read-only from `./settings.yaml` |
| Secrets | Passed via environment variables from `.env` — never baked into the image |
| Restart | Both services use `unless-stopped` |

**Enabling hybrid search in Docker:** Set `AXIOLEX_HYBRID_ENABLED=true` in `.env`. The Docker image includes the ColBERT extra. On first startup, the ColBERT model (~436MB) is downloaded into the `axiolex-models` volume. Subsequent startups use the cached model.

**Deploying the Axiolex container independently:** Docker Compose is just a convenient deployment package. The same Axiolex image can be deployed with an externally managed Redis:

```bash
docker build -t axiolex .
docker run -d -p 9700:9700 \
  -e AXIOLEX_REDIS_HOST=redis.example.com \
  -e AXIOLEX_REDIS_PORT=6379 \
  -v ./source_files:/app/source_files:ro \
  axiolex
```

### Where Redis can run

Redis is required for the shared MCP tool catalog, but it does not need to run in Docker or inside the Axiolex Python package.

| Usage | Redis required? | Where Redis can run |
| --- | --- | --- |
| Direct `BM25SRetriever` Python usage with local documents | No | Retrieval indexes remain in the Python process |
| REST/UI server (web management platform) | Yes | Local Redis, Docker Redis, remote Redis, or managed Redis |
| Axiolex MCP `axiolex_discover_tools` / `axiolex_execute_tool` server | Yes | Reachable private Redis instance |
| Installed PyPI package used as an indexer or MCP server | Yes | Redis is deployed separately from the package |

All Axiolex processes that share a catalog must use the same Redis host, port, and database:

```bash
export AXIOLEX_REDIS_HOST=localhost
export AXIOLEX_REDIS_PORT=6380
export AXIOLEX_REDIS_DB=0
```

Do not expose Redis publicly. External LLM clients connect to the Axiolex MCP endpoint and do not need Redis access.

## Reference Architecture

Axiolex is designed around a simple separation of responsibilities:

| Layer | Responsibility |
| --- | --- |
| Calling application / AI client | Understand the user request, select scope, decide which discovered capabilities to use |
| Axiolex | Maintain the capability catalog and retrieve/rank capabilities within the supplied scope |
| MCP provider / internal service | Expose the underlying business capability |
| Execution layer | Authenticate, authorize, validate, execute, and apply application-specific policy |
| LLM / agent | Reason over the request and the small set of capabilities supplied by the host |

This keeps enterprise capability discovery independent from domain-specific application reasoning and downstream execution.

## Documentation

- [Complete API Reference](https://vrraj.github.io/axiolex/api-reference.html)
- [Document and Tool Ingestion Guide](https://vrraj.github.io/axiolex/document-and-tool-ingestion-guide.html)
- [GitHub Repository](https://github.com/vrraj/axiolex)
- [PyPI Package](https://pypi.org/project/axiolex/)
- [Medium: Context Engineering for Tool-Heavy Agents](https://medium.com/@vr.rajkumar99/context-engineering-for-tool-heavy-agents-lexical-routing-c1b0ebad7495)

## Third-Party Model Notice

Optional hybrid retrieval downloads the pinned [`colbert-ir/colbertv2.0`](https://huggingface.co/colbert-ir/colbertv2.0) checkpoint through FastEmbed.

The model is not included in the repository or Axiolex package. Its model card declares the [MIT License](https://opensource.org/license/mit); see the [upstream model card](https://huggingface.co/colbert-ir/colbertv2.0) for the model and its current metadata.

## License

This project is licensed under the **GNU General Public License v3.0 (GPLv3)**.

- Feel free to clone, modify, run locally, and use it for personal, educational, or open-source projects.
- If you modify, bundle, or distribute `axiolex` code as part of a commercial application, GPLv3 requires you to open-source your entire application under the same license.

### Commercial Licensing

If you want to integrate Axiolex into a closed-source proprietary system, or require a custom enterprise domain setup, a commercial license is available.

Interested in a commercial license? Contact `ai0musings99@gmail.com`.
