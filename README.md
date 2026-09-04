# Axiolex

[![PyPI - Version](https://img.shields.io/pypi/v/axiolex?color=blue&logo=pypi&logoColor=white)](https://pypi.org/project/axiolex/)
[![GitHub Release](https://img.shields.io/github/v/release/vrraj/axiolex?label=github%20release&color=orange&logo=github)](https://github.com/vrraj/axiolex/releases)
![CI Status](https://github.com/vrraj/axiolex/actions/workflows/ci.yml/badge.svg)

**Centralized tool discovery and execution broker for enterprise AI applications**

Axiolex resolves MCP tools, A2A agent skills, and internal REST APIs into a single dynamic catalog—eliminating context window bloat for AI clients like **Claude, Cursor, and Enterprise Copilots**.

AI clients and applications such as Claude, Cursor, enterprise copilots, and internal agents can **discover and execute relevant tools** without pre-registering every provider, endpoint, or tool. The caller never needs to know whether a tool is backed by MCP, A2A, or an internal service — Axiolex resolves the transport, endpoint, and credentials server-side and returns a normalized result through a single `execute(tool_id, arguments)` contract.
>***As MCP servers, A2A agents, and tool definitions change, Axiolex keeps discovery current across consuming clients***.

For a user query or application-generated tool request, Axiolex resolves the intent within the applicable business scope and returns the **Top-K matching tools**, **ranked by relevance**. MCP tools and A2A agent skills are discovered and ranked together in a single catalog — the caller does not need to know which protocol a tool came from. A2A execution is synchronous: Axiolex sends the request, waits for the result within the configured timeout, and returns a normalized response. Long-running async task workflows are a future extension, not part of the current contract.

A **Python SDK** is shipped with this product (`pip install axiolex`) for Python applications that want programmatic access to discovery and execution. AI clients (Claude Desktop, Cursor, custom LLM agents) integrate through the **MCP interface** — Axiolex serves a single HTTP endpoint for both REST and MCP, with an optional ***npx proxy for stdio-only clients (https://www.npmjs.com/package/@axiolex/mcp-gateway)***. See [Consumption Model](#consumption-model) for the comparison.

To run Axiolex locally or deploy it as a shared service, see [Install and Quick Start](#install-and-quick-start).



## The Problem: Token Overhead, Tool Drift, and Governance

Connecting AI agents directly to raw enterprise tool inventories breaks down at scale:

- **Token overhead and direct API costs** — loading 50–200 static tool definitions into every prompt consumes **40,000–60,000 tokens** before the conversation starts. Anthropic documented a 58-tool setup consuming ~55,000 tokens upfront per request. [Source](https://www.anthropic.com/engineering/advanced-tool-use)
- **Degraded tool selection accuracy** — as tool inventories grow, competing tool descriptions and overlapping schemas increase tool-selection errors and hallucinations
- **Tool inventory drift and manual tool lifecycle management** — when enterprises add, swap, or update MCP tools, A2A agents, agent skills, or custom tools, every AI client (Claude Desktop, Cursor, enterprise copilots, and custom agents) must be reconfigured individually
- **Transport and security fragmentation** — managing connections across MCP stdio, Streamable HTTP, and A2A SendMessage requires protocol-specific handling in every client, leaving security teams with no central point for access control or audit logging

> Axiolex moves tool discovery into a **shared service**: query intent ranks tools, optional namespace scope limits eligibility, and clients receive only the Top-K matches. Provider and tool changes are **refreshed centrally**, so consuming applications query the current tool set instead of maintaining their own copies.



<p align="center">
  <img src="https://raw.githubusercontent.com/vrraj/axiolex/main/docs/images/axiolex_architecture.png" width="100%" />
</p>
<p align="center"><em>Axiolex architecture — shared discovery, routing, and execution layer across MCP tools, A2A endpoints, and internal services.</em></p>


# Core Capabilities

Axiolex provides a shared layer for discovering, ranking, and executing enterprise tools across applications and AI clients.

* **Managed shared tool catalog** — keeps MCP tools, A2A endpoints, internal services, and static tool definitions current as providers and tools are added, changed, renamed, or retired.
* **Intent-based discovery** — `axiolex_discover_tools()` returns the Top-K tools ranked by relevance to the query intent.
* **Optional namespace scoping** — limits discovery to one or more business domains when a narrower search boundary is useful.
* **Hybrid retrieval** — combines BM25S lexical retrieval with optional ColBERT semantic retrieval.
* **Execution-ready tool contracts** — returns `tool_id`, schemas, parameters, provider metadata, and runtime information required for orchestration or execution.
* **Stable tool execution** — `axiolex_execute_tool()` lets clients invoke discovered tools without managing downstream provider endpoints or transports directly. Supports MCP (Streamable HTTP, stdio) and A2A (Agent-to-Agent) providers.
* **Python SDK** — `pip install axiolex` provides a thin client for discovery and execution from Python applications without requiring Redis, ColBERT, or other server-side dependencies.
* **REST API** — exposes discovery, provider management, catalog operations, and execution over HTTP.
* **MCP interface** — Claude, Cursor, and other MCP-compatible clients can use Axiolex through stdio or Streamable HTTP.
* **A2A support** — Axiolex discovers skills from A2A agents via their agent card and executes them through the A2A `SendMessage` protocol.
* **Built-in provider adapters** — includes a lightweight Atlassian Jira adapter (`atlassian_rest_to_mcp`) that maps standard API token credentials directly to Jira's REST API using Basic auth — no OAuth or `cloudId` required. Works with any Atlassian Cloud plan, including Free.
* **Discovery audit trail** — records query intent, namespace scope, ranked results, scores, and latency for evaluation and troubleshooting.


## Axiolex Tool Catalog

Axiolex organizes tools, MCP services, A2A endpoints, and internal services by business domain so discovery can be scoped to the parts of the enterprise relevant to a user query or application request.

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

## How AI Clients and Applications Use Axiolex

Applications and AI clients use Axiolex to discover and invoke tools relevant to a user query or application-generated request.

For each discovery call, the caller provides the query intent and can optionally restrict the search to a single namespace or multiple namespaces. If no namespace is supplied, Axiolex searches the full catalog.

```text
User Request --> query intent + optional namespace scope --> axiolex_discover_tools() --> Top-K-tools ranked by relevance
```

The same core operations are available through MCP, the Python SDK, and REST.

**MCP**

- list_namespaces()
- axiolex_discover_tools(...)
- axiolex_execute_tool(...)

**Python SDK**

```python
results = client.discover(
    query="contract approval status",
    namespaces=["legal"],
    top_k=7,
)
```

**REST API**

```http
POST /discover
```

The access method changes; the underlying Axiolex catalog, namespace rules, retrieval, ranking, and execution services remain the same.

See [Consumption Model](#consumption-model) for the integration and deployment model.

Axiolex supports two common **integration patterns**.

### Purpose-Built Enterprise Applications

Applications that control their own orchestration can execute a discovered tool directly or use `axiolex_execute_tool()`.


### AI Clients and Agents

AI clients such as Claude, Cursor, enterprise copilots, and other agents can use Axiolex without loading or registering the full enterprise tool set in advance.

When namespace scoping is useful, they can obtain namespace names and descriptions through `list_namespaces()` and retain them in session context.

Discovered tools can be invoked through `axiolex_execute_tool()` when Axiolex provides the execution path.


**Full-catalog discovery.** Some clients or workflows may need to consider the full enterprise catalog.

```python
results = client.discover(
    query="analyze supplier lead-time risk for MICRON_HBM3E in Q4 2026",
    namespaces=["all"],
)
```


## Tool Execution

Axiolex can execute a discovered tool by `tool_id` without requiring the client to manage the provider endpoint or transport.

**MCP Example:**
```text
axiolex_execute_tool(tool_id, arguments)
```

Axiolex resolves the current provider and tool contract, validates the arguments, and invokes the underlying tool.

Execution supports three provider transports:

- **MCP Streamable HTTP** — remote MCP servers (e.g. Alpha Vantage, Tavily)
- **MCP stdio** — local subprocess MCP servers (e.g. Fetch, text utilities)
- **A2A** — Agent-to-Agent endpoints that expose skills via an agent card (e.g. Veris research agents)

**A2A Example:**
```python
# Discover A2A agent skills
tools = client.discover("financial research on Nvidia", namespaces=["veris.research"])

# Execute — the A2A adapter sends a SendMessage to the agent
result = client.execute(
    "veris_finance_a2a:financial_research",
    {"prompt": "What was Nvidia revenue in 2024?"}
)
```

Purpose-built applications can also execute discovered tools directly when they control their own orchestration.


## A2A (Agent-to-Agent) Provider Support

Axiolex supports A2A agents alongside MCP providers. A2A agents expose their capabilities as **skills** via an agent card, and Axiolex maps each skill to a tool in the unified catalog — ranked alongside MCP tools and internal services.

### How A2A works in Axiolex

**Discovery:** During index refresh, Axiolex fetches the agent card at `{endpoint}/.well-known/agent-card.json` and maps each skill to a catalog tool with a `prompt` input parameter.

**Execution:** When a caller executes an A2A tool, Axiolex sends a JSON-RPC 2.0 `SendMessage` request to the agent endpoint with the `A2A-Version: 1.0` header. The agent's response (task artifacts) is normalized into Axiolex's standard `{content: [], is_error: false}` response shape.

**Synchronous only:** A2A execution is synchronous. Axiolex sends the request, waits for the result within the configured execution timeout, and returns a normalized response. If the agent does not respond in time, Axiolex returns a standard `UPSTREAM_TIMEOUT` error. Long-running async task workflows (polling, task IDs, streaming) are a future extension.

### Provider configuration

```yaml
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

### MCP vs A2A

| Aspect | MCP | A2A |
|---|---|---|
| Discovery | `tools/list` over MCP session | GET agent card at `/.well-known/agent-card.json` |
| Tool unit | MCP tool with `inputSchema` | A2A skill with `id`, `name`, `description` |
| Execution | `tools/call` with structured arguments | `SendMessage` with text parts |
| Required header | `Mcp-Session-Id` | `A2A-Version: 1.0` |
| Session | Stateful (initialize handshake) | Stateless (no handshake) |
| Response | `CallToolResult` with `content[]` | `Task` with `artifacts[].parts[].text` |
| Arguments | Structured key-value matching schema | Natural-language `prompt` as text part |

The caller never sees these differences — they call `execute(tool_id, arguments)` and get back the same normalized response regardless of protocol.

### End-to-end example

```python
from axiolex import Axiolex

client = Axiolex("http://localhost:9700")

# Discover — A2A skills are ranked alongside MCP tools
tools = client.discover("financial research on Nvidia", top_k=5)

# Execute — Axiolex sends SendMessage to the A2A agent
result = client.execute(
    "veris_finance_a2a:financial_research",
    {"prompt": "What was Nvidia revenue in 2024?"}
)

# Result is the same normalized shape as an MCP tool result
for item in result["result"]["content"]:
    print(item["text"])
```

For full A2A architecture details, see [docs/architecture.md](docs/architecture.md) and [docs/api-reference.md](docs/api-reference.md).


## Namespace Model

Namespaces organize tools by business area and define which tools are eligible for discovery when a scope is supplied.

| Namespace | Capability area |
| --- | --- |
| `finance` | Financial planning, forecasting, reporting, revenue, costs, and related finance capabilities |
| `legal` | Contracts, agreements, legal review, and related legal capabilities |
| `sales` | Opportunities, accounts, pipeline, and related sales capabilities |
| `hr.recruiting` | Recruiting, open roles, candidates, requisitions, and hiring workflows |
| `hr.employee_services` | Benefits, insurance, leave, compensation, payroll, and employee support |
| `supply_chain` | Suppliers, procurement, inventory, logistics, and related supply-chain capabilities |

**A tool can belong to multiple namespaces**. When scope is supplied, Axiolex searches only those namespaces; unknown namespaces fail explicitly. Namespace names and descriptions are available through list_namespaces().

### Discovery and Orchestration

Axiolex narrows the tool catalog in two steps: **namespace scope defines which tools are eligible, and query intent determines which of those tools rank highest.**

```text
User request
    ↓
query intent + optional namespace scope
    ↓
eligible tool set
    ↓
BM25S + optional ColBERT
    ↓
ranked Top-K tools
    ↓
application / AI client
```

For multiple namespaces, Axiolex searches their union. With `all`, the full catalog is eligible. `top_k` controls the maximum number of tools returned.

The calling application, LLM, or orchestrator decides which returned tools are used, added to model context, or executed.

For multi-domain or multi-step requests, the caller can decompose the request into focused discovery queries and search the appropriate namespace for each step.

For a query that spans multiple domains like "Show me open orders from Acme for HBM3E memory
and check whether Acme is covered under a current NDA", **the caller can decompose it into two focused queries**:

```text
"Show me open orders from Acme for HBM3E memory
and check whether Acme is covered under a current NDA."
                    ↓
            LLM / orchestrator
                    ↓
"Find open Acme orders for HBM3E memory"
    → sales
    → axiolex_discover_tools(...)

"Check current NDA coverage for Acme"
    → legal
    → axiolex_discover_tools(...)
```

**Conversational requests can also be expanded into more retrieval-specific intent** before discovery. **Axiolex itself does not rewrite, decompose, or orchestrate the request**; it ranks tools against the query and optional namespace scope it receives.

**Execution sequencing also remains with the caller**, including workflows that require `discover → execute → discover`.



## Consumption Model

Applications and AI clients access Axiolex through three integration surfaces. All hit the same backend — same Redis catalog, same retrieval engine, same execution dispatcher. They are different front doors, not different systems.

| Surface | Best for | How it works |
|---|---|---|
| **Python SDK** (`axiolex.sdk.Axiolex`) | Python applications | `pip install axiolex`, instantiate `Axiolex(base_url=...)`, call `.discover()` / `.execute()` directly in code |
| **REST API** (FastAPI server) | Non-Python applications, curl, Postman, any HTTP client | `POST /discover`, `POST /execute`, `GET /namespaces` over HTTP to the Axiolex server |
| **MCP server** (`axiolex.mcp.server`) | AI clients (Claude Desktop, Cursor, custom LLM agents) that speak MCP | Client connects via stdio or streamable-HTTP, gets `axiolex_discover_tools` and `axiolex_execute_tool` as native MCP tools the LLM can call |

```text
External Python app  ──►  SDK   ──┐
                                  │
Any HTTP client       ──►  REST  ──┼──►  FastAPI server (9700)  ──►  Retrieval + Execution
                                  │         └── /mcp  ──►  MCP streamable-http
AI client / LLM       ──►  MCP   ──┘
```

All three surfaces expose the same core operations — only the naming differs:

| Capability | Python SDK | REST endpoint | MCP tool |
|---|---|---|---|
| List namespaces | `client.list_namespaces()` | `GET /namespaces` | `list_namespaces()` |
| Discover tools | `client.discover(...)` | `POST /discover` | `axiolex_discover_tools(...)` |
| Execute tool | `client.execute(...)` | `POST /execute` | `axiolex_execute_tool(...)` |

The `axiolex_` prefix on MCP tool names namespaces them so an AI client connected to multiple MCP servers can distinguish Axiolex's tools from others. The Python SDK and REST API don't need the prefix — the SDK is scoped to the `Axiolex` client object, and REST endpoints are scoped to the Axiolex server URL.

### When to use each surface

| Surface | Use when | Example |
|---|---|---|
| **Python SDK** | The app is Python and wants programmatic control. You are building orchestration logic, batch workflows, or custom ranking pipelines. You need lower-level params (`bm25_weight`, `candidate_limit`, `namespaces`) that an LLM would not naturally pass. You want synchronous request/response without an MCP client library. | `client.discover("get stock earnings", top_k=5, namespaces=["finance"])` |
| **REST API** | The consumer is non-Python (Go, Java, JS, curl, Postman). You want a language-agnostic HTTP interface. You need to integrate Axiolex into an existing HTTP-based service mesh. | `POST /discover {"query": "...", "namespaces": ["finance"]}` |
| **MCP server** | The consumer is an AI client or agent that already supports MCP. The LLM should discover tools and determine which tool to invoke. You are integrating with Claude, Cursor, or another MCP-compatible client. | `"axiolex": { "url": "http://localhost:9700/mcp" }` |

**Python SDK:**

```python
from axiolex import Axiolex

client = Axiolex("http://axiolex-host:9700")
tools = client.discover("get stock earnings", top_k=5, namespaces=["finance"])
result = client.execute(tools["tools"][0]["tool_id"], {"symbol": "AAPL"})
```

The base PyPI package is a thin HTTP client (httpx + pydantic only). Applications do not connect directly to Redis, build indexes, load ColBERT, or discover MCP providers themselves.

**MCP server:**

```json
// Claude Desktop / Cursor config (streamable HTTP)
"axiolex": { "url": "http://localhost:9700/mcp" }
```

Claude Desktop, Cursor, and other AI clients that use stdio transport connect via the [`@axiolex/mcp-gateway`](https://www.npmjs.com/package/@axiolex/mcp-gateway) npx proxy, which bridges stdio to the Axiolex HTTP endpoint. In enterprise environments where installing the full Python stdio server on each desktop is not a deployment option, the proxy is the standard connection method — it requires only Node.js (no Python, no Redis, no ML libraries) and can be audited by IT in minutes:

```json
// Claude Desktop / Cursor config (stdio via npx proxy)
"axiolex": {
  "command": "npx",
  "args": ["-y", "@axiolex/mcp-gateway", "--endpoint", "http://localhost:9700/mcp"]
}
```

The AI client sees `axiolex_discover_tools` and `axiolex_execute_tool` as callable tools. It does not need to maintain the downstream MCP provider and tool inventory itself.

### Operator and Administration Interfaces

Provider registration, provider refresh, namespace management, and secret management are operator functions rather than application-consumption functions.

These operations are available through:

- the admin REST API;
- the Axiolex Web UI;
- the axiolex-index CLI.

The Python SDK remains focused on application-side discovery and execution.

### What is not in the SDK

Registry management — adding/removing providers (MCP and A2A), refreshing the index, namespace CRUD, secret management — is an operator concern, not an application-consumption concern. Those operations are exposed through the admin REST surface (`/mcp-providers`, `/namespaces`, `/mcp-providers/{id}/secret`), the Web UI, and the `axiolex-index` CLI.

## Provider and Catalog Management

Axiolex keeps the shared capability catalog current as providers and tools change.

- **Provider management** — add, edit, enable, disable, or remove MCP and A2A providers.
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
query intent --> eligible tools --> BM25S + optional ColBERT --> ranked Top-K tools
```

> **Retrieval mode and ranking weights** are deployment settings; consuming applications do not need to manage the underlying search implementation. For tuning details (temperature, cutoff, hybrid weights, ColBERT model configuration), see the [Application Reference](docs/app_reference.md).

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
        (Streamable HTTP for remote MCP providers,
         stdio for local subprocess MCP providers,
         A2A for Agent-to-Agent endpoints)
        │
        ▼
  normalize result into response contract
```

Every call is fully self-contained — the dispatcher does not assume `axiolex_discover_tools` was called in the same session. `tool_id` is re-resolved fresh from the catalog on every call.

### Idempotency

The `idempotency_key` field is accepted and logged to the execution audit log, but **de-duplication is not enforced in Phase 1**. The field exists in the contract so callers can start sending it immediately without a schema change later. When the idempotency store is wired in, the dispatcher will short-circuit repeat calls with the same key within a bounded window (recommended: 24h) and return the original result rather than re-executing.

The downstream MCP providers do not see or participate in idempotency — it is an Axiolex-side concern. The MCP protocol's `tools/call` method takes only `name` and `arguments`; the dispatcher decides whether to send the call or return a cached result.

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

### Install the Python SDK

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

### Run locally

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

### Connect AI clients (Claude Desktop, Cursor, Codex)

Axiolex serves MCP at `http://localhost:9700/mcp` over streamable HTTP. Clients that support HTTP directly just need the URL. Clients that use stdio transport connect via the [`@axiolex/mcp-gateway`](https://www.npmjs.com/package/@axiolex/mcp-gateway) npx proxy — no Python on the client, only Node.js.

The MCP endpoint URL and the npx proxy command are the same across all clients — only the config file location and format differ. The examples below are current as of early 2026; refer to each client's MCP documentation for any changes:

- [Claude Desktop MCP docs](https://modelcontextprotocol.io/quickstart/user)
- [Cursor MCP docs](https://cursor.com/docs/mcp)
- [Codex MCP docs](https://learn.chatgpt.com/docs/extend/mcp)

**Streamable HTTP** (preferred — no proxy needed):

Claude Desktop and Cursor (`~/Library/Application Support/Claude/claude_desktop_config.json` or `~/.cursor/mcp.json` — JSON format):

```json
{
  "mcpServers": {
    "axiolex": { "url": "http://localhost:9700/mcp" }
  }
}
```

Codex (`~/.codex/config.toml` — TOML format, shared across ChatGPT desktop, CLI, and IDE extension):

```toml
[mcp_servers.axiolex]
url = "http://localhost:9700/mcp"
enabled = true
```

Or via Codex CLI: `codex mcp add axiolex --url http://localhost:9700/mcp`

**Stdio via npx proxy** (for clients that require stdio transport):

Claude Desktop and Cursor (JSON). Use the absolute path to `npx` (`which npx`) to avoid PATH resolution issues — Claude Desktop uses a restricted system PATH that may not include nvm/volta paths:

```json
{
  "mcpServers": {
    "axiolex": {
      "command": "/absolute/path/to/npx",
      "args": ["-y", "@axiolex/mcp-gateway", "--endpoint", "http://localhost:9700/mcp"]
    }
  }
}
```

Codex (TOML):

```toml
[mcp_servers.axiolex]
command = "npx"
args = ["-y", "@axiolex/mcp-gateway", "--endpoint", "http://localhost:9700/mcp"]
enabled = true
```

See [Connect Claude Desktop](docs/claude-mcp.md) for a full walkthrough including enterprise deployment.

### @axiolex/mcp-gateway (npm package)

The stdio proxy is published as [`@axiolex/mcp-gateway`](https://www.npmjs.com/package/@axiolex/mcp-gateway) on npm. It is a ~120-line Node.js package with one dependency (`@modelcontextprotocol/sdk`) — no Python, no Redis, no ML libraries. Source is in [`mcp-gateway/`](mcp-gateway/) in this repo.

**For end users:** no install needed — `npx -y @axiolex/mcp-gateway` fetches and caches it automatically.

**For developers working on the proxy itself:**

```bash
cd mcp-gateway
npm install          # install dependencies
node index.js --endpoint http://localhost:9700/mcp   # run locally
npm publish --access public   # publish new version (requires npm login)
```

The proxy version is independent of the Axiolex Python package version. Bump `mcp-gateway/package.json` and publish to npm when the proxy changes.

### Axiolex MCP Tools

Axiolex exposes three MCP tools to AI clients. These are the only tools Claude, Cursor, or Codex see — downstream provider tools (Jira, Alpha Vantage, Tavily, etc.) are discovered and executed through Axiolex, not exposed directly.

| Tool | Purpose |
| --- | --- |
| `list_namespaces` | List all enabled tool domains (e.g. `finance.market_data`, `research.web`) |
| `axiolex_discover_tools` | Find tools relevant to a natural-language request, optionally filtered by namespace |
| `axiolex_execute_tool` | Execute a discovered tool by its `tool_id` with validated arguments |

**How AI clients use them:**

1. Call `list_namespaces` early in the session to learn what tool domains Axiolex covers. Keep the result in memory.
2. When a user request comes in, call `axiolex_discover_tools` with the query. Optionally pass one or more namespace IDs to filter results to a relevant domain.
3. Call `axiolex_execute_tool` with the `tool_id` returned by discovery and the arguments matching the tool's input schema.

**Where tool descriptions are defined:**

Each tool's description is split into two parts in `axiolex/mcp/server.py`:

- **Contract** (`_*_CONTRACT` variables) — describes what the tool does. Part of the MCP contract; **do not change**.
- **Behavior** (`_*_BEHAVIOR` variables) — tells the AI client how to present results to the user (e.g. "list the tool names you found at the end of your response"). Freely editable.

The final description sent to the client is: `description = CONTRACT + " " + BEHAVIOR`

To change the behavioral wording, edit the `_BEHAVIOR` variables in `axiolex/mcp/server.py`, then restart the server:

```bash
make stop && make start
```

> **ColBERT / hybrid search is optional at install time.** `make install` gives you a fully working app with BM25 lexical search. Run `make colbert` to add the ColBERT extra (`fastembed`, `huggingface-hub`, `onnxruntime`) upfront, then set `AXIOLEX_HYBRID_ENABLED=true` in `.env` to enable semantic/hybrid ranking. If you skip `make colbert`, `make start` will still install the colbert packages on first launch (via `uv run --extra colbert`) — this adds a one-time download delay. If you edit `pyproject.toml` to add a base dependency, re-run `make install` (or `make colbert` if you had colbert installed) rather than a bare `uv sync`, since `uv sync` reconciles the `.venv` to exactly what is requested and will prune the colbert packages if `--extra colbert` is not included.

### Common Makefile targets

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

### Deployment

Axiolex runs as a shared FastAPI service with Redis-backed catalog state.

Typical deployment components are:

- **Axiolex server** — REST and MCP interfaces.
- **Redis** — shared capability catalog and runtime metadata.
- **Registered providers** — MCP (Streamable HTTP, stdio) and A2A agents.
- **Optional ColBERT runtime** — for hybrid semantic retrieval.

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

## Security Overview

Axiolex has two separate security boundaries: **clients accessing Axiolex** and **Axiolex accessing downstream providers**.

### Client Authentication and Authorization

The current Axiolex implementation assumes a trusted deployment environment.

For a centrally deployed enterprise service, requests to the REST API, MCP interface, Python SDK endpoints, and Web UI should be authenticated before discovery, management, or execution.

Standard enterprise mechanisms can be added at the Axiolex service boundary, including OAuth/OIDC, machine-to-machine credentials, signed JWTs, mTLS, or API keys.

Fine-grained user- and client-level authorization is not implemented in the current phase.

### Downstream Provider Authentication

Axiolex connects to registered providers through **MCP** (Streamable HTTP or stdio) and **A2A** (Agent-to-Agent).

Provider configuration is stored in:

```text
source_files/mcp_providers.yaml
```

Provider credentials remain server-side and are not exposed to consuming applications or AI clients.

Secrets can be supplied through:

1. **Environment variables** referenced by `auth.secret_env`.
2. **Encrypted secret store** managed through the Web UI:

```text
source_files/mcp_secrets.enc
```

Secrets stored in `mcp_secrets.enc` are encrypted with **AES-256-GCM**. The encryption master key is supplied separately through:

```text
AXIOLEX_SECRET_MASTER_KEY
```

Secret resolution uses the environment variable first and the encrypted secret store second.

#### Basic auth (username + token)

Some providers (e.g. **Jira**) require HTTP Basic authentication with an email and an API token. The email is a non-secret account identifier stored in the provider YAML; the token is a secret stored in the encrypted secret store. Axiolex passes both to the provider's stdio subprocess as environment variables at runtime.

```yaml
# source_files/mcp_providers.yaml
- id: jira
  name: Jira
  transport: stdio
  command: python
  args: [stdio_servers/jira/atlassian_rest_to_mcp.py]
  auth:
    type: basic
    username: your-email@domain.com    # non-secret, stored in YAML
    secret_env: JIRA_API_TOKEN         # token resolved from encrypted store or env var
  namespaces: [enterprise.project_management]
```

The subprocess receives `JIRA_API_TOKEN` (the resolved token) and `JIRA_API_TOKEN_USERNAME` (the email). Neither value is written to logs or returned to consuming applications.

#### Atlassian Jira adapter (`atlassian_rest_to_mcp`)

The `transport` field describes how Axiolex communicates with the provider, not how the provider talks to its downstream service:

```text
Axiolex ──[stdio, MCP protocol]──► atlassian_rest_to_mcp.py ──[HTTPS, REST API]──► atlassian.net
```

The Jira integration uses a lightweight MCP adapter (`stdio_servers/jira/atlassian_rest_to_mcp.py`) that maps standard Atlassian API token credentials directly to Jira's classic REST API endpoints (e.g. `https://your-site.atlassian.net`). It does not require a `cloudId` or OAuth scopes because it handles the API calls directly using Basic auth credentials (email + API token). The adapter exposes two tools:

- `search_tickets` — search issues using JQL
- `create_ticket` — create a new issue with project, type, title, and description

Atlassian also offers an official cloud-hosted MCP server (Atlassian Rovo MCP at `https://mcp.atlassian.com/v2/mcp`) that covers Jira, Confluence, Bitbucket, Jira Service Management, and Loom. That endpoint requires OAuth 2.1 authorization with scoped tokens — a standard API token alone authenticates the connection but cannot execute tools. Support for the official Rovo MCP endpoint via OAuth 2.1 is a future enhancement. The current `atlassian_rest_to_mcp` adapter works with any Atlassian Cloud plan, including Free, using only an API token.

#### Enterprise deployment model

Axiolex is configured with **service-account credentials** for each downstream provider. In a centralized deployment, Axiolex runs as a shared server and holds one service-account credential per provider (e.g. one Jira email + API token). All employee clients — Claude, Cursor, custom apps — connect to Axiolex and execute tools through it. Employees never need downstream provider credentials on their laptops; their client config contains only the Axiolex URL.

This model can be **extended to per-user credentials** in a future phase, where Axiolex maps the authenticated employee to their own downstream provider credentials instead of using the shared service account.

| Concern | Current phase (service accounts) | Future (per-user credentials) |
|---------|----------------------------------|-------------------------------|
| Who holds provider credentials | Axiolex server (encrypted store, one service account per provider) | Axiolex server (per-user credential mapping or OAuth token exchange) |
| Employee client config | Axiolex URL only | Same |
| Employee / user authentication | At Axiolex service boundary (OAuth/OIDC, mTLS, API keys) | Same — Axiolex authenticates the user, then delegates to their downstream credentials |
| Ticket created as | Service account | Individual employee |
| Per-user provider permissions | Not enforced — service account has broad access | Enforced — operations run as the authenticated user |
| Audit trail in downstream systems | Shows service account | Shows individual employee |

The current phase uses service accounts and is designed for trusted environments. Per-user credential delegation is an architectural extension point, not a redesign — the execution contract (`axiolex_execute_tool`) and credential resolution layer (`resolve_secret` + `build_stdio_env`) are structured to accept a user context without changing the caller-facing API.

### Secret Handling

* `mcp_providers.yaml` stores secret references, not secret values.
* `mcp_secrets.enc` is git-ignored and stores encrypted provider secrets.
* REST responses and Redis runtime metadata do not expose provider secret values.
* Inline `secret_value`, credentials embedded in URLs, and credentials supplied directly in provider headers are rejected.
* Sensitive query parameters are redacted before outbound URLs are written to logs.

The encryption master key remains an operator-managed deployment secret and is not stored in the provider registry or encrypted secret store.

For provider configuration fields, YAML examples, encrypted secret store setup, and detailed security properties, see the [Technical Architecture](docs/architecture.md).



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
| `GET` | `/mcp-providers` | List providers (MCP and A2A) |
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

## Development

For local development setup, see [Install and Quick Start](#install-and-quick-start).

For details on MCP tool descriptions and how to customize AI client behavior, see [Axiolex MCP Tools](#axiolex-mcp-tools).

Additional Docker targets:

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

Axiolex is available under the [GNU GPLv3](LICENSE).

Feel free to clone, explore, modify, and build with Axiolex under the
terms of GPLv3.

Commercial licensing is also available for organizations interested in
incorporating Axiolex into proprietary products or custom solutions.

ai-musings99@gmail.com
