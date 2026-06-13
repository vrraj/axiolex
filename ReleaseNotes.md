# Release Notes

## Version 1.0.2 — Badge Fix

### Changes
- Fixed GitHub Release badge URL to use `/v/release` instead of `v-release`
- No functional changes - badge display fix only

---

## Version 1.0.0 — Initial Public Release

### Overview

`axiolex` is a lightweight BM25S-powered lexical retrieval and routing layer for Python applications, REST services, LLM systems, and MCP-based tool workflows.

This is the first public release. The complete API surface is documented in [docs/api-reference.md](https://vrraj.github.io/axiolex/api-reference.html).

---

## Core Capabilities

### BM25S Retrieval
- Primary `BM25SRetriever` class for in-process document indexing and retrieval
- BM25S algorithm with PyStemmer for efficient stemming-aware lexical matching
- Softmax scoring with configurable temperature parameter
- Cutoff filtering for low or zero-relevance results
- YAML-backed document/tool registry support

### REST Service
- FastAPI-powered REST API for remote retrieval
- HTTP client (`BM25SClient`) for service integration
- Dynamic document injection and management
- Search settings endpoint for runtime configuration
- Demo Web UI for testing and parameter tuning

### Tool Routing
- Designed for LLM and MCP-based tool filtering
- Acts as a relevance layer between tool discovery and prompt assembly
- Reduces context bloat by selecting a small, relevant subset of tools
- Supports tools from YAML, MCP discovery, and internal registries
- Deterministic lexical scoring for explainable tool selection

### Response Contract
- Normalized response schema with scores, rankings, and metadata
- Pydantic models for type-safe response handling
- Consistent interface across Python API and REST service

### Configuration
- `BM25SSettings` for retrieval parameters
- YAML configuration file support
- Environment variable support
- Runtime setting updates via REST API

---

## Documentation Structure

- **[README.md](https://github.com/vrraj/axiolex#readme)** — Quick start and high-level overview
- **[docs/api-reference.md](https://vrraj.github.io/axiolex/api-reference.html)** — Complete method signatures and response contracts
- **[examples/](https://github.com/vrraj/axiolex/tree/main/examples)** — Usage examples and REST API demonstrations
- **[ReleaseNotes.md](https://github.com/vrraj/axiolex/blob/main/ReleaseNotes.md)** — Version history

---

## Public API Surface

Stable entry points:
- `BM25SRetriever(settings, document_file)` — In-process lexical retriever and router
- `BM25SRetriever.add_documents(documents)` — Index documents
- `BM25SRetriever.retrieve_documents(query, temperature, ignore_zero, llm_tools_cutoff)` — Search
- `BM25SClient(base_url)` — HTTP client for REST service
- `BM25SClient.retrieve(...)` — Remote search
- `BM25SClient.add_document(...)` — Add documents via API
- `BM25SClient.get_documents()` — List documents
- `BM25SClient.delete_document(doc_id)` — Delete documents
- `BM25SClient.get_settings()` — Read settings
- `BM25SClient.update_settings(...)` — Update settings

Stable response contracts:
- `Document` — Document representation
- `RetrieveResponse` — Search results with documents, scores, and settings
- `BM25SSettings` — Retrieval configuration

---

## Compatibility

- Python 3.10+
- BM25S and PyStemmer dependencies
- FastAPI and httpx for REST service (optional)
- Jinja2 for Web UI (optional)

---

## Notes

This release establishes the stable 1.x API contract for `axiolex`.

The focus of this release is lexical routing for tool-heavy agentic systems, especially where MCP or large tool registries introduce context and selection challenges.

Backward compatibility will be maintained within the 1.x series.
