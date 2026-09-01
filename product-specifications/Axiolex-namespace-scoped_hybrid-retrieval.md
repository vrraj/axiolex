# Axiolex Namespace-Scoped Hybrid Retrieval Specification

## Objective

Add namespace-based retrieval to Axiolex so that BM25S and ColBERT
search only capabilities belonging to the namespaces requested by the
client.

Namespace filtering is a **hard retrieval constraint**, not a
post-ranking filter.

## Catalog Model

Each normalized discovery record in Redis gains:

``` yaml
namespaces:
  - finance.market_data
  - finance.trading
```

Namespaces originate from the provider configuration for dynamically
discovered MCP tools, or from the applicable configuration for static
tools.

The existing Redis runtime data and catalog-version mechanism remain
unchanged.

## Index Architecture

Maintain the existing architecture:

``` text
Redis normalized catalog
        ↓
Axiolex Service
        ↓
load discovery documents
        ↓
┌─────────────────────┐
│ ONE BM25S index     │
│ ONE ColBERT index   │
└─────────────────────┘
        +
namespace → document/tool ID mapping
```

Do **not** create separate BM25S or ColBERT indexes per namespace.

Indexes remain derived, in-process structures and are rebuilt when the
Redis catalog version changes.

## Namespace Membership

During index construction, build a mapping such as:

``` python
namespace_docs = {
    "finance.market_data": {"tool_1", "tool_7", "tool_12"},
    "finance.trading": {"tool_3", "tool_7", "tool_19"},
    "research.web": {"tool_21", "tool_22"},
}
```

A capability may belong to multiple namespaces.

## Retrieval

A discovery request accepts:

``` json
{
  "query": "get NVIDIA historical prices",
  "namespaces": ["finance.market_data"]
}
```

Axiolex must:

``` text
validate requested namespaces
        ↓
resolve namespace → eligible document IDs
        ↓
        ┌─────────────────────────┐
        ↓                         ↓
BM25S retrieval              ColBERT retrieval
using eligibility mask       using eligible doc_ids
        ↓                         ↓
        └───────────┬─────────────┘
                    ↓
              hybrid fusion
                    ↓
                 top-k
```

For **BM25S**, convert the eligible document set into the corresponding
retrieval `weight_mask`.

For **ColBERT**, restrict retrieval to the corresponding eligible
`doc_ids`.

For multiple namespaces, eligibility is the **union** of their document
sets.

For example:

``` text
finance.market_data → {1, 5, 9}
research.web        → {8, 10, 12}

requested both
        ↓
eligible = {1, 5, 8, 9, 10, 12}
```

Both BM25S and ColBERT operate against that same eligible set.

## Hard-Boundary Requirement

Tools outside the requested namespaces must **not participate in BM25S
retrieval, ColBERT retrieval, or hybrid fusion**.

Do not implement:

``` text
global retrieval
→ global top-k
→ namespace filter
```

Implement:

``` text
namespace eligibility
→ constrained BM25S + constrained ColBERT
→ hybrid fusion
→ top-k
```

## API / SDK

The thin Axiolex SDK sends the query and namespaces to the central
Axiolex service over HTTP:

``` python
results = axiolex.discover(
    query="get NVIDIA historical prices",
    namespaces=["finance.market_data"]
)
```

The SDK does not access Redis, construct indexes, load ColBERT, or
perform retrieval locally.

## Failure Behavior

Invalid namespaces must fail explicitly.

Axiolex must not silently:

-   remove an invalid namespace;
-   fall back to global retrieval;
-   search additional namespaces when scoped retrieval fails.

## Core Design Rule

> **One catalog. One BM25S index. One ColBERT index. Namespaces define
> the eligible capability set before retrieval. BM25S and ColBERT search
> only that set, and only those results participate in hybrid fusion.**

This provides namespace isolation without multiplying indexes or
changing the existing Redis → in-memory-index architecture.
