# Axiolex Central Capability Discovery — Architecture Specification

## 1. Objective

Extend **Axiolex** into a central capability discovery and routing layer that can be shared across multiple AI applications, agents, and clients within an enterprise.

Axiolex provides a common catalog of available MCP providers and their dynamically discovered capabilities, organizes those providers through managed namespaces, and allows consuming applications to retrieve only the capabilities relevant to their context and user request.

Individual applications should not need to maintain their own MCP tool inventories, discovery infrastructure, retrieval indexes, or routing logic.

Applications integrate with Axiolex through a lightweight SDK and request capability discovery within one or more namespaces.

```text id="ptd7q4"
Enterprise MCP Providers
        ↓
Axiolex Discovery + Normalization
        ↓
Central Capability Catalog
        ↓
Namespace-Scoped Retrieval
        ↓
BM25S / Optional ColBERT Ranking
        ↓
Axiolex API + SDK
        ↓
AI Applications / Agents / Clients
```

Axiolex remains a **discovery and routing layer**.

It does not execute downstream tools.

---

## 2. Architectural Principle

Axiolex follows a centralized service / thin-client architecture:

**Axiolex Service = intelligence + catalog + discovery + ranking**

**Axiolex SDK = thin client contract**

The **Axiolex Service** owns:

- namespace management;
- MCP provider configuration;
- MCP discovery and normalization;
- the central capability catalog;
- Redis runtime/catalog state;
- retrieval indexes;
- BM25S retrieval;
- optional ColBERT reranking.

The **Axiolex SDK** provides applications, agents, and clients with a lightweight interface to the central service.

It does **not** maintain its own capability catalog, retrieval index, MCP discovery runtime, provider registry, or routing intelligence.

```text id="3ukb30"
                    AXIOLEX SERVICE
        ┌─────────────────────────────────┐
        │ Namespace Registry              │
        │ MCP Provider Registry           │
        │ MCP Discovery + Normalization   │
        │ Central Capability Catalog      │
        │ BM25S / ColBERT Ranking         │
        └────────────────┬────────────────┘
                         │
                    Axiolex API
                         │
                 Thin Axiolex SDK
                         │
             ┌───────────┼───────────┐
             ↓           ↓           ↓
          AI App      AI Agent     AI Client
```

This ensures that consuming applications use the same current capability catalog and routing behavior without duplicating Axiolex infrastructure.

### Core principle

**Centralized discovery and ranking; decentralized execution.**

Axiolex determines which capabilities are relevant.

The consuming application remains responsible for deciding what to expose to its LLM and what, if anything, to execute.

---

## 3. Problem Being Solved

As enterprises deploy more AI applications, capabilities will increasingly be distributed across multiple MCP servers and other systems.

An enterprise may expose capabilities across areas such as:

```text id="s3gr69"
Finance
HR
Legal
Supply Chain
Manufacturing
Customer Service
IT
Security
Research
Market Data
```

Without a shared discovery layer, each AI application would need to:

- maintain MCP server configurations;
- discover and normalize tools independently;
- maintain its own capability catalog;
- maintain its own retrieval index;
- expose potentially large tool catalogs to its LLM;
- independently solve capability selection and tool ambiguity.

As the number of applications, MCP providers, and tools increases, this duplication becomes difficult to manage and increases the possibility of irrelevant or semantically similar tools competing for selection.

Axiolex provides one central capability discovery layer that applications can query according to their own scope.

---

## 4. Namespace Model

Use **namespaces** rather than separate `domain` and `function` fields.

A namespace represents a logical discovery scope.

Examples:

```text id="7m5pko"
finance.market_data
finance.trading
finance.reporting

supply_chain.procurement
supply_chain.inventory

manufacturing.process
manufacturing.predictive_analytics

hr.benefits
legal.contracts

research.web
enterprise.utilities
```

Namespaces intentionally do not impose a rigid enterprise taxonomy.

Depending on the organization, they may represent:

- business functions;
- capability areas;
- organizational boundaries;
- application scopes;
- technical capability groups.

Axiolex does not need to understand the semantic hierarchy.

To Axiolex:

**Namespace = logical scope within which capabilities can be discovered.**

Namespaces are centrally registered and referenced using exact canonical IDs.

---

## 5. MCP Provider and Namespace Relationship

Namespaces are assigned to **MCP providers**, not manually to individual MCP tools.

This is important because Axiolex does not know an MCP provider's tool inventory before discovery.

The lifecycle is:

```text id="kvdb1p"
MCP Provider
     ↓
Configured Namespace(s)
     ↓
Dynamic MCP Tool Discovery
     ↓
Discovered Tools Inherit Provider Namespaces
     ↓
Normalization
     ↓
Redis Catalog
     ↓
Retrieval Index
```

For example:

```yaml id="ofkw1v"
id: aina_markets

namespaces:
  - finance.market_data
  - finance.trading
```

If Aina Markets dynamically exposes 15 tools through MCP, Axiolex discovers those tools and associates the provider namespaces with each normalized capability.

There is no requirement to know or configure those 15 tool names beforehand.

The relationship is many-to-many:

```text id="pkffg7"
One MCP provider → multiple namespaces

One namespace → multiple MCP providers
```

The namespace restricts the discovery space.

BM25S and optional ColBERT ranking determine which dynamically discovered capabilities within that space best match the actual request.

---

## 6. Namespace Registry

Add a new configuration registry in the same configuration area as the existing MCP provider registry.

```text id="lhd34n"
config/
    mcp_providers.yaml
    namespaces.yaml
```

`namespaces.yaml` is the authoritative registry of valid namespaces.

Example:

```yaml id="ajrv7g"
namespaces:

  - id: finance.market_data
    name: Market Data
    description: >
      Market prices, historical data, securities data,
      and related financial-market capabilities.
    enabled: true

  - id: finance.trading
    name: Trading
    description: >
      Trading and brokerage-related capabilities.
    enabled: true

  - id: supply_chain.procurement
    name: Procurement
    description: >
      Procurement, sourcing, supplier, and material
      purchasing capabilities.
    enabled: true

  - id: manufacturing.predictive_analytics
    name: Manufacturing Predictive Analytics
    description: >
      Predictive analytics capabilities related to
      manufacturing processes and operations.
    enabled: true

  - id: research.web
    name: Web Research
    description: >
      General external web research and search capabilities.
    enabled: true
```

The namespace `id` is the canonical value used throughout Axiolex.

Namespace IDs must be unique.

---

## 7. MCP Provider Configuration

Extend the existing `mcp_providers.yaml` format with a `namespaces` field.

Existing provider configuration remains responsible for connection, authentication, transport, feature, and limit information.

Namespaces add the provider's logical discovery scopes.

Example:

```yaml id="bz58wh"
providers:

  - id: alphavantage_finance
    name: Alpha Vantage MCP
    enabled: true

    namespaces:
      - finance.market_data

    transport: streamable-http
    endpoint: https://mcp.alphavantage.co/mcp

    args: []

    auth:
      type: api_key
      key_param: apikey
      secret_env: ALPHAVANTAGE_API_KEY

    features:
      supports_streaming: true

    limits:
      max_page_size: 15
      max_requests_per_minute: 60
      max_results: 100
      timeout_seconds: 10
```

A provider may participate in multiple namespaces:

```yaml id="89y79q"
  - id: aina_markets
    name: Aina Markets
    enabled: true

    namespaces:
      - finance.market_data
      - finance.trading

    transport: streamable-http
    endpoint: http://localhost:9001/mcp

    args: []

    auth:
      type: none
      key_param: api_key
      secret_env: null

    features:
      supports_streaming: false

    limits:
      max_page_size: 50
      max_requests_per_minute: 60
      max_results: 100
      timeout_seconds: 10
```

A general-purpose provider can use a cross-cutting namespace:

```yaml id="6r0jkp"
  - id: tavily_mcp
    name: Tavily
    enabled: true

    namespaces:
      - research.web

    transport: streamable-http
    endpoint: https://mcp.tavily.com/mcp
```

---

## 8. Discovery and Normalization

Provider namespaces must propagate automatically during MCP discovery.

Conceptually:

```text id="agf2tf"
Provider Configuration
    │
    ├── provider_id
    ├── namespaces[]
    └── connection metadata
            ↓
       MCP Discovery
            ↓
     Discovered Tools
            ↓
       Normalization
            ↓
Normalized Capability
    │
    ├── provider_id
    ├── tool_name
    ├── tool description/schema
    ├── namespaces[]
    ├── runtime metadata
    └── artifact metadata
```

The discovered MCP tool remains the source of truth for tool name, description, schema, and other MCP-provided capability information.

Axiolex enriches that discovered information with its own provider, namespace, runtime, and retrieval metadata.

No individual MCP tool definitions need to be maintained manually in `mcp_providers.yaml`.

---

## 9. Configuration Validation

Namespace references must be validated strictly.

When Axiolex loads `mcp_providers.yaml`, every referenced namespace must exist in `namespaces.yaml`.

For example:

```yaml id="7ejqdt"
namespaces:
  - finance.marketdata
```

must fail if the registered namespace is:

```text id="1xmb1p"
finance.market_data
```

Axiolex must not:

- silently repair namespace IDs;
- infer alternatives;
- substitute another namespace;
- ignore invalid namespace references.

The error should clearly identify both the invalid namespace and provider.

Example:

```text id="v18pd6"
Unknown namespace 'finance.marketdata'
referenced by provider 'aina_markets'.
```

Duplicate namespace IDs must also fail validation.

---

## 10. Failure Handling

Do not introduce fallback behavior for namespace, provider-discovery, catalog, configuration, or retrieval failures.

Failures must be explicit and observable.

Examples include:

```text id="66ql35"
Invalid namespace
Duplicate namespace
Provider references nonexistent namespace
Malformed provider configuration
MCP provider discovery failure
Malformed MCP response
Redis write failure
Retrieval index update failure
Retrieval execution failure
SDK/API request failure
```

The system should surface the actual failure to the appropriate calling layer.

Do not silently:

```text id="7z86oa"
Search all namespaces
Drop namespace constraints
Reuse stale provider metadata
Substitute another provider
Ignore failed discovery
Treat failed indexing as successful
Return unrelated capabilities
```

Silent fallback behavior is particularly dangerous in capability routing because it can produce an apparently successful result from the wrong discovery scope.

---

## 11. Namespace-Scoped Retrieval

Applications can specify one or more namespaces when requesting discovery.

Example:

```python id="qddghx"
results = axiolex.discover(
    query=user_prompt,
    namespaces=[
        "finance.market_data",
        "research.web"
    ]
)
```

The retrieval lifecycle becomes:

```text id="dyot24"
User Request
     ↓
Requested Namespace(s)
     ↓
Eligible Catalog Capabilities
     ↓
BM25S Retrieval
     ↓
Optional ColBERT Reranking
     ↓
Ranked Capabilities
     ↓
Calling Application
```

Namespaces reduce the eligible capability space.

Retrieval and ranking determine which capabilities within that space best match the user request.

This keeps namespace selection and semantic tool selection as separate concerns:

```text id="osb1zv"
Namespace
    ↓
Where should Axiolex search?

Retrieval / Ranking
    ↓
Which capabilities are most relevant?
```

---

## 12. Discovery Response

Axiolex should preserve its existing runtime and artifact metadata while adding namespace information to normalized capability results.

Conceptually:

```json id="lq9o0s"
{
  "provider_id": "aina_markets",
  "tool_name": "get_stock_quote",
  "namespaces": [
    "finance.market_data",
    "finance.trading"
  ],
  "score": 0.87,
  "runtime": {},
  "artifact": {}
}
```

The `tool_name` shown here is illustrative.

It is obtained dynamically through MCP discovery and is not configured manually in Axiolex.

---

## 13. Axiolex Python SDK

The Axiolex PyPI package should remain deliberately small.

Its purpose is to provide a convenient client contract for applications using the central Axiolex service.

Example:

```python id="cf34qy"
from axiolex import Axiolex

axiolex = Axiolex(
    base_url="http://axiolex.internal"
)

tools = axiolex.discover(
    query=user_prompt,
    namespaces=["supply_chain.procurement"]
)
```

The SDK may expose operations such as:

```text id="pnnh26"
discover()
list_namespaces()
get_namespace()
```

as required by application integration.

The SDK should not contain:

```text id="jtv1vw"
Redis catalog
BM25S index
ColBERT models
MCP provider discovery
Provider registry
Namespace registry
Central routing logic
```

Those remain service-side concerns.

Therefore:

**Axiolex Service = intelligence + catalog + discovery + ranking**

**Axiolex SDK = thin client contract**

---

## 14. MCP Provider Management UX

Extend the existing MCP Server management interface to support namespace assignment.

When creating or editing an MCP provider, add a **Namespaces** section.

The user should be able to select one or more registered namespaces.

Example:

```text id="4bykn8"
Namespaces

[x] finance.market_data
[x] finance.trading
[ ] finance.reporting
[ ] research.web
```

Namespace selection should use the central namespace registry.

Do not allow arbitrary namespace strings to be entered directly into MCP provider configuration.

The MCP provider detail screen should display its currently assigned namespaces.

The provider management UX continues to manage connection information such as:

```text id="lv1z39"
Provider name
Transport
Endpoint / command
Authentication
Features
Limits
Namespaces
```

---

## 15. Namespace Management UX

Add a separate **Namespaces** management interface.

The user should be able to:

- view registered namespaces;
- create a namespace;
- edit a namespace;
- enable or disable a namespace;
- view which MCP providers reference a namespace.

Suggested fields:

```text id="5k54s1"
Namespace ID
Display Name
Description
Enabled
Associated Providers
```

Example:

```text id="7k9afl"
finance.market_data

Market Data

Market prices, historical data, securities data,
and related market-information capabilities.

Providers:
  Alpha Vantage MCP
  Aina Markets
```

### Referential integrity

A namespace referenced by an active MCP provider must not simply be deleted.

Deletion should fail and identify the providers referencing it.

Example:

```text id="ym97m7"
Cannot delete namespace 'finance.market_data'.

Referenced by:
- alphavantage_finance
- aina_markets
```

The provider references must first be removed or changed.

---

## 16. Modularity

Keep namespace management, provider management, MCP discovery, catalog storage, retrieval, and client integration as separate concerns.

Conceptually:

```text id="1bbvng"
Namespace Registry
        ↓
Provider Registry
        ↓
MCP Discovery
        ↓
Normalization
        ↓
Central Capability Catalog
        ↓
Retrieval / Ranking
        ↓
Axiolex API
        ↓
Thin SDK
        ↓
Applications / Agents / Clients
```

### Module boundaries

**Namespace Registry**

Owns canonical namespace definitions and validation.

**Provider Registry**

Owns MCP provider configuration and namespace associations.

**MCP Discovery**

Connects to configured providers and dynamically discovers capabilities.

**Normalization**

Converts discovered MCP capabilities into Axiolex catalog records and attaches provider/namespace metadata.

**Catalog**

Maintains discovery and runtime capability information.

**Retrieval**

Performs BM25S retrieval and optional ColBERT reranking against eligible capabilities.

**API**

Exposes central Axiolex functionality to consumers.

**SDK**

Provides a lightweight Python client contract.

These boundaries should remain independent enough that one component can evolve without requiring unrelated components to be redesigned.

---

## 17. Phase 1 Scope

The initial implementation should remain focused.

Phase 1 consists of:

1. Add `namespaces.yaml`.
2. Add namespace registry loading and strict validation.
3. Add `namespaces[]` to MCP provider configuration.
4. Propagate provider namespaces to dynamically discovered MCP tools.
5. Store namespace metadata with normalized catalog records.
6. Support namespace filtering during capability retrieval.
7. Return namespace metadata with ranked results.
8. Extend MCP Provider Management UX with namespace selection.
9. Add Namespace Management UX.
10. Expose namespace-aware discovery through the Axiolex API.
11. Keep the PyPI SDK as a thin client for the central service.
12. Add tests for namespace validation, propagation, retrieval filtering, and configuration failures.

Do not expand Phase 1 into tool execution, authorization, orchestration, or enterprise governance.

---

# Future Extensions

The following capabilities can be added later without changing the core architecture.

## Automatic Tool-Level Namespace Classification

Provider-level namespaces intentionally provide a broad discovery boundary.

In the future, Axiolex could inspect dynamically discovered MCP tool names, descriptions, annotations, and schemas and classify individual tools into more specific namespaces.

For example:

```text id="e5u1oq"
Aina Markets
Provider namespaces:
    finance.market_data
    finance.trading

            ↓ MCP discovery

Tool A → finance.market_data
Tool B → finance.market_data
Tool C → finance.trading
Tool D → finance.trading
```

This preserves dynamic MCP discovery without requiring tool names to be known or configured beforehand.

---

## Hierarchical Namespace Queries

Support namespace patterns such as:

```text id="z7uwcv"
finance.*
supply_chain.*
manufacturing.*
```

while retaining exact canonical namespace definitions internally.

---

## Application Profiles

Applications could register their normal capability scopes.

Example:

```text id="hh8xfv"
Procurement AI

Default namespaces:
  - supply_chain.procurement
  - supply_chain.inventory
  - research.web
```

The application could then request discovery using its profile while still overriding namespaces for individual requests.

---

## Automatic Namespace Selection

General-purpose AI applications may not always know the appropriate namespace.

Axiolex could eventually determine likely namespaces from the request:

```text id="g9k2zg"
User Request
      ↓
Namespace Selection
      ↓
finance.market_data
research.web
      ↓
Capability Retrieval
      ↓
Ranking
```

This should be a deliberate future capability rather than a silent fallback when an explicitly requested namespace fails.

---

## Namespace-Aware Authorization

Authorization policies could eventually determine which applications, agents, users, or service identities are permitted to discover particular namespaces.

Discovery authorization and execution authorization should remain separate concerns.

---

## Capability Lifecycle Metadata

The central catalog could eventually track:

```text id="fvg4rx"
version
owner
environment
status
deprecation
health
last_discovered
```

This would allow Axiolex to evolve toward broader enterprise capability management without changing the underlying discovery model.

---

## Additional Capability Types

The same namespace and retrieval architecture could eventually organize more than MCP tools.

Possible capability sources include:

```text id="s5duy6"
MCP tools
REST APIs
A2A agents
Workflows
Documents
Datasets
Models
Internal services
```

All could ultimately participate in the same discovery model:

```text id="xphfkd"
Capability Sources
       ↓
Discovery / Registration
       ↓
Normalization
       ↓
Namespace-Aware Catalog
       ↓
Retrieval + Ranking
       ↓
Applications
```

---

## Enterprise Capability Catalog

Over time, Axiolex can evolve from MCP-oriented tool routing into a broader enterprise capability discovery layer shared across AI applications.

The fundamental architectural boundary should remain unchanged:

**Axiolex Service = intelligence + catalog + discovery + ranking**

**Axiolex SDK = thin client contract**

and:

**Centralized discovery and ranking; decentralized execution.**

Axiolex determines which capabilities are relevant.

The consuming application determines what gets executed.