# vrraj-axiolex

[![PyPI - Version](https://img.shields.io/pypi/v/vrraj-axiolex?color=blue&logo=pypi&logoColor=white)](https://pypi.org/project/vrraj-axiolex/)
[![GitHub Release](https://img.shields.io/github/v/release/vrraj/axiolex?label=github%20release&color=orange&logo=github)](https://github.com/vrraj/axiolex/releases)
![CI Status](https://github.com/vrraj/axiolex/actions/workflows/ci.yml/badge.svg)


> **Interactive Demo UI:**  
> The GitHub repo includes a FastAPI-powered **Demo Web UI** for testing retrieval behavior, inspecting ranked results, adding documents, and tuning search parameters. See **[Demo Web UI](#demo-web-ui)** for setup instructions.

**AxioLex: Multi-modal retrieval primitive for agentic infrastructure (Lexical & Neural).**

Currently powered by BM25S + PyStemmer for fast, deterministic lexical retrieval with a routing layer for LLM tools, documents, and hybrid RAG. Designed as an extensible foundation for multi-modal retrieval in agentic systems.

Use it to search documents, route LLM tool calls, filter MCP-discovered tools, and build fast lexical retrieval layers without running a vector database. Future extensions will add neural retrieval capabilities.

**[Quick Start →](#install)**

![BM25S Retriever LLM Architecture](https://raw.githubusercontent.com/vrraj/axiolex/main/images/vrraj-axiolex-llm.png)

<center><em>Figure: BM25S Retriever architecture for tool routing and context filtering</em></center>

## Why this exists

LLM applications often have too much context available: too many tools, too many documents, too many chunks, and too many near-duplicate choices.

This becomes more important in agentic systems where the LLM may have access to large tool registries. As the number of tools grows (20+), this becomes a scaling problem: context size increases, token costs rise, and tool selection becomes less reliable.

> `vrraj-axiolex` gives you a small, deterministic lexical **retrieval layer** that can sit before an LLM and narrow the candidate set **before prompt assembly**.
> This package is designed for applications where many tools are available, but only a small subset is relevant for any given request. It serves as the foundation for multi-modal retrieval in agentic systems.

Typical flow:

```text
User Query / Prompt → BM25S Retrieval with stemming → Filtered Tools / Documents → LLM Context → Execution
```

This becomes especially important in systems with large tool registries, where user intent maps to a **bounded set of actions**: trading, customer support, CRM, finance workflows, operations, and other tool-driven systems.

In these domains, the retrieval problem is often not broad semantic discovery. It is selecting the right tool, command, document, or workflow from a known set of possibilities.

>Clear action language matters: tool names, workflow names, order actions, support tasks, CRM operations, command phrases, and domain-specific vocabulary.

## What you get


- **Multi-modal retrieval primitive** for agentic infrastructure (currently lexical, with neural extensions planned)
- **Python retrieval library** for programmatic lexical search and tool routing
- **YAML-backed document/tool registry support** for static tool definitions and document collections
- **Runtime document/tool injection** for MCP-discovered tools and internal registries
- **REST service** for remote retrieval, dynamic indexing, and document/tool management
- **HTTP client** for connecting applications to the AxioLex REST service (supports remote deployments and service-oriented architectures)
- **BM25S + PyStemmer** for fast stemming-aware lexical matching
- **Softmax relevance scoring** with configurable temperature and cutoff filtering
- **Normalized response schema** with scores, rankings, metadata, and settings
- **Demo Web UI** for testing retrieval behavior, tuning parameters, and refining tool descriptions

## Usage Patterns

### YAML-Based Static Registries
Define tools and documents in YAML files for static, version-controlled registries. Ideal for:
- Pre-defined tool catalogs
- Document collections that don't change frequently
- Version-controlled knowledge bases
- Startup-time loading of known tool sets

```yaml
# tools.yaml
- id: get_customer_profile
  title: Get Customer Profile
  content: Lookup customer account details
  keywords: ["customer", "profile", "account"]
```

### Runtime Document/Tool Injection
Add tools and documents dynamically at runtime. Ideal for:
- MCP-discovered tools from external servers
- Combining static YAML with dynamic tool discovery
- Multi-source document aggregation
- Real-time tool registry updates

```python
# Inject MCP-discovered tools at runtime
mcp_tools = [
    Document(
        id="mcp_tool_1",
        title="MCP Tool",
        content="Description from MCP server",
        keywords=["mcp", "tool"],
        metadata={"source": "mcp"}
    )
]
retriever.add_documents(mcp_tools)
```

### Remote Service-Oriented Architecture
Run AxioLex as a standalone HTTP service. Ideal for:
- Multi-application environments sharing the same index
- Microservices architecture
- Remote deployments (AxioLex on separate server)
- Service-oriented integration patterns

```bash
# Start AxioLex REST service
pip install "vrraj-axiolex[server]"
axiolex-server --config settings.yaml
```

```python
# Connect from any application
from axiolex import BM25SClient
client = BM25SClient("http://remote-server:9700")
results = client.retrieve("query")
```

### MCP Tool Injection
Combine MCP tool discovery with BM25S retrieval. Ideal for:
- Agentic systems with MCP servers
- Filtering MCP tools before LLM context assembly
- Hybrid static + dynamic tool registries

```python
# Load static tools from YAML
retriever = BM25SRetriever(document_file="tools.yaml")

# Inject MCP-discovered tools (your MCP client maps discovered tools to Document objects)
mcp_tools = discover_mcp_tools()  # Your MCP client maps discovered tools to Document objects
retriever.add_documents(mcp_tools)

# Search across both sources
results = retriever.retrieve_documents("user query")
```

## Install

```bash
pip install vrraj-axiolex
```

Links:

- **PyPI:** https://pypi.org/project/vrraj-axiolex/
- **GitHub:** https://github.com/vrraj/axiolex
- **API Documentation:** https://vrraj.github.io/axiolex/

## Quick start

### Option A: Use directly in Python

*For Python applications (most common)*

Requires only the base package (no server extras):

```bash
pip install vrraj-axiolex
```

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

results = retriever.retrieve_documents("place a limit buy order")

for doc in results["documents"]:
    print(doc["id"], doc["title"], doc["score_percentage"])
```

### Option B: Use as a REST service

*For shared services and web UI*

Install with server dependencies (includes FastAPI, Uvicorn, Jinja2):

```bash
pip install "vrraj-axiolex[server]"
```

Start the server:

```bash
axiolex-server --config settings.yaml
```

Search documents:

```bash
curl -X POST http://localhost:9700/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query": "show open customer orders"}'
```

Use the Python HTTP client:

```python
from axiolex import BM25SClient

client = BM25SClient("http://localhost:9700")
results = client.retrieve("show open customer orders")

print(f"Found {len(results['documents'])} matching tools/documents")
```

### Option C: Run the example script

*For quick testing (not production)*

```bash
curl -L -O https://raw.githubusercontent.com/vrraj/axiolex/main/examples/bm25s_basic_usage.py
python bm25s_basic_usage.py
```

## Primary use case: LLM and MCP tool routing

Modern agentic systems increasingly discover tools through **Model Context Protocol (MCP)**, internal registries, and service APIs. MCP standardizes tool discovery, but it does not decide which tools should be passed to the LLM for a specific user request.

That selection step still belongs in the MCP client, host application, or orchestrator.

### Axiolex MCP discovery server

Axiolex can expose its query-time tool selection as a Streamable HTTP MCP
server. The server advertises one MCP tool, `discover_tools`. Calling that tool
returns the ranked downstream tools that the calling application can pass to
its LLM and local tool executor.

The MCP server is a read-only Redis cache consumer. It never discovers provider
tools, loads YAML into Redis, refreshes entries, or builds the cache. Build and
refresh the Redis tool cache through a separate administration process or CLI
before starting the MCP server. Startup fails clearly if Redis is unavailable
or the tool cache is empty. Every cached tool must include `tool_name`,
`transport`, and `endpoint`; an incomplete cache is rejected rather than
silently repaired by the MCP process.

Build or refresh the complete Redis catalog before starting the MCP server:

```bash
axiolex-index refresh \
  --tools-file /path/to/your/tools_list.yaml \
  --providers-file /path/to/your/mcp_providers.yaml
```

The indexer loads enabled YAML tools, discovers tools from every enabled MCP
provider, validates execution metadata, atomically replaces the Redis catalog,
prints a JSON summary, and exits. By default, an enabled MCP provider returning
no tools aborts the refresh and leaves the previous Redis catalog untouched.
Use `--allow-partial` only when intentionally accepting a partial catalog.
Each successful replacement writes a new catalog version. The read-only MCP
server detects that version on the next `discover_tools` call and reloads its
in-memory BM25 index without requiring a restart.

Both YAML files are caller-owned local configuration. They are passed
explicitly and are not assumed to live inside the installed Python package.
The calling application can alternatively configure them through environment
variables:

```bash
export AXIOLEX_TOOLS_FILE=/path/to/your/tools_list.yaml
export AXIOLEX_MCP_PROVIDERS_FILE=/path/to/your/mcp_providers.yaml
axiolex-index refresh
```

Inspect the current catalog:

```bash
axiolex-index status
```

The same indexing boundary is available to Python callers:

```python
import asyncio

from axiolex import ToolIndexingService

result = asyncio.run(
    ToolIndexingService(
        tools_file="/path/to/your/tools_list.yaml",
        providers_file="/path/to/your/mcp_providers.yaml",
    ).refresh()
)
print(result.to_dict())
```

The indexer is a one-shot administration CLI and does not require a port. Keep
the MCP discovery server on port `9701`. If remote refresh triggering is needed
later, expose the indexing service through a separately authenticated private
admin API rather than through the public MCP server.

Start the MCP server:

```bash
axiolex-mcp-server --host 0.0.0.0 --port 9701
```

Connect MCP clients to:

```text
http://localhost:9701/mcp
```

The bind address `0.0.0.0` makes the server reachable through the machine or
container hostname too, such as `http://axiolex:9701/mcp`. URL fragments such
as `#discover-tools` are browser-only and are not part of an MCP endpoint.

Example MCP client:

```python
import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main():
    async with streamable_http_client("http://localhost:9701/mcp") as streams:
        async with ClientSession(*streams[:2]) as session:
            await session.initialize()

            # tools/list exposes Axiolex's discover_tools function.
            print(await session.list_tools())

            # tools/call returns selected downstream tool definitions.
            result = await session.call_tool(
                "discover_tools",
                {"query": "get stock price history", "max_tools": 5},
            )
            print(result.structuredContent)


asyncio.run(main())
```

Each returned downstream tool includes:

- `name`: exact tool name for execution
- `description`: tool purpose
- `params` and `inputSchema`: parameter definitions
- `endpoint`: HTTP, MCP, or provider-specific endpoint configuration
- `transport`: execution transport
- `provider`: provider identifier, when available

For direct Python use without MCP:

```python
from axiolex import discover_tools

result = discover_tools("get stock price history", max_tools=5)
```

`vrraj-axiolex` acts as a lightweight relevance layer between tool discovery and prompt assembly. It is useful when user intent maps to a bounded set of actions: quotes, market movers, order placement, customer order lookup, CRM updates, follow-up emails, escalations, and similar workflow-driven tasks.

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

Tools can come from YAML, MCP discovery, or internal registries. The client or orchestration layer maps them into BM25S documents and injects them into a unified in-memory index. At query time, BM25S filters the relevant subset before the LLM sees the tool list.

Benefits:

- Filter MCP-discovered tools on demand before passing tool definitions to the LLM
- Combine static YAML tool definitions, MCP-discovered tools, and internal tool definitions in the same BM25S retrieval index
- Reduce tool context from large registries to a small, relevant candidate set
- Lower token usage, latency, and cost by avoiding unnecessary tool definitions in the prompt
- Improve tool selection when tools have narrow, specific purposes
- Return metadata with retrieved tools/documents so the client or orchestrator can apply its own scope, policy, or routing logic
- Keep routing deterministic and explainable

Example:

```bash
python examples/llm_tool_routing_example.py
```

See:

- [examples/llm_tool_routing_example.py](https://github.com/vrraj/axiolex/blob/main/examples/llm_tool_routing_example.py)

## Other use cases

### Domain-constrained retrieval

Use BM25S to search curated document sets, tool registries, or MCP tool catalogs where the language is controlled and exact matches matter.

The tool catalog does not have to be static. Applications can load a YAML registry at startup, then add or refresh tool definitions discovered from MCP servers during runtime.

Examples:

- Trading actions and market-data tools
- Support case workflows
- CRM tasks and follow-up actions
- Internal process documentation
- Compliance or policy snippets

### Bounded domains and lexical precision

`vrraj-axiolex` is designed for bounded domains where user intent maps to a known set of tools, workflows, or documents.

In these environments, tools are usually described using a finite set of verbs, workflow names, and domain-specific terms. This makes lexical routing predictable, tunable, and explainable.

For example, if a tool is defined as `purchase_order`, the retriever can be configured with keywords such as `buy`, `order`, or `place order` to cover common user phrasing. Because the domain is bounded, these mappings can be explicitly controlled rather than inferred.

Users can try different keywords, descriptions, temperature values, and cutoff thresholds in the included Demo Web UI to see how ranking changes before settling on production defaults.

### Hybrid RAG

AxioLex works well alongside embeddings, especially when you want lexical precision before or alongside semantic search:

- Use AxioLex for keyword precision
- Use embeddings for semantic recall
- Merge or rerank results before passing context to the LLM

This is helpful when semantic retrieval may miss exact tool names, workflow names, commands, abbreviations, or domain-specific terms.

Vector search is powerful for broad semantic discovery, but it can add latency and cost when embedding calls are required at runtime or when the system has to sort through many semantically similar matches. For bounded tool-selection problems, a lexical pass can be faster, cheaper, and easier to reason about.

### Lightweight retrieval service

For small-to-medium document sets, AxioLex can be enough by itself:

- No vector database required
- Fast in-memory retrieval
- Deterministic scoring
- Simple deployment
- Easy YAML-based configuration

## Demo Web UI

The GitHub repository includes a FastAPI-powered demo UI for testing retrieval behavior, inspecting ranked results, adding documents, and tuning search parameters.

It also acts as an interactive tuning environment. You can load your own YAML documents or tool definitions, inject additional documents or tools through the API, test retrieval parameters such as temperature, softmax cutoff thresholds, keywords, and content/tool descriptions, and iteratively refine routing behavior using the included UI.

This helps you visualize the ranking logic and see how tools or documents are prioritized before pushing retrieval settings into production.

![BM25S Retriever Web Interface](https://raw.githubusercontent.com/vrraj/axiolex/main/images/vrraj-axiolex-interactive-ui.png)

Run locally:

```bash
git clone https://github.com/vrraj/axiolex.git
cd axiolex
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e ".[dev]"
axiolex-server --config settings.yaml
```

Open:

```text
http://localhost:9700/
```

Manual start:

```bash
uvicorn axiolex.main:app --reload --port 9700
```

## Public API overview

### Library API

- `BM25SRetriever()` - Create a retriever instance
- `retriever.add_documents(...) -> None` - Add documents to the index
- `retriever.retrieve_documents(...) -> Dict` - Search documents with BM25S scoring
- `retriever.rebuild_index() -> None` - Reload documents from YAML and rebuild the index

### HTTP Client API

- `BM25SClient(base_url)` - Create an HTTP client
- `client.retrieve(...) -> Dict` - Search documents
- `client.add_document(...) -> Dict` - Add a document
- `client.get_documents() -> Dict` - List documents
- `client.delete_document(doc_id) -> Dict` - Delete a document
- `client.get_settings() -> Dict` - Read search settings
- `client.update_settings(...) -> Dict` - Update search settings

For complete method signatures and response details, see:

- [API Reference](https://vrraj.github.io/axiolex/api-reference.html)

## Search response schema

```python
{
    "success": bool,
    "message": str,
    "documents": [
        {
            "id": str,
            "title": str,
            "content": str,
            "keywords": list[str],
            "metadata": dict,
            "bm25_score": float,
            "score_percentage": float,
            "rank": int,
        }
    ],
    "total_retrieved": int,
    "cutoff_percentage": float,
    "settings": {
        "temperature": float,
        "ignore_zero": bool,
        "llm_tools_cutoff": float,
    },
}
```

## Document schema

```python
{
    "id": str,
    "title": str,
    "content": str,
    "keywords": list[str],
    "metadata": dict,
}
```

Searchable fields:

- `title`
- `content`
- `keywords`

Reference fields:

- `id`
- `metadata`
- `parameters` when present in YAML tool definitions

`metadata` is returned with each document/tool result so the client or orchestration layer can decide how to use it for routing, display, filtering, policy checks, or downstream logic.

## Configuration

### settings.yaml

```yaml
bm25s:
  temperature: 0.5          # Softmax temperature control
  ignore_zero: true         # Filter out zero-score results
  llm_tools_cutoff: 10.0    # Minimum softmax score percentage

documents:
  source: "source_files/tools_list.yaml"
  auto_reload: true

server:
  host: "0.0.0.0"
  port: 9700
  reload: false
```

### tools_list.yaml

```yaml
documents:
  - id: "get_customer_orders"
    title: "Get Customer Orders"
    content: "Retrieve open, closed, priority, delayed, or historical customer orders."
    keywords: ["orders", "customer orders", "open orders", "order history"]
    metadata:
      category: "customer_support"
      type: "tool"
```

### Environment variables

```bash
# Server configuration
BM25S_HOST=0.0.0.0
BM25S_PORT=9700
BM25S_RELOAD=false

# Document configuration
BM25S_DOCUMENTS_PATH=./source_files/tools_list.yaml
BM25S_AUTO_RELOAD=true

# BM25S defaults
BM25S_TEMPERATURE=0.5
BM25S_IGNORE_ZERO=true
BM25S_CUTOFF=10.0
```

## Document loading

Load from a custom YAML file:

```python
from axiolex import BM25SRetriever

retriever = BM25SRetriever(document_file="path/to/your/tools_list.yaml")
```

Or add documents programmatically:

```python
from axiolex import BM25SRetriever, Document

retriever = BM25SRetriever()
retriever.add_documents([
    Document(
        id="custom_doc",
        title="Custom Document",
        content="Your searchable content here.",
        keywords=["tag1", "tag2"],
    )
])
```

After editing a YAML source file, reload the index manually:

```python
retriever.rebuild_index()
```

Or create a new retriever instance:

```python
retriever = BM25SRetriever()
```

### Dynamic tool injection

You can also add tool definitions at runtime. This is useful when your application starts with a YAML registry but discovers additional tools from MCP servers or other tool providers and wants those tools to participate in lexical retrieval.

```python
from axiolex import Document

retriever.add_documents([
    Document(
        id="mcp_get_account_summary",
        title="Get Account Summary",
        content="Retrieve account balances, buying power, positions, and account status from an MCP-discovered tool.",
        keywords=["account", "balances", "buying power", "positions"],
        metadata={
            "source": "mcp",
            "server": "brokerage_tools",
            "type": "tool",
        },
    )
])
```

Retrieved results include metadata, allowing the client or orchestrator to map the selected document back to the underlying tool provider, MCP server, or execution layer.

## Search tuning

The GitHub repo is useful for hands-on retrieval tuning. Run the demo UI locally with your own data to test temperature, softmax scoring, and cutoff settings, then refine your keywords and tool descriptions based on the ranked results.

### Stemming

The retriever uses PyStemmer to improve lexical recall across related word forms.

Examples:

- `trade`, `trading`, `traded`
- `invest`, `investing`, `investment`
- `order`, `orders`, `ordering`

### Temperature

- `0.1 - 0.5`: More focused and selective
- `0.5 - 1.5`: Balanced retrieval
- `1.5+`: Broader retrieval

Default: `0.5` in the sample configuration above. Tune based on your data and use case.

### Cutoff percentage

- `5 - 15%`: Typical range
- Lower values return more results
- Higher values return only stronger matches

Default: `10.0` in the sample configuration above. Tune based on your desired selectivity.

### Score interpretation

- `>20%`: Strong match
- `8-20%`: Good match
- `<8%`: Weak match
- `0%`: No lexical relevance

## Example scripts

### YAML file usage

```bash
python examples/load_yaml_documents.py
```

Covers:

- Loading custom YAML documents
- Search configuration
- Document management patterns

### REST API usage

```bash
axiolex-server --config settings.yaml
python examples/rest_api_examples.py
```

Covers:

- HTTP client operations
- REST-based document management
- Error handling patterns

### curl examples

```bash
axiolex-server --config settings.yaml
./examples/curl_api_examples.sh
```

Covers:

- Command-line API operations
- Search, add, list, and delete endpoints

## REST API examples

Add a document:

```bash
curl -X POST http://localhost:9700/documents \
  -H "Content-Type: application/json" \
  -d '{
    "id": "get_customer_orders",
    "title": "Get Customer Orders",
    "content": "Retrieve open, closed, priority, delayed, or historical customer orders.",
    "keywords": ["orders", "customer orders", "open orders", "order history"]
  }'
```

Search:

```bash
curl -X POST http://localhost:9700/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query": "show open customer orders", "temperature": 0.5}'
```

List documents:

```bash
curl http://localhost:9700/documents
```

Delete a document:

```bash
curl -X DELETE http://localhost:9700/documents/get_customer_orders
```

## Performance notes

Approximate guidance:

- **Small collections (<100 docs):** sub-second indexing, instant search
- **Medium collections (100-1,000 docs):** 1-3 second indexing, usually <100ms search
- **Larger collections (1,000+ docs):** 3-10 second indexing, roughly 100-500ms search depending on content size

Documents and the BM25S index are stored in memory for fast access.

Optimization tips:

- Keep `content` focused and specific
- Add realistic `keywords` that match how users ask questions
- Use lower temperature for more selective tool routing
- Use cutoff filtering to reduce noisy matches
- Use returned metadata in the client or orchestration layer for filtering, routing, display, policy checks, or downstream decisions

## Development

```bash
git clone https://github.com/vrraj/axiolex.git
cd axiolex
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e ".[dev]"
axiolex-server --config settings.yaml
```

Run tests:

```bash
pytest
pytest -m integration
pytest -m "integration or unit"
```

## Documentation

- [Complete API Reference](https://vrraj.github.io/axiolex/api-reference.html)
- [Document and Tool Ingestion Guide](https://vrraj.github.io/axiolex/document-and-tool-ingestion-guide.html)
- [GitHub Repository](https://github.com/vrraj/axiolex)
- [PyPI Package](https://pypi.org/project/vrraj-axiolex/)
- [Medium Story](https://medium.com/@vr.rajkumar99/context-engineering-for-tool-heavy-agents-lexical-routing-c1b0ebad7495)
- [AI computational complexity and the economics of approximation](https://medium.com/@vr.rajkumar99/the-p-vs-np-wall-why-ais-energy-crisis-may-actually-be-a-math-problem-46390ca3b853)

## License

MIT License.
