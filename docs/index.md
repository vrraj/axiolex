---
layout: default
title: "Context Engineering for Tool-Heavy Agents: Lexical Routing"
description: "A lightweight BM25S-powered lexical retrieval and tool-routing package for Python applications, REST services, LLM systems, and MCP-based tool workflows."
---

# Axiolex

<p align="left">
  <a href="https://pypi.org/project/axiolex/">
    <img src="https://img.shields.io/pypi/v/axiolex?color=blue&logo=pypi&logoColor=white" alt="PyPI - Version">
  </a>
  <a href="https://github.com/vrraj/axiolex/releases">
    <img src="https://img.shields.io/github/v/release/vrraj/axiolex?label=github%20release&color=orange&logo=github" alt="GitHub Release">
  </a>
  <a href="https://github.com/vrraj/axiolex/actions">
    <img src="https://github.com/vrraj/axiolex/actions/workflows/ci.yml/badge.svg" alt="CI Status">
  </a>
</p>

A lightweight **BM25S-powered lexical retrieval package** for Python applications, REST services, LLM systems, and MCP-based tool workflows.

Use it to route LLM tool calls, filter MCP-discovered tools, search documents, and build fast lexical retrieval layers without running a vector database.

The ingestion model is intentionally flexible: combine your own YAML tool registry, MCP-discovered tools, and documents or tool definitions injected through the REST API into one in-memory BM25S index. The retriever can then be tuned to return the most relevant tool or tool set before anything is passed to the LLM.

## Why this exists

Tool-heavy agentic systems can quickly run into context bloat. As tool registries grow, passing every tool definition, description, and parameter schema into the LLM increases token usage, adds latency, and can make tool selection less reliable.

`axiolex` acts as a small deterministic relevance layer before prompt assembly. It is designed for applications where many tools are available, but only a small subset is relevant for any given request.


**Example from a trading agent built with this routing layer:**


<div style="display: flex; gap: 16px;">
  <div style="flex: 1;">
    <img src="https://raw.githubusercontent.com/vrraj/axiolex/main/images/agent-with-tool-routing.png" />
    <p align="center"><em>With lexical routing (~600 tokens, 1 tool)</em></p>
  </div>
  <div style="flex: 1;">
    <img src="https://raw.githubusercontent.com/vrraj/axiolex/main/images/agent-without-tool-routing.png" />
    <p align="center"><em>Without routing (~3.6K tokens, 20+ tools)</em></p>
  </div>
</div>

## Primary use case: LLM and MCP tool routing

Modern agentic systems increasingly discover tools through **Model Context Protocol (MCP)**, internal registries, and service APIs. MCP standardizes tool discovery, but it does not decide which tools should be passed to the LLM for a specific user request.

That selection step still belongs in the MCP client, host application, or orchestrator.

```text
Discover / Load → Inject → Index → Filter → Focused LLM Context
```

In practice:

```text
YAML Tool Registry + MCP-Discovered Tools + Internal Tool Definitions
→ Inject into BM25S Index (REST or in-process)
→ Query-Time Tool Filtering
→ Focused LLM Context
```

> Tools can come from YAML, MCP discovery, or internal registries. The client or orchestration layer maps them into BM25S documents and injects them into a unified in-memory index. At query time, BM25S filters the relevant subset before the LLM sees the tool list.

## Flexible ingestion architecture

**Architecture overview:**


![BM25S Retriever LLM Architecture](../images/axiolex-llm.png)

<center><em>BM25S-based lexical routing layer showing ingestion from YAML, MCP, and REST sources, followed by query-time filtering before LLM context assembly.</em></center>

The retriever is not limited to one source of truth. A single BM25S index can consolidate:

- Your own YAML-based tool or document registry
- MCP-discovered tools mapped by the client or orchestrator
- Internal tool definitions from application code or service registries
- Documents or tool definitions injected dynamically through the REST API

This allows static definitions and runtime-discovered tools to participate in the same lexical ranking flow. You can tune temperature, cutoff thresholds, keywords, and tool descriptions to control whether the router returns one highly specific tool or a small candidate set for the LLM.

## What you get

- **Python retrieval library** for programmatic lexical search and tool routing
- **YAML-backed document/tool registry support** for static tool definitions and document collections
- **Runtime document/tool injection** for MCP-discovered tools, internal registries, and API-supplied context
- **REST service** for remote retrieval, dynamic in-memory indexing, and document/tool management
- **HTTP client** for connecting applications to the BM25S REST service, including remote deployments and service-oriented architectures
- **BM25S + PyStemmer** for fast stemming-aware lexical matching
- **Softmax relevance scoring** with configurable temperature and cutoff filtering
- **Normalized response schema** with scores, rankings, metadata, and settings
- **Demo Web UI** for testing retrieval behavior, tuning parameters, and refining tool descriptions

## Install

```bash
pip install axiolex
```

For the REST service extras:

```bash
pip install "axiolex[server]"
```

## Quick example

```python
from axiolex import BM25SRetriever, Document

retriever = BM25SRetriever()

retriever.add_documents([
    Document(
        id="create_order",
        title="Create Order",
        content="Place a buy or sell order for a stock or equity trade.",
        keywords=["place order", "buy order", "sell order", "stock trade"],
        metadata={"category": "trading", "type": "tool"},
    ),
    Document(
        id="get_market_movers",
        title="Get Market Movers",
        content="Retrieve top gaining, losing, or most active market movers.",
        keywords=["market movers", "top gainers", "top losers", "most active"],
        metadata={"category": "trading", "type": "tool"},
    ),
])

results = retriever.retrieve_documents(
    query="place a limit buy order",
    temperature=0.5,
    ignore_zero=True,
    llm_tools_cutoff=10.0,
)

for doc in results["documents"]:
    print(doc["id"], doc["title"], doc["score_percentage"])
```

## Interactive tuning UI

The GitHub repo includes a FastAPI-powered **Demo Web UI** for testing retrieval behavior, inspecting ranked results, adding documents, and tuning retrieval behavior before production use.

The UI is useful for experimenting with parameters such as temperature, softmax cutoff thresholds, keywords, and content/tool descriptions so you can see how ranking changes for real queries.

Use it as a local experimentation environment: load your own YAML documents or tool definitions, inject additional documents or tools through the API, test queries, tune scoring behavior, refine keywords and descriptions, and see exactly how results are ranked before using the settings in production.

See setup instructions in the README: [Demo Web UI](https://github.com/vrraj/axiolex#demo-web-ui)

## Summary

**axiolex** is a lightweight BM25S-based retrieval layer for lexical routing in tool-heavy LLM systems.

It is designed for bounded domains where user intent maps to a known set of tools, workflows, or documents. In these environments, tools are usually described using a finite set of verbs, workflow names, and domain-specific terms. This makes lexical routing predictable, tunable, and explainable.


For example, if a tool is defined as `purchase_order`, the retriever can be configured with keywords such as `buy`, `order`, or `place order` to cover common user phrasing. Because the domain is bounded, these mappings can be explicitly controlled rather than inferred.

Users can try different keywords, descriptions, temperature values, and cutoff thresholds in the included Demo Web UI to see how ranking changes before settling on production defaults.

For broader or more ambiguous domains, this lexical layer can be combined with vector-based retrieval. The trade-off is additional embedding cost, latency, and the possibility of less precise matches.

For tool-heavy agents where precision, explainability, and token control matter, a lexical-first routing layer is often the simplest place to start.


## Links

- [GitHub Repository](https://github.com/vrraj/axiolex)
- [PyPI Package](https://pypi.org/project/axiolex/)
- [Full README](https://github.com/vrraj/axiolex#readme)
- [Setup & Usage](setup-usage.html)
- [Connect Claude Desktop](claude-mcp.html)
- [API Reference](api-reference.html)
- [Document and Tool Ingestion Guide](document-and-tool-ingestion-guide.html)
- [MCP Providers Guide](mcp_providers.html)
- [Medium Story](https://medium.com/@vr.rajkumar99/context-engineering-for-tool-heavy-agents-lexical-routing-c1b0ebad7495)
- [Medium Story- AI computational complexitty and the economics of approximation](https://medium.com/@vr.rajkumar99/the-p-vs-np-wall-why-ais-energy-crisis-may-actually-be-a-math-problem-46390ca3b853)
