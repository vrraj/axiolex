# Axiolex Distribution Model

## Overview

Axiolex is distributed as two complementary components:

1.  **Axiolex Server** --- the deployable capability discovery and
    retrieval service.
2.  **Axiolex Python SDK** --- a lightweight client used by applications
    and agents to call a deployed Axiolex Server over HTTP.

The full GitHub repository contains the product and deployment assets.
PyPI provides the lightweight Python client contract.

## Distribution Architecture

``` text
Axiolex GitHub Repository
│
├── Axiolex Server
│   ├── REST API
│   ├── MCP provider discovery
│   ├── normalization and catalog refresh
│   ├── Redis catalog
│   ├── namespace management
│   ├── BM25S retrieval
│   ├── ColBERT retrieval
│   └── hybrid ranking/fusion
│
├── Deployment
│   ├── Dockerfile
│   └── Docker Compose
│
└── Python SDK
    ├── HTTP client
    ├── request/response models
    ├── configuration/auth handling
    └── exceptions
```

## Server Distribution

The Axiolex Server is the central runtime. It is deployed by the
platform or application owner and provides capability discovery to
multiple consumers.

The recommended public/self-hosted distribution is through the **GitHub
repository and Docker**.

Typical deployment:

``` bash
docker compose up
```

The deployment starts the Axiolex runtime and its required
infrastructure, including Redis. BM25S and ColBERT indexes remain
derived runtime structures managed by the Axiolex service.

Applications do not require direct Redis access.

## Python SDK Distribution

Publish the lightweight Python SDK to PyPI as:

``` bash
pip install axiolex
```

The SDK communicates with a deployed Axiolex Server over HTTP.

Example:

``` python
from axiolex import Axiolex

client = Axiolex(
    base_url="https://axiolex.company.internal"
)

results = client.discover(
    "get NVIDIA historical prices",
    namespaces=["finance.market_data"],
    top_k=5,
)
```

The SDK should remain lightweight and should **not** require:

-   Redis connectivity or credentials
-   BM25S indexes
-   ColBERT models or indexes
-   MCP provider discovery dependencies
-   catalog-building logic
-   server-side retrieval dependencies

## Enterprise Consumption Model

``` text
Platform / Infrastructure Team
            │
            ↓
    Deploy Axiolex Server
            │
      Redis + Retrieval
            │
            │ HTTP
            ↓
      Axiolex Python SDK
            │
    ┌───────┼────────┐
    ↓       ↓        ↓
 AI Apps   Agents   Services
```

The server centralizes discovery, catalog management, namespace-scoped
retrieval, and ranking. Consumers remain responsible for deciding which
returned capabilities to expose or execute.

## Repository and Package Strategy

For the initial distribution, keep a **single Axiolex GitHub
repository** containing both server and SDK source code.

Use:

-   **GitHub + Docker** for deploying the Axiolex Server.
-   **PyPI (`axiolex`)** for distributing the Python SDK.

A separate `axiolex-sdk` repository or package is not required
initially. The SDK can remain part of the main codebase while being
packaged independently as the lightweight PyPI artifact.

Avoid making the default PyPI installation pull in the complete server
stack, particularly ColBERT/PyTorch/model dependencies. If server
installation through Python becomes useful later, it can be introduced
separately without changing the SDK contract.

## Core Distribution Principle

> **Axiolex is the server product. GitHub/Docker distributes the
> deployable runtime; PyPI distributes the lightweight Python SDK used
> to consume it.**

This keeps the enterprise runtime centralized while giving application
teams a simple, stable integration surface.
