# AxioLex — Initial Release

AxioLex is a **fast, deterministic lexical retrieval and tool-routing runtime** for agentic systems. It uses BM25S to select the most relevant tools, documents, and MCP-discovered resources before they are handed to the LLM, with optional hybrid (ColBERT) search for harder semantic matches.

## Highlights

- **Python retrieval library** (`BM25SRetriever`, `Document`) for in-process lexical ranking and tool routing.
- **FastAPI management server** with a web UI for onboarding MCP providers, tuning search, and reindexing the catalog.
- **MCP provider support** over Streamable HTTP and stdio transports, with tool discovery and caching to a shared Redis catalog.
- **Encrypted secret store** for API keys and bearer tokens, backed by AES-256-GCM.
- **Redis-backed shared catalog** so multiple processes can consume the same tool and runtime metadata.
- **BM25S + PyStemmer in-memory index** with softmax scoring, temperature, cutoff filtering, and keyword/ description tuning.
- **Optional hybrid search** with ColBERT for combined semantic and lexical retrieval.
- **CLI entry points**: `axiolex`, `axiolex-server`, `axiolex-mcp-server`, and `axiolex-index`.
- **REST API** for adding providers, discovering tools, storing secrets, reindexing, and retrieving documents.

> AxioLex keeps LLM context windows small and precise by routing only the relevant tools and documents for each request. It is designed to be embedded as a library, run as a sidecar management service, or deployed as a standalone platform.

## Deployment Note

AxioLex is a reference runtime and does not include a built-in identity provider, user store, or tenant authorization model. Deployments should apply authentication, authorization, rate limits, and audit logging appropriate to their REST, MCP, and management interfaces.
