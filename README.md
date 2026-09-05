# Axiolex

[![PyPI - Version](https://img.shields.io/pypi/v/axiolex?color=blue&logo=pypi&logoColor=white)](https://pypi.org/project/axiolex/)
[![GitHub Release](https://img.shields.io/github/v/release/vrraj/axiolex?label=github%20release&color=orange&logo=github)](https://github.com/vrraj/axiolex/releases)
![CI Status](https://github.com/vrraj/axiolex/actions/workflows/ci.yml/badge.svg)

> **Centralized tool discovery and execution gateway for AI clients, coding tools, enterprise applications, copilots, and agents.**

Axiolex connects **MCP tools, A2A agent skills, REST APIs, and internal enterprise services** through a shared catalog and execution layer. **Claude Desktop, Cursor, Codex, Microsoft Copilot, enterprise applications, and custom agents** can access relevant capabilities without configuring every downstream provider, endpoint, or credential directly.

* **Unified Tool Catalog:** index MCP tools, A2A agent skills, REST APIs, and internal services in one searchable catalog.
* **Intent-Driven Discovery:** rank the Top-K relevant tools using BM25S and optional ColBERT, with namespace-based business-domain scoping.
* **Normalized Execution:** use one `execute(tool_id, arguments)` contract while Axiolex handles transport, endpoint resolution, authentication, and response normalization.
* **Enterprise Provider Integration:** connect MCP servers and A2A agents directly ; for REST-based providers integrate thru MCP adapters (included example: `atlassian_rest_to_mcp` Jira adapter)
* **Flexible Access:** Python SDK (`pip install axiolex`), REST API, and MCP access — including the stdio **MCP gateway proxy** via `npx` ([`@axiolex/mcp-gateway`](https://www.npmjs.com/package/@axiolex/mcp-gateway)) for Claude Desktop and Cursor integration.
* **Management Dashboard:** configure providers, namespaces, credentials, retrieval settings, and test discovery and execution from the web UI.

## Why Axiolex?

As tool catalogs grow, loading every tool definition into every AI client becomes expensive and difficult to manage.

Anthropic documented a five-server setup with **58 tools consuming ~55K tokens before the conversation starts**, with **Jira alone accounting for ~17K tokens** in that example. [Anthropic: Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)

Whether for a **power user connecting multiple MCP servers** or an **enterprise team exposing internal tools and services to AI agents and applications**, Axiolex provides:

* **Relevant tools only:** a small ranked Top-K set instead of the full catalog.
* **Focused tool selection:** fewer competing capabilities for the LLM to evaluate.
* **Centralized integration:** connect providers once rather than maintaining them across individual clients and applications.
* **Governed execution:** normalize stdio, HTTP, A2A, and REST behind one gateway with server-side authentication and audit logging.

```text
User Request
     ↓
Intent + Optional Namespace (e.g., `hr`, `legal`, `sales`)
     ↓
Axiolex Discovery (`axiolex discover_tools`)
     ↓
Top-K Relevant Tools
     ↓
Client / LLM Selects
     ↓
Axiolex Execute (`axiolex execute_tool`)
     ↓
MCP / A2A / REST Provider
```


## Axiolex Tool Catalog

Axiolex organizes tools, MCP services, A2A endpoints, and internal services by business domain so discovery can be scoped to the parts of the enterprise relevant to a user query or application request.

| User query | Search scope |
| --- | --- |
| "Show which business units have the largest variance between forecast and actual revenue." | Finance |
| "Check whether the Acme Inc NDA covers product evaluation." | Legal |
| "What health insurance options are available for dependents?" | HR Employee Services |
| "Explain what is driving the predicted supplier lead time up for `SAMSUNG_HBM3e_LINES`." | Supply Chain |
| "Which deals expected to close this quarter are still waiting for contract approval?" | Sales + Legal |

A calling application or AI client can use **single-scope discovery**, **multi-scope discovery**, or **full-catalog discovery**, depending on the request.

> Axiolex represents these search scopes as **namespaces**, such as `finance`, `legal`, `sales`, `hr.recruiting`, `hr.employee_services`, and `supply_chain`. A request can search one namespace, multiple namespaces, or the full catalog


## How AI Clients and Applications Use Axiolex

Applications and AI clients discover and execute tools dynamically using query intent and optional namespace scoping.

```text
User Request --> Query Intent + Optional Scope --> axiolex_discover_tools() --> Top-K Relevant Tools
```

### Access surfaces

The same Axiolex catalog, discovery engine, and execution layer are available through:

* **MCP tools:** `list_namespaces()`, `axiolex_discover_tools()`, `axiolex_execute_tool()`
* **REST API:** `POST /discover`, `POST /execute`
* **Python SDK:**

```python
results = client.discover(
    query="contract approval status",
    namespaces=["legal"],
    top_k=7,
)
```

### Integration patterns

**Enterprise applications:** custom applications can control their own orchestration and use Axiolex for discovery and execution.

**AI clients and agents:** Claude Desktop, Cursor, Codex, copilots, and custom agents can discover and execute tools without loading the full enterprise tool inventory into the client.

**Full-catalog discovery:** when a workflow needs to search across all available domains, omit the namespace filter.

```python
results = client.discover(
    query="analyze supplier lead-time risk for MICRON_HBM3E in Q4 2026",
)
```

### Retrieval guidance

**Multi-domain scoping:** search multiple namespaces when one request spans related business areas.

```python
results = client.discover(
    query="deals waiting for contract approval",
    namespaces=["sales", "legal"],
)
```

**Compound requests:** when a prompt contains distinct tasks, the calling LLM or application can decompose it into focused discovery queries.

```text
"Show open HR roles and summarize Q3 revenue variance"
       ├──> discover("open engineering roles", namespaces=["hr"])
       └──> discover("Q3 revenue variance", namespaces=["finance"])
```

**Query expansion:** conversational requests can be translated into more retrieval-specific intent before discovery.

```text
"How is Apple doing lately?"
       ↓
"Apple AAPL recent stock price performance and market data"
       ↓
axiolex_discover_tools(...)
```

Axiolex ranks the query it receives; it does not rewrite, expand, decompose, or orchestrate the request. Execution sequencing also remains with the caller, including workflows such as `discover → execute → discover`.

For details on catalog synchronization, `tools/list_changed`, and discovery evaluation, see the [Technical Architecture](docs/architecture.md).


## Unified Tool Execution: One Contract, Any Transport

Axiolex executes discovered tools through a single contract:

```text
execute(tool_id, arguments)
```

The caller does not manage downstream endpoints, authentication, or transport mechanics. Axiolex resolves them server-side and returns a normalized response shape:

```json
{ "content": [], "is_error": false }
```

Axiolex currently supports **MCP Streamable HTTP, MCP stdio, and A2A** directly. REST-only enterprise systems can participate through adapters that expose them through a supported execution path.

### Protocol and provider normalization

| Aspect | MCP Streamable HTTP | MCP stdio | A2A |
| --- | --- | --- | --- |
| Discovery | `tools/list` over MCP session | `tools/list` over subprocess stdio | GET `/.well-known/agent-card.json` |
| Catalog unit | MCP tool with `inputSchema` | MCP tool with `inputSchema` | A2A skill mapped to tool with `prompt` input |
| Execution | `tools/call` over HTTP/SSE | `tools/call` over stdio pipes | JSON-RPC 2.0 `SendMessage` |
| Required header | `Mcp-Session-Id` | — | `A2A-Version: 1.0` |
| Session | Stateful | Stateful | Stateless |
| Response | `CallToolResult` with `content[]` | `CallToolResult` with `content[]` | `Task` with `artifacts[].parts[].text` |
| Arguments | Structured key-value matching schema | Structured key-value matching schema | Natural-language `prompt` as text part |
| Execution mode | Synchronous | Synchronous | Synchronous within `UPSTREAM_TIMEOUT` |

The caller sees the same Axiolex execution contract regardless of the underlying protocol.

### Provider configuration examples

Configure remote MCP servers, A2A agents, and local stdio MCP servers in `source_files/mcp_providers.yaml`:

```yaml
# 1. Remote MCP server
- id: tavily_mcp
  name: Tavily
  transport: streamable-http
  endpoint: https://mcp.tavily.com/mcp
  auth:
    type: api_key
    key_param: tavilyApiKey
    secret_env: TAVILY_API_KEY
  enabled: true
  namespaces: ["research.web"]

# 2. A2A agent
- id: veris_finance_a2a
  name: Veris Finance Research
  transport: a2a
  endpoint: http://localhost:8100/agents/veris-finance-research-agent/
  auth:
    type: none
  enabled: true
  namespaces: ["veris.research"]

# 3. REST-only enterprise system via stdio MCP adapter
- id: jira
  name: Jira
  transport: stdio
  command: python
  args: ["stdio_servers/jira/atlassian_rest_to_mcp.py"]
  auth:
    type: basic
    key_param: api_key
    secret_env: JIRA_API_TOKEN
    username: ${JIRA_USERNAME}
  enabled: true
  namespaces: ["product_management"]
```

The Jira example uses the **`atlassian_rest_to_mcp` adapter** to expose a REST-only enterprise system through the same Axiolex discovery and execution path. The same adapter pattern can be used for other REST-based systems.

### End-to-end example

```python
from axiolex import Axiolex

client = Axiolex("http://localhost:9700")

# Discover
tools = client.discover("financial research on Nvidia", top_k=5)

# Execute
result = client.execute(
    "veris_finance_a2a:financial_research",
    {"prompt": "What was Nvidia revenue in 2024?"}
)

for item in result["result"]["content"]:
    print(item["text"])
```

A2A execution is currently synchronous: Axiolex sends the request, waits within the configured timeout, and returns a normalized response. Long-running asynchronous task workflows are a future extension.

For full architecture details, see [docs/architecture.md](docs/architecture.md) and [docs/api-reference.md](docs/api-reference.md).


## Integration Surfaces & Client Access

Applications and AI clients access Axiolex through three front-door surfaces. All three use the same catalog, discovery engine, and execution layer.

```text
Python application  ──►  Python SDK  ──┐
                                       │
HTTP application    ──►  REST API   ──┼──►  Axiolex Server  ──►  Catalog, Discovery & Execution
                                       │
AI client / agent   ──►  MCP Server ──┘
```

### Access options

| Capability | Python SDK | REST API | MCP Interface |
| --- | --- | --- | --- |
| List namespaces | `client.list_namespaces()` | `GET /namespaces` | `list_namespaces()` |
| Discover tools | `client.discover(...)` | `POST /discover` | `axiolex_discover_tools(...)` |
| Execute tool | `client.execute(...)` | `POST /execute` | `axiolex_execute_tool(...)` |

### Python SDK

For Python applications, orchestration pipelines, and batch workflows.

```python
from axiolex import Axiolex

client = Axiolex("http://localhost:9700")

tools = client.discover(
    "get stock earnings",
    namespaces=["finance"],
    top_k=5,
)

result = client.execute(
    tools["tools"][0]["tool_id"],
    {"symbol": "AAPL"},
)
```

The PyPI package is a thin HTTP client — no Redis, ColBERT, or server-side ML dependencies are required on the client.

### REST API

Language-agnostic access for enterprise applications, microservices, and non-Python clients.

```bash
curl -X POST http://localhost:9700/discover \
  -H "Content-Type: application/json" \
  -d '{"query": "contract approval status", "namespaces": ["legal"]}'
```

### MCP interface

Claude Desktop, Cursor, Codex, and compatible AI clients can connect directly to Axiolex through MCP.

**Streamable HTTP:**

```json
{
  "mcpServers": {
    "axiolex": {
      "url": "http://localhost:9700/mcp"
    }
  }
}
```

For clients requiring stdio, use the **`@axiolex/mcp-gateway`** proxy:

```json
{
  "mcpServers": {
    "axiolex": {
      "command": "npx",
      "args": [
        "-y",
        "@axiolex/mcp-gateway",
        "--endpoint",
        "http://localhost:9700/mcp"
      ]
    }
  }
}
```

The proxy is available through `npx` and requires no local Axiolex Python installation.

### Control plane boundary

Provider registration, namespace management, index refreshes, and credential configuration are administrative functions managed through the **Axiolex Web UI, REST administration endpoints, or CLI** rather than client-facing discovery and execution interfaces.


## Namespace Model

Namespaces organize tools by business domain and define which capabilities are eligible for discovery when a scope is supplied.

| Namespace | Capability area |
| --- | --- |
| `finance` | Financial planning, forecasting, reporting, revenue, costs, and related finance capabilities |
| `legal` | Contracts, agreements, legal review, and related legal capabilities |
| `sales` | Opportunities, accounts, pipeline, and related sales capabilities |
| `hr.recruiting` | Recruiting, open roles, candidates, requisitions, and hiring workflows |
| `hr.employee_services` | Benefits, insurance, leave, compensation, payroll, and employee support |
| `supply_chain` | Suppliers, procurement, inventory, logistics, and related supply-chain capabilities |

A tool can belong to **multiple namespaces**. A request can search one namespace, multiple namespaces, or the full catalog. When namespaces are supplied, they form a hard discovery boundary; only tools within those scopes are eligible for ranking.

```text
User Request
     ↓
Query Intent + Optional Namespace Scope
     ↓
Eligible Tool Set
     ↓
BM25S + Optional ColBERT
     ↓
Ranked Top-K Tools
     ↓
Application / AI Client
```

The calling application, LLM, or orchestrator decides which returned tools are added to model context or executed.

### Multi-domain and multi-step requests

For a request spanning multiple domains, the caller can either search multiple namespaces together or decompose the request into focused discovery calls.

```text
"Show open orders from Acme for HBM3E memory
and check whether Acme is covered under a current NDA."
                    ↓
            LLM / Orchestrator
                    ↓
"Find open Acme orders for HBM3E memory"
    → sales
    → axiolex_discover_tools(...)

"Check current NDA coverage for Acme"
    → legal
    → axiolex_discover_tools(...)
```

Conversational requests can also be expanded into more retrieval-specific intent before discovery.

**Axiolex does not rewrite, decompose, or orchestrate the request itself.** It ranks tools against the query and namespace scope it receives. Execution sequencing also remains with the caller, including workflows such as `discover → execute → discover`.


## Retrieval Engine & Schema Contracts

Axiolex ranks tools within the eligible namespace scope using **BM25S lexical retrieval** with optional **ColBERT semantic retrieval**, returning a normalized relevance score from `0.0` to `1.0`.

```text
Query Intent
    ↓
Namespace Scope
    ↓
BM25S + Optional ColBERT
    ↓
Ranked Top-K Tools
```

Retrieval mode, ranking weights, and ColBERT configuration are deployment settings. See the [Application Reference](docs/app_reference.md) for tuning details.

### Discovery result contract

`axiolex_discover_tools()` and `POST /discover` return execution-ready tool specifications with runtime metadata, input schemas, and relevance scores.

```json
{
  "tool_id": "finance.market_data.get_quote",
  "name": "get_quote",
  "description": "Retrieve the latest market quote for a security",
  "namespace": "finance",
  "provider": "market-data-mcp",
  "relevance_score": 0.94,
  "bm25_score": 12.4,
  "colbert_score": 0.88,
  "parameters": {
    "type": "object",
    "properties": {
      "symbol": { "type": "string" }
    },
    "required": ["symbol"]
  }
}
```

### Execution contract

Tool execution through `axiolex_execute_tool()` or `POST /execute` requires only the stable `tool_id` returned during discovery and arguments matching the tool schema.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `tool_id` | string | Yes | Stable Axiolex identifier returned during discovery |
| `arguments` | object | Yes | Arguments validated against the current tool schema |
| `idempotency_key` | string | No | Optional client key for request de-duplication |
| `timeout_ms` | integer | No | Execution timeout override, subject to the server limit |

```json
{
  "status": "success",
  "tool_id": "finance.market_data.get_quote",
  "execution_id": "exec_98f2a11b0c",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "AAPL: $224.23 (+1.2%)"
      }
    ]
  },
  "error": null
}
```

### Standardized execution errors

Axiolex normalizes execution failures across supported transports.

| Error code | Description | Retryable |
| --- | --- | --- |
| `TOOL_NOT_FOUND` | `tool_id` does not resolve in the current catalog | No |
| `TOOL_UNAVAILABLE` | Tool transport is disabled or unavailable | No |
| `INVALID_ARGUMENTS` | Arguments failed schema validation | No |
| `UPSTREAM_TIMEOUT` | Downstream provider exceeded the execution timeout | Yes |
| `UPSTREAM_ERROR` | Downstream provider returned a runtime error | Depends |
| `RATE_LIMITED` | Axiolex or downstream provider rate limit reached | Yes |
| `INTERNAL_ERROR` | Server-side execution failure | Yes |

### Observability and artifact metadata

Discovery and execution activity can be logged for routing diagnostics, security review, and relevance evaluation.

Captured metadata includes:

* query and namespace scope
* ranked Top-K candidates and relevance scores
* execution latency
* caller identifiers
* tool and provider identifiers

Tools that produce visual or structured artifacts can also return artifact-aware metadata so host applications can route rendered output to the UI while keeping compact semantic results in the LLM context.


## Setup & Quick Start

### 1. Server installation & local run

Axiolex runs as a shared FastAPI service backed by Redis for catalog state. Choose either host-based installation or containerized deployment.

**Option A: Local host setup (recommended for dev):**

```bash
# Clone repository
git clone https://github.com/vrraj/axiolex.git && cd axiolex

# Install server & dependencies (BM25 lexical search enabled)
make install

# Optional: add ColBERT hybrid search (semantic retrieval)
make colbert

# Start local services (Redis + Axiolex API)
make start
```

**Option B: Docker deployment (production-like):**

```bash
# Spin up Axiolex and Redis in isolated containers
make docker-up

# Verify service health
curl http://localhost:9700/status
```

ColBERT model cache is bind-mounted to the host via `AXIOLEX_COLBERT_CACHE_HOST_DIR` (default: `~/models/fastembed_cache`) so model downloads persist across container rebuilds and are shared with host-mode runs.

Once running, access the web dashboard at http://localhost:9700/.

**Install extras:**

| Extra | Command | Purpose |
| --- | --- | --- |
| `server` | `pip install "axiolex[server]"` | FastAPI, Uvicorn, BM25S, PyStemmer, Redis, MCP SDK, cryptography |
| `colbert` | `pip install "axiolex[colbert]"` | FastEmbed, ONNX Runtime, NumPy, ColBERT hybrid retrieval |
| `dev` | `pip install "axiolex[dev]"` | pytest, black, ruff |

> **ColBERT is optional at install time.** `make install` gives you a fully working server with BM25 lexical search. Run `make colbert` to add semantic retrieval, then set `AXIOLEX_HYBRID_ENABLED=true` in `.env`. If you skip `make colbert`, `make start` will install the packages on first launch (one-time download delay).

### 2. Connect AI clients (MCP setup)

Axiolex exposes MCP at `http://localhost:9700/mcp`. See [Integration Surfaces & Client Access](#integration-surfaces--client-access) for configuration examples for Claude Desktop, Cursor, and Codex (streamable HTTP and npx stdio proxy).

### 3. Application & SDK access

For Python SDK and REST API code examples, see [Integration Surfaces & Client Access](#integration-surfaces--client-access).

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

### @axiolex/mcp-gateway (npm package)

The stdio proxy is published as [`@axiolex/mcp-gateway`](https://www.npmjs.com/package/@axiolex/mcp-gateway) on npm. The proxy version is independent of the Axiolex Python package version. Bump `mcp-gateway/package.json` and publish to npm when the proxy changes.

**For developers working on the proxy itself:**

```bash
cd mcp-gateway
npm install          # install dependencies
node index.js --endpoint http://localhost:9700/mcp   # run locally
npm publish --access public   # publish new version (requires npm login)
```

### Common Makefile targets

| Target | Purpose |
| --- | --- |
| `make install` | Install Axiolex server and development dependencies with BM25 lexical retrieval |
| `make colbert` | Add optional ColBERT hybrid retrieval dependencies |
| `make start` | Start Redis, refresh the catalog, and run the Axiolex services |
| `make stop` | Stop local services |
| `make docker-up` | Run full stack (Axiolex + Redis) in Docker containers |
| `make docker-down` | Stop and remove Docker containers |
| `make index-refresh` | Rebuild the Redis catalog from configured sources |
| `make test` | Run the test suite |
| `make format` | Format code and run lint fixes |
| `make type-check` | Run static type checks |
| `make build` | Build Python package artifacts |
| `make clean` | Remove local build and Python cache artifacts |

**Links:** [PyPI](https://pypi.org/project/axiolex/) · [GitHub](https://github.com/vrraj/axiolex) · [API Documentation](https://vrraj.github.io/axiolex/)

## Web UI & Operational Control

The Axiolex Web UI is the primary management, administration, and testing control plane for enterprise tool governance. Accessible at http://localhost:9700/, it provides live visual control over the capability catalog, retrieval engines, and provider security without requiring custom code or client restarts.

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              AXIOLEX DASHBOARD & CONTROL PLANE                         │
├───────────────────────────────┬───────────────────────────────┬────────────────────────┤
│  1. Provider Management       │  2. Interactive Testing       │  3. Retrieval Tuning   │
│  • Dynamic Add/Edit/Disable   │  • Live Query Discovery       │  • BM25 Lexical        │
│  • Encrypted Secrets (GCM)    │  • Relevance Score Validation │  • ColBERT Semantic    │
│  • Direct Tool Execution      │  • Namespace Scope Inspection │  • Adjust top_k Bounds │
└───────────────────────────────┴───────────────────────────────┴────────────────────────┘
│                     *Operates against the unified Axiolex REST API*                    │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Core operations & management capabilities

* **Provider registration & lifecycle:** register, enable, disable, or refresh downstream MCP providers (stdio and Streamable HTTP), A2A agents, and local tool definitions. Configure transport, endpoints, auth, and namespace assignments from a single form. Reindex the catalog (rebuild BM25S + ColBERT indexes) or reload from cache after provider changes.
* **Encrypted secret management:** configure provider authentication (Basic auth, Bearer tokens, API keys) securely via the UI — encrypting secrets directly into the AES-256-GCM backend (`mcp_secrets.enc`).
* **Discovery evaluation & interactive testing:** run live discovery queries with different parameters (namespace scope, `top_k`, hybrid search toggle) to evaluate retrieval quality, relevance scores, and ranking behavior before rolling out to AI agents. Execute discovered tools directly to verify arguments, schema compliance, and provider responses.
* **Retrieval engine tuning:** bench-test hybrid search performance live by toggling between BM25S lexical search and ColBERT semantic retrieval, adjusting temperature, softmax cutoff, and `top_k` response limits. Inspect rank and relevance scores across namespaces.
* **Namespace setup & inspection:** create, edit, and delete namespaces; explore the unified catalog hierarchy to audit domain boundaries, tool assignments, and schema definitions across the enterprise.
* **System status:** monitor service health, Redis connectivity, retriever status, and catalog version.

The Web UI operates against the same Axiolex REST API and catalog as the Python SDK, MCP interface, and CLI tools.

![Axiolex Web UI](images/axiolex-interactive-ui.png)

## Security Overview

Axiolex enforces a dual-boundary security architecture: securing clients accessing Axiolex and protecting Axiolex accessing downstream providers.

```text
┌─────────────────┐    Authenticated Boundary    ┌─────────────────┐   Server-Side Secrets   ┌──────────────────┐
│  Client / LLM   │ ───────────────────────────► │ Axiolex Gateway │ ──────────────────────► │ Downstream Provider│
│ (Claude/Cursor) │  OAuth2 / mTLS / API Keys    │  (AES-256-GCM)  │   Service Accounts     │  (Jira / Tavily) │
└─────────────────┘                              └─────────────────┘                         └──────────────────┘
```

### 1. Client authentication & authorization

* **Trusted environment model:** requests to REST, MCP, SDK, and Web UI endpoints should be authenticated at the enterprise boundary (e.g. via OAuth/OIDC, mTLS, or API keys).
* **Isolation:** consuming applications and AI clients never receive or negotiate downstream provider credentials.

### 2. Downstream provider authentication

* **Encrypted secret store:** secrets are stored in `source_files/mcp_secrets.enc`, encrypted at rest using AES-256-GCM. Master keys are passed via `AXIOLEX_SECRET_MASTER_KEY`.
* **Resolution hierarchy:** Axiolex resolves credentials via environment variables (`auth.secret_env`) first, falling back to the encrypted secret store second.
* **Redaction & zero-leakage:** provider tokens are injected into child processes at runtime (e.g. via stdio environment variables). Credentials are strictly stripped from logs, REST payloads, and Redis metadata.

### 3. Identity model & lifecycle

| Dimension | Current phase (service accounts) | Future phase (per-user delegation) |
| --- | --- | --- |
| Credential storage | Centralized in Axiolex encrypted store (1 service account / provider) | Axiolex per-user credential mapping or OAuth token exchange |
| Client configuration | Axiolex server URL only | Axiolex server URL only |
| User authentication | Enterprise boundary (OAuth / API keys) | Enterprise boundary (OAuth / API keys) |
| Audit trail | Downstream logs show central service account | Downstream logs reflect individual user identity |

For provider YAML configurations, detailed secret store setup, and adapter specifications, see [docs/architecture.md](docs/architecture.md).

## API Reference

Comprehensive OpenAPI / Swagger interactive documentation is served directly from a running instance at http://localhost:9700/docs.

### Core API & SDK mapping

| Operation | REST endpoint | Python SDK method | Description |
| --- | --- | --- | --- |
| Discovery | `POST /discover` | `client.discover()` | Search ranked capabilities using BM25S / ColBERT |
| Execution | `POST /execute` | `client.execute()` | Execute a discovered tool using its `tool_id` |
| Namespaces | `GET /namespaces` | `client.list_namespaces()` | List registered enterprise tool domains and scopes |
| System status | `GET /status` | `client.health()` | Health check, uptime, and underlying Redis metrics |

### Management & administration endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET/POST/PUT/DELETE` | `/mcp-providers` | Manage registered MCP/A2A provider definitions |
| `POST/GET/DELETE` | `/mcp-providers/{id}/secret` | Store, check existence of, or clear encrypted provider credentials |
| `POST/PUT/DELETE` | `/namespaces/{id}` | Manage capability domain filtering and scoping |

For complete request/response JSON schemas and CLI commands, see the [Application Reference](docs/app_reference.md).

## Development

For local development setup, see [Setup & Quick Start](#setup--quick-start).

For details on MCP tool descriptions and how to customize AI client behavior, see [Axiolex MCP Tools](#axiolex-mcp-tools).

Additional Docker targets:

```bash
make docker-logs          # tail Axiolex container logs
make docker-restart       # restart Axiolex (e.g. after editing source_files/*.yaml)
make docker-build         # rebuild image without cache
make docker-down-volumes  # stop + wipe volumes (full reset)
```

For full Docker configuration details, Redis placement options, and environment variables, see the [Technical Architecture](docs/technical_architecture.md).

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
