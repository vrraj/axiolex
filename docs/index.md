---
description: Enterprise capability discovery and execution for AI clients and applications across MCP tools, A2A agent skills, internal services, and shared capability catalogs.
layout: default
title: "Axiolex: Enterprise Capability Discovery for AI Clients and Applications"
---

# Axiolex

## Enterprise Capability Discovery for AI Clients and Applications

What does it look like when an AI client can discover the right enterprise tools at runtime instead of loading or maintaining the full capability catalog itself?

### Axiolex through an AI Client

<blockquote style="border-left: 0;"><strong>What capability can check contract approval status</strong> for deals expected to close this quarter?</blockquote>

<blockquote style="border-left: 0;"><strong>Find the tool that can explain supplier lead-time risk</strong> for a semiconductor materials workflow.</blockquote>

<blockquote style="border-left: 0;"><strong>Which HR recruiting tools are available</strong> for identifying engineering roles that have remained open for more than 60 days?</blockquote>

<blockquote style="border-left: 0;"><strong>How has Apple been doing lately?</strong> Expand the request into market-data intent, discover the appropriate capability, and execute it.</blockquote>

<br>

<blockquote>
  <h4 style="color:#ab6a27"><strong>Dynamic discovery:</strong> Axiolex lets AI clients and applications search a shared enterprise capability catalog by query intent and business scope, then execute discovered tools through a stable interface when the client cannot register new tools dynamically.</h4>
</blockquote>

## Behind the Queries

**Axiolex** is a shared capability discovery layer for enterprise applications and AI clients.

It maintains a searchable catalog of **MCP tools, A2A agent skills, internal services, and static capability definitions**, then retrieves a small ranked set of capabilities based on the **user's intent** and the applicable **business scope**. The caller never needs to know whether a tool is backed by MCP, A2A, or an internal service — Axiolex discovers, ranks, and executes them through the same contract.

An AI client does not need to know every tool name, every provider endpoint, or every capability deployed across the organization before a session begins.

Instead, it can discover what it needs when the request arrives.

> **Explore:** [GitHub](https://github.com/vrraj/axiolex) · [PyPI](https://pypi.org/project/axiolex/) · [API Documentation](https://vrraj.github.io/axiolex/)

## The Problem, in Numbers

An AI client connected to 20 MCP servers with 10 tools each may have 200 tool definitions available.

If those schemas average 200–300 tokens each across names, descriptions, input schemas, and examples, tool definitions alone could consume roughly **40,000–60,000 tokens of context** before the user's question, conversation history, or retrieved data are added.

Anthropic has documented the same scaling problem, including a 58-tool example consuming approximately **55,000 tokens** before the conversation begins.

The problem is broader than context size:

- **Tool selection gets harder as catalogs grow.**
- **Each client can end up maintaining its own stale tool inventory.**
- **New MCP servers are invisible to clients that were never configured to connect to them.**
- **Capability updates have to propagate across many consumers instead of one shared catalog.**

Axiolex separates **capability discovery** from **capability execution** so clients can retrieve only the tools relevant to the current request.

## Enterprise Requests

Axiolex organizes enterprise capabilities by business scope and retrieves tools that match the request intent within that eligible set.

| User request | Search scope |
|---|---|
| “Show which business units have the largest variance between forecast and actual revenue.” | Finance |
| “Check whether the Micron NDA covers product evaluation.” | Legal |
| “Show engineering roles that have remained unfilled for more than 60 days.” | HR Recruiting |
| “What health insurance options are available for dependents?” | HR Employee Services |
| “Explain what is driving the predicted supplier lead time up for `SAMSUNG_HBM3e_LINES`.” | Supply Chain |
| “Which deals expected to close this quarter are still waiting for contract approval?” | Sales + Legal |
| “Search Jira for open tickets in the SCRUM project and create a new task.” | Project Management |

Axiolex represents these search scopes as **namespaces** such as `finance`, `legal`, `sales`, `hr.recruiting`, `hr.employee_services`, and `supply_chain`.

A request can search one namespace, multiple namespaces, or `all`.

The namespace defines **eligibility**. Query intent determines **ranking** within that eligible set.

## How Axiolex Is Used

Axiolex supports two common patterns.

### Purpose-Built Enterprise Applications

Applications that control their own orchestration can call Axiolex directly with the request intent and namespace scope.

```text
User Request
     ↓
query intent + namespace scope
     ↓
Axiolex
     ↓
Intent-matched tools and capabilities
     ↓
Application orchestrates or executes
```

The application can execute the selected capability itself or use `axiolex_execute_tool`.

### General-Purpose AI Clients and Agents

Clients such as Claude, Cursor, enterprise copilots, and other agents can use:

```text
list_namespaces()
axiolex_discover_tools(...)
axiolex_execute_tool(...)
```

The client only needs Axiolex's stable discovery and execution interface registered ahead of time.

Downstream tools, providers, endpoints, and transports can change without requiring every capability to be individually registered with the client.

## Tool Discovery Flow

Axiolex narrows the enterprise catalog in two steps:

**search scope defines eligibility → query intent determines ranking**

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

For multi-scope requests, Axiolex searches the union of the supplied namespaces.

With `all`, the complete catalog is eligible for retrieval, but results are still ranked by relevance.

## Core Capabilities

- **Shared capability catalog** — maintains current tool and provider definitions across MCP servers, A2A agent skills, static registries, and internal services.
- **Dynamic provider discovery** — refreshes registered MCP and A2A providers so additions, renames, schema changes, and retirements are reflected centrally.
- **Intent-based retrieval** — ranks tools against the request using BM25S lexical retrieval with optional ColBERT semantic retrieval.
- **Namespace-scoped discovery** — supports single-scope, multi-scope, and full-catalog discovery.
- **Stable execution bridge** — executes a discovered capability by `tool_id` when the client cannot dynamically register new tools.
- **Multiple interfaces** — REST API, Python SDK, MCP interface, CLI, and Web UI.
- **Auditability** — records request intent, search scope, ranked results, scores, and latency for evaluation and troubleshooting.

## One Catalog, Different Capability Sources

Axiolex normalizes capabilities from different enterprise systems into one searchable catalog.

```text
MCP Providers
Static Registries
A2A Agent Skills
Internal Services
       │
       ▼
  Axiolex Catalog
       │
       ▼
Discovery + Ranking
       │
       ▼
Applications / AI Clients
```

Registered MCP providers can use **Streamable HTTP** or **stdio**. A2A providers expose skills via an agent card and are executed through the A2A `SendMessage` protocol. A2A execution is synchronous — Axiolex sends the request, waits within the configured timeout, and returns a normalized result.

Provider credentials remain server-side, so consuming applications do not need direct access to downstream secrets. For providers that require username + token authentication (e.g. **Jira** using email + API token), Axiolex stores the non-secret username in the provider config and the token in an encrypted secret store, passing both to the provider's subprocess at runtime.

### Included Provider Integrations

| Provider | Transport | Auth | Tools |
|----------|-----------|------|-------|
| **Alpha Vantage** | Streamable-HTTP | API Key | Financial market data |
| **Tavily** | Streamable-HTTP | API Key | Web research and search |
| **Fetch Server** | stdio | None | Web page fetching |
| **Text Utilities** | stdio | None | Word count, slug generation, keyword extraction |
| **Jira** | stdio | Basic (email + API token) | Ticket search (JQL), ticket creation |
| **A2A Agents** | A2A | Bearer / None | Agent skills via agent card |

Custom stdio servers can be added by placing a Python MCP server script in `stdio_servers/` and registering it in `mcp_providers.yaml`. The `transport` field describes how Axiolex communicates with the provider, not how the provider talks to its downstream service — for example, the Jira adapter (`atlassian_rest_to_mcp`) speaks MCP over stdio with Axiolex and HTTPS REST with Atlassian:

```text
Axiolex ──[stdio, MCP protocol]──► atlassian_rest_to_mcp.py ──[HTTPS, REST API]──► atlassian.net
```

See the [Providers Guide](mcp_providers.md) for configuration details.

## Provider and Catalog Management

Axiolex keeps the shared catalog current as providers and tools change.

Provider and catalog operations are available through the **Web UI** and **REST APIs**.

Teams can:

- add, edit, enable, disable, or remove providers;
- refresh provider tool definitions;
- assign namespaces;
- propagate additions, renames, schema changes, and retirements;
- increment catalog versions so Axiolex processes rebuild retrieval indexes against the latest state.

This centralizes capability lifecycle management instead of reproducing it in every consuming client.

## Retrieval and Ranking

Axiolex ranks the capabilities most likely to satisfy the request intent within the selected scope.

- **BM25S** provides lexical retrieval across tool names, descriptions, parameters, and domain terminology.
- **ColBERT** can add semantic matching when lexical overlap is not sufficient.
- **Hybrid ranking** combines lexical and semantic evidence.
- **Unified relevance scores** give consumers a consistent ranking signal.
- **Top-K control** limits how many tools are returned.

The calling application decides which returned capabilities are injected into model context, orchestrated, or executed.

## Search Result Contract

Each discovery result returns the information a caller needs to evaluate or execute the capability.

Typical fields include:

- `tool_id`
- `name`
- `description`
- `parameters`
- `namespace`
- `provider`
- `relevance_score`
- optional lexical and semantic scores
- transport and runtime metadata

```json
{
  "tool_id": "finance.market_data.get_quote",
  "name": "get_quote",
  "description": "Retrieve the latest market quote for a security",
  "namespace": "finance",
  "provider": "market-data-mcp",
  "relevance_score": 0.94
}
```

The client does not need to embed the current runtime location of the tool.

## Stable Tool Execution

Axiolex can execute a discovered capability by `tool_id` without requiring the client to know the provider endpoint or transport.

```text
axiolex_execute_tool(tool_id, arguments)
```

Axiolex resolves the current provider and tool contract from the catalog, validates the arguments, and invokes the underlying capability.

Purpose-built applications can still execute discovered tools directly when they control their own orchestration.

## Discovery and Orchestration Boundaries

Axiolex keeps tool retrieval separate from request expansion, decomposition, and workflow planning.

### Compound Requests

A compound request contains multiple independently answerable intents.

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

The calling LLM or orchestrator is responsible for decomposing the request into focused retrieval queries.

Axiolex does not rewrite or decompose the request itself.

### Query Expansion

The caller can also translate conversational language into retrieval-specific intent before calling Axiolex.

```text
"How is Apple doing lately?"
        ↓
"Apple AAPL recent stock price performance and market data"
        ↓
axiolex_discover_tools(...)
```

This gives retrieval a cleaner intent and improves the likelihood of matching narrow tool descriptions.

### Multi-Scope Requests

A multi-scope request is different: it has **one business intent** that requires capabilities from more than one domain.

For example:

> “Which deals expected to close this quarter are still waiting for contract approval?”

The caller can search `["sales", "legal"]` together because both domains are required to answer the same question.

### Execution Sequencing

Independent work can be discovered upfront.

Workflows with data dependencies can use:

```text
discover → execute → discover
```

The calling LLM or orchestrator decides when discovery happens relative to execution.

## Why MCP `list_changed` Is Not Enough

MCP `tools/list_changed` is useful for signaling tool changes from a server the client is **already connected to**.

It does not solve discovery of a newly deployed MCP server that the client has never been configured to connect to.

Even within an existing connection, coverage depends on implementation behavior:

- **Client support varies** — clients differ in whether and when they refresh tool definitions.
- **Servers must emit the notification** — if a server does not implement `listChanged`, the client receives no update.
- **Active conversations may still contain stale tool context** — refreshing the server tool list does not automatically replace tool descriptions or parameter assumptions already present in the conversation.

Axiolex instead maintains the current enterprise capability catalog centrally.

Newly registered providers and refreshed tool definitions become available to consumers on subsequent discovery calls.

## Discovery Audit and Evaluation

Axiolex records discovery requests so teams can evaluate retrieval quality and troubleshoot routing.

Audit records can include:

- query;
- namespace scope;
- returned Top-K tools and scores;
- discovery latency;
- caller identifier.

Two quality measures are especially useful:

- **Tool retrieval accuracy** — whether the correct capability appears near the top of the ranking.
- **Namespace-selection accuracy** — whether the calling LLM or application selected the correct search scope.

These fail independently and can be tuned independently.

## Web UI

Axiolex includes a Web UI for managing providers, inspecting the catalog, and testing discovery behavior.

The UI can be used to:

- manage and refresh providers;
- inspect discovered tools and namespace assignments;
- run discovery queries;
- review ranked results and relevance scores;
- validate catalog changes without writing client code.

The Web UI uses the same Axiolex service and catalog as the REST, Python SDK, and MCP interfaces.

## Enterprise Security

The current Axiolex implementation assumes a trusted deployment environment.

For a centrally deployed enterprise service, client requests should be authenticated at the Axiolex service boundary using mechanisms such as OAuth/OIDC, machine-to-machine credentials, signed JWTs, mTLS, or API keys.

Downstream MCP and service credentials remain server-side. Fine-grained user- and client-level authorization is not implemented in the current phase.

## For Developers

Axiolex is implemented as a modular Python service with a shared catalog and thin client interfaces.

| Layer | Technology | Role |
|---|---|---|
| Language | **Python** | Core service, provider management, retrieval, execution |
| API / Service | **FastAPI** | REST APIs, provider management, Web UI |
| Catalog | **Redis** | Shared capability and runtime metadata |
| Retrieval | **BM25S** | Lexical tool discovery |
| Semantic retrieval | **ColBERT** | Optional hybrid semantic ranking |
| Agent access | **MCP** | Namespace discovery, tool discovery, stable execution |
| Client access | **Python SDK + HTTP** | Application integration |
| Provider transports | **Streamable HTTP + stdio + A2A** | MCP provider connectivity, A2A agent skills |

### Runtime Interfaces

- **MCP** — `list_namespaces`, `axiolex_discover_tools`, `axiolex_execute_tool`
- **REST / OpenAPI** — discovery, provider management, catalog operations, execution
- **Python SDK** — thin client over the Axiolex service
- **Web UI** — provider management and retrieval validation

## Install and Quick Start

Install the Python SDK:

```bash
uv add axiolex
```

or:

```bash
pip install axiolex
```

For the Axiolex server:

```bash
pip install "axiolex[server]"
```

For server + ColBERT hybrid retrieval:

```bash
pip install "axiolex[server,colbert]"
```

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

### Deployment

Axiolex runs as a shared FastAPI service with Redis-backed catalog state.

Docker can be used to run the Axiolex server and Redis together.

## Explore the Project

- [GitHub Repository](https://github.com/vrraj/axiolex) — source, releases, tests, and README
- [PyPI](https://pypi.org/project/axiolex/) — Python package
- [API Documentation](https://vrraj.github.io/axiolex/) — REST and OpenAPI reference

## License

Axiolex is released under the license included in the repository.
