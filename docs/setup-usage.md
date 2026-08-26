---
layout: default
title: "Setup & Usage | AxioLex"
description: "Install, configure, and run AxioLex as a PyPI package, management platform, or automated pipeline."
---

# AxioLex Setup & Usage Guide

## Summary of approaches

AxioLex can be used three ways. Pick the one that matches how you want to integrate it:

- **Install from PyPI** — embed the `axiolex` package or CLI in an existing Python project. No repo checkout, no web UI, just the runtime and the command-line tools.
- **Run the management platform** — start the FastAPI server and web UI to onboard MCP tool providers, inspect the catalog, tune search, and refresh indexes interactively.
- **Automate via API or CLI** — script provider registration, secret storage, tool discovery, and catalog refresh. Everything in the UI is also a REST endpoint.

| Approach | Best for | What you get |
|---|---|---|
| PyPI install | Library/CLI use in another project | `axiolex`, `axiolex-server`, `axiolex-mcp-server`, `axiolex-index` |
| Management platform | Interactive tool onboarding and tuning | FastAPI UI at `http://localhost:9700` plus MCP discovery at `http://localhost:9701/mcp` |
| Automation | CI/CD, scheduled refresh, agent-driven setup | `POST /mcp-providers`, `GET /mcp-providers/{id}/discover`, `axiolex-index refresh` |

## Install from PyPI

```bash
pip install axiolex
```

With optional capabilities:

```bash
# FastAPI UI / REST server
pip install "axiolex[server]"

# Optional hybrid ColBERT search
pip install "axiolex[colbert]"

# Everything
pip install "axiolex[server,colbert]"
```

Entry points installed:

- `axiolex` — main CLI
- `axiolex-server` — FastAPI web / REST server
- `axiolex-mcp-server` — MCP discovery server
- `axiolex-index` — Redis catalog refresh CLI

## Add-on to an existing application

You can add AxioLex to an existing application without making it a monolith. Pick the pattern that matches how much of the platform you actually need.

### Embedded library

Install only the base package in your existing app:

```bash
pip install axiolex
```

Use the Python API to search the catalog:

```python
from axiolex.core.retriever import retrieve_documents

results = retrieve_documents(
    "find a finance research tool",
    max_results=5,
    hybrid_search=False,
)
```

This needs only a Redis connection. It does **not** start FastAPI or the web UI.

### Management sidecar

If admins need a web UI to add MCP providers and refresh the catalog, run the server separately:

```bash
pip install "axiolex[server]"
axiolex-server --config settings.yaml --port 9700
```

Your existing app stays unchanged and still uses the `axiolex` library. Both the app and the sidecar point at the same Redis.

### When to use which

| Pattern | Choose when | Footprint |
|---|---|---|
| Embedded library | Existing app just needs tool/document retrieval | Base package only |
| Management sidecar | Admins need a UI, but the app should stay lightweight | Base package + `[server]` extra |
| Full standalone | You want a local demo or an all-in-one service | `make start` (Redis + FastAPI + MCP server) |

### Optional hybrid search

Add ColBERT only if you need semantic + lexical search. It pulls in ONNX Runtime and downloads a model:

```bash
pip install "axiolex[colbert]"
export AXIOLEX_HYBRID_ENABLED=true
```

This is completely optional; the base package is lexical-only and much lighter.

## Run the management platform

The platform requires Redis. The quickest path from a checkout is:

```bash
make start        # Redis + FastAPI server + MCP discovery server
```

Then open the web UI at `http://localhost:9700` and the MCP discovery endpoint at `http://localhost:9701/mcp`.

From the UI you can:

- Add, edit, enable, or disable MCP providers
- Store provider secrets in the encrypted secret store
- Retrieve tools per provider
- Tune retrieval parameters and run search
- Reload and reindex the catalog

## Automate with the API or CLI

Every management action is available over HTTP. A typical provider onboarding flow:

1. Add the provider:

```bash
curl -X POST http://localhost:9700/mcp-providers \
  -H "Content-Type: application/json" \
  -d '{
    "id": "tavily",
    "name": "Tavily Search",
    "transport": "streamable_http",
    "endpoint": "https://...",
    "auth": {"type": "api_key", "key_param": "api_key", "secret_env": "TAVILY_API_KEY"},
    "enabled": true
  }'
```

2. Store the secret:

```bash
curl -X POST http://localhost:9700/mcp-providers/tavily/secret \
  -H "Content-Type: application/json" \
  -d '{"secret": "<TAVILY_API_KEY>"}'
```

3. Discover and cache tools:

```bash
curl http://localhost:9700/mcp-providers/tavily/discover
```

4. Refresh the search index:

```bash
curl -X POST http://localhost:9700/documents/reindex-bm25s
```

For full catalog rebuilds from YAML plus all enabled providers, use the CLI:

```bash
axiolex-index refresh \
  --tools-file source_files/tools_list.yaml \
  --providers-file source_files/mcp_providers.yaml
```

## Environment quick reference

| Variable | Purpose | Default |
|---|---|---|
| `AXIOLEX_REDIS_HOST` | Redis host | `localhost` |
| `AXIOLEX_REDIS_PORT` | Redis port | `6380` |
| `AXIOLEX_REDIS_DB` | Redis DB index | `0` |
| `AXIOLEX_TOOLS_FILE` | Local tool catalog YAML | `source_files/tools_list.yaml` |
| `AXIOLEX_MCP_PROVIDERS_FILE` | MCP provider YAML | `source_files/mcp_providers.yaml` |
| `AXIOLEX_SECRET_MASTER_KEY` | Master key for encrypted secret store | required at runtime for secrets |
