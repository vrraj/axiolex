---
description: Capability discovery for enterprise applications and AI clients.
  Axiolex maintains a searchable catalog of enterprise capabilities and returns
  only the tools relevant to each request, scoped by business namespace.
layout: default
title: "Axiolex: Capability Discovery for Enterprise Applications and AI Clients"
---

# Axiolex

## Capability Discovery for Enterprise Applications and AI Clients

What does it look like when an AI client or enterprise application can discover the right enterprise capability for a business question without knowing what tools exist, who owns them, or where they are deployed?

### Axiolex through Claude

<blockquote style="border-left: 0;"> <strong>What health insurance options are available for dependents?</strong></blockquote>

<blockquote style="border-left: 0;"> <strong>Which deals expected to close this quarter are still waiting for contract approval?</strong></blockquote>

<blockquote style="border-left: 0;"> <strong>Show engineering roles that have remained unfilled for more than 60 days.</strong></blockquote>

<blockquote style="border-left: 0;"> <strong>Explain what is driving the predicted supplier lead time up for SAMSUNG_HBM3e_LINES.</strong></blockquote>

<br>

<table style="width:100%; border:none; table-layout:fixed;">
  <tr>
    <td width="50%" align="center" valign="top" style="border:none; padding:8px;">
      <strong>Discovering capabilities by namespace</strong>
      <br><br>
      <img src="https://raw.githubusercontent.com/vrraj/axiolex/main/images/axiolex-interactive-ui.png" width="100%" />
    </td>
    <td width="50%" align="center" valign="top" style="border:none; padding:8px;">
      <strong>Routing layer before LLM context assembly</strong>
      <br><br>
      <img src="https://raw.githubusercontent.com/vrraj/axiolex/main/images/axiolex-llm.png" width="100%" />
    </td>
  </tr>
</table>

<blockquote>
  <h4 style="color:#ab6a27"><strong>MCP access:</strong> Axiolex includes an MCP server for AI clients. Call <code>list_namespaces</code> to discover the enterprise capability map, <code>axiolex_discover_tools</code> to find ranked capabilities within a business scope, and <code>axiolex_execute_tool</code> to execute a discovered tool by its <code>tool_id</code> — without loading the full tool catalog into context.</h4>
</blockquote>

## Behind the Queries

**Axiolex** is a **capability discovery service for enterprise applications and AI clients**. It maintains a searchable catalog of enterprise capabilities — MCP tools, A2A endpoints, internal services, and YAML-defined tools — and returns only the small subset relevant to a given request.

Core business capabilities become discoverable to AI clients and AI-enabled applications such as Claude, Cursor, enterprise copilots, and internal agentic applications without each user needing to know what exists, who owns it, or where it is deployed.

For each request, Axiolex can expose only the capabilities relevant to the user's intent — reducing tool confusion, limiting context and token overhead, and giving applications a controlled way to govern which capabilities are available.

> **Explore:** [GitHub](https://github.com/vrraj/axiolex) · [Setup &
> Usage](setup-usage) · [Technical Architecture](technical-architecture)

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

A calling application or AI client can use **single-scope discovery**, **multi-scope discovery**, or **full-catalog discovery**, depending on the request.

Axiolex represents these search scopes as **namespaces**, such as `finance`, `legal`, `sales`, `hr.recruiting`, `hr.employee_services`, and `supply_chain`.

## How Axiolex Is Used

### Domain and Enterprise Applications

A purpose-built application can be configured with the business areas it is allowed to search. An HR application might use `hr.recruiting` and `hr.employee_services`. A sales application might use `sales`, `finance`, and `legal`. For each request, the application selects the relevant search scope and asks Axiolex to discover matching capabilities.

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

### General-Purpose AI Clients and Agents

A general-purpose AI client may not know the organization's capability map in advance. Axiolex exposes that map through `list_namespaces()`. The client uses the returned names and descriptions to determine the relevant search scope, then calls `axiolex_discover_tools()`.

```text
User
  │
  │ "What health insurance options are available for dependents?"
  ▼
AI Client / Agent
  │
  ├── list_namespaces()
  │       finance · legal · sales
  │       hr.recruiting · hr.employee_services · supply_chain
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

## Core Capabilities

- **Shared capability catalog** — normalize MCP-discovered and configured capabilities into a common searchable catalog.
- **Dynamic MCP discovery** — connect to configured MCP providers over Streamable HTTP or stdio and ingest their tool definitions.
- **Namespace discovery** — expose available business capability areas and descriptions through `list_namespaces`.
- **Single-scope, multi-scope, and full-catalog discovery** — search within one namespace, across multiple namespaces, or across all eligible capabilities.
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

Namespaces are applied before retrieval. With multiple namespaces, Axiolex searches the union of capabilities eligible for those namespaces. `top_k` controls the maximum number of candidates returned. The calling application decides which results enter LLM context.

## How the System Fits Together

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

The calling application determines the business intent and search scope. Axiolex searches the eligible capability set and returns the most relevant results. Execution, authentication, authorization, workflow logic, and application-specific guardrails remain with the consuming application or execution layer.

### Data Architecture

Axiolex separates the shared capability catalog (Redis) from per-process search indexes (in-memory). Redis stores what tools exist and how to execute them. Each process builds its own BM25S and optional ColBERT indexes from that catalog.

```text
        tools_list.yaml · mcp_providers.yaml · namespaces.yaml
                         │
                         ▼
                 catalog refresh
                         │
                         ▼
                ┌─────────────────┐
                │      REDIS      │
                │ shared catalog  │
                │ discovery data  │
                │ runtime data    │
                │ catalog version │
                └────────┬────────┘
                         │
                Axiolex process
                         │
                ┌────────┴────────┐
                │ in-process      │
                │ search indexes  │
                │ BM25S           │
                │ ColBERT optional│
                └─────────────────┘
```

Redis stores shared catalog state. BM25S and ColBERT indexes are derived data held in process memory and rebuilt from Redis when the catalog version changes.

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

The base PyPI package is a thin HTTP client. Applications do not connect directly to Redis, build indexes, load ColBERT, or discover MCP providers themselves.

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

## Retrieval

### Lexical Search

BM25S with PyStemmer provides the base retrieval path — useful for tool and command names, enterprise terminology, domain-specific vocabulary, and deterministic low-latency retrieval. The base install does not require a model download.

### Optional Hybrid Search

Axiolex can combine BM25S lexical retrieval with ColBERT late-interaction semantic retrieval. BM25S and ColBERT operate only on the capability set eligible for the supplied namespaces. Axiolex normalizes each model's candidate scores independently before weighted fusion because raw BM25 and ColBERT scores use different numeric scales.

```text
P_bm25(doc)   = softmax(BM25 scores / temperature)
P_colbert(doc)= softmax(ColBERT scores / temperature)

hybrid_score(doc) =
    normalized_bm25_weight   * P_bm25(doc)
  + normalized_colbert_weight * P_colbert(doc)
```

When hybrid search is unavailable, an explicit hybrid request fails clearly rather than silently falling back to lexical search.

### Unified Relevance Contract

Consumers receive a unified `relevance_score` regardless of search mode. In lexical mode it reflects the normalized lexical ranking score; in hybrid mode it reflects the fused hybrid ranking score. The score is intended for ranking and approximate filtering within the current result set.

## MCP Discovery Server

Axiolex exposes an MCP interface for external AI clients and MCP hosts. The interface exposes three tools:

```text
list_namespaces
axiolex_discover_tools
axiolex_execute_tool
```

`axiolex_discover_tools` returns ranked capabilities with a `tool_id`. `axiolex_execute_tool` runs a discovered tool by its `tool_id` — the dispatcher resolves the endpoint, transport, and provider from the catalog at call time.

<blockquote>
  <h4 style="color:#ab6a27"><strong>Claude Desktop integration:</strong> Add Axiolex as an MCP server and Claude can discover enterprise capabilities by namespace without loading the full tool catalog. See the <a href="claude-mcp">Claude MCP guide</a> for setup.</h4>
</blockquote>

## Capability Sources

Axiolex can build its catalog from multiple sources:

- **MCP Providers** — discovered over Streamable HTTP (remote services) or stdio (local subprocesses).
- **Static Registries** — YAML-backed definitions for version-controlled tools and internal capability records.
- **Internal Services and Endpoints** — A2A endpoints and other enterprise capabilities represented through the same normalized discovery metadata.

## Provider and Catalog Management

Axiolex includes management interfaces for maintaining the capability catalog:

- Add, edit, enable, disable, and remove MCP providers.
- Assign namespaces to providers.
- Retrieve or refresh tools from individual providers.
- Manage namespaces and namespace descriptions.
- Inspect cached tool counts.
- Refresh the shared catalog without restarting consuming applications.

Catalog changes increment a shared catalog version. Axiolex processes detect the change and rebuild their in-memory retrieval indexes from the updated Redis catalog.

## For Developers

Axiolex is implemented as a modular Python architecture with a thin SDK surface and a server-side retrieval engine.

| Layer | Technology | Role |
|---|---|---|
| Language | **Python** | SDK, retrieval engine, services, MCP server |
| SDK | **httpx + pydantic** | Thin HTTP client — always importable from the base package |
| API / Service | **FastAPI + Uvicorn** | REST API and web UI service layer |
| Lexical retrieval | **BM25S + PyStemmer** | Fast, deterministic keyword matching with stemming |
| Semantic retrieval | **FastEmbed + ColBERT** | Optional late-interaction semantic search |
| Catalog | **Redis** | Shared capability catalog (discovery + runtime data) |
| Configuration | **YAML** | Tools, providers, namespaces, settings |
| Agent access | **MCP SDK** | `axiolex_discover_tools`, `axiolex_execute_tool`, and `list_namespaces` over stdio and Streamable HTTP |
| Security | **AES-256-GCM (cryptography)** | Encrypted secret store for provider credentials |
| Testing | **pytest** | Unit, integration, and MCP coverage |

### Runtime Interfaces

- **MCP** — `axiolex_discover_tools`, `axiolex_execute_tool`, and `list_namespaces` for AI clients over stdio or Streamable HTTP.
- **REST / OpenAPI** — programmatic access to discovery, retrieval, namespace management, provider management, and secret management.
- **Python SDK** — thin HTTP client for applications (`pip install axiolex`).
- **Web UI** — interactive discovery, provider onboarding, namespace management, and retrieval tuning.
- **CLI** — `axiolex-server`, `axiolex-index`, `axiolex-mcp-server`.

### Install

```bash
pip install axiolex          # thin SDK (httpx + pydantic only)
```

Optional extras:

| Extra | Command | Purpose |
| --- | --- | --- |
| `server` | `pip install "axiolex[server]"` | FastAPI, Uvicorn, BM25S, PyStemmer, Redis, MCP SDK, cryptography |
| `colbert` | `pip install "axiolex[colbert]"` | FastEmbed, ONNX Runtime, NumPy — hybrid retrieval |
| `dev` | `pip install "axiolex[dev]"` | pytest, black, ruff |

For a full server with hybrid retrieval: `pip install "axiolex[server,colbert]"`

## Extending Axiolex

The architecture is designed to extend along several dimensions:

- add MCP providers from new sources (Streamable HTTP or stdio);
- add pre-built MCP servers from PyPI (`uvx`) or npm (`npx`);
- define additional namespaces and assign them to providers;
- add static capability definitions through YAML;
- tune retrieval parameters (temperature, cutoff, hybrid weights);
- extend the retrieval engine with new backends;
- add cache backends alongside Redis.

The shipped MCP server supports discovery and execution. `axiolex_discover_tools` finds ranked capabilities; `axiolex_execute_tool` dispatches a discovered tool through Axiolex's transport adapter layer. Authentication, authorization, and per-user governance can be added as a separate execution-policy layer.

## Explore the Project

- [GitHub Repository](https://github.com/vrraj/axiolex) — source, releases, tests, and full README
- [Technical Architecture](technical-architecture) — top-down architecture document with progressive detail
- [Setup & Usage Guide](setup-usage) — installation, platform, and automation instructions
- [API Reference](api-reference) — REST endpoint signatures and response schemas
- [MCP Providers Guide](mcp_providers) — provider configuration in depth
- [Claude MCP Integration](claude-mcp) — Claude Desktop setup
- [Document and Tool Ingestion Guide](document-and-tool-ingestion-guide) — ingestion workflows
- [Full README](https://github.com/vrraj/axiolex#readme) — install, features, configuration, deployment
- [PyPI Package](https://pypi.org/project/axiolex/)
- [Story on Medium](https://medium.com/@vr.rajkumar99/context-engineering-for-tool-heavy-agents-lexical-routing-c1b0ebad7495) — context engineering for tool-heavy agents

## License

Axiolex is available under the [GNU GPLv3](https://github.com/vrraj/axiolex/blob/main/LICENSE).

Commercial licensing is also available — ai0musings99@gmail.com
