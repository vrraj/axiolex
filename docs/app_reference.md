# AxioLex Application Reference

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Python Library API](#python-library-api)
- [REST API Reference](#rest-api-reference)
- [CLI Reference](#cli-reference)
- [Configuration Reference](#configuration-reference)
- [MCP Integration](#mcp-integration)
- [Examples](#examples)

## Installation

### Base Installation (Library Only)

```bash
pip install axiolex
```

### Full Installation (with Server)

```bash
pip install "axiolex[server]"
```

### Development Installation

```bash
git clone https://github.com/vrraj/axiolex.git
cd axiolex
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e ".[dev]"
```

## Quick Start

### Option A: Python Library

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
])

results = retriever.retrieve_documents("place a limit buy order")

for doc in results["documents"]:
    print(doc["id"], doc["title"], doc["score_percentage"])
```

### Option B: REST Service

```bash
# Start server
axiolex-server --config settings.yaml

# Search via curl
curl -X POST http://localhost:9700/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query": "show open customer orders"}'
```

### Option C: Python HTTP Client

```python
from axiolex import BM25SClient

client = BM25SClient("http://localhost:9700")
results = client.retrieve("show open customer orders")

print(f"Found {len(results['documents'])} matching tools/documents")
```

## Python Library API

### BM25SRetriever

#### Constructor

```python
BM25SRetriever(
    settings: BM25SSettings = None,
    document_file: str = "source_files/tools_list.yaml",
    use_cache: bool = True,
    cache_read_only: bool = False,
    require_cache: bool = False,
)
```

**Parameters:**
- `settings`: BM25S retrieval settings (optional)
- `document_file`: Path to YAML document file
- `use_cache`: Enable Redis cache
- `cache_read_only`: Read-only cache access (for MCP server)
- `require_cache`: Require cache to be available (fail if unavailable)

#### Methods

##### `retrieve_documents(query: str, **kwargs) -> Dict[str, Any]`

Retrieve documents based on query using BM25S with softmax scoring.

**Parameters:**
- `query`: Search query string
- `temperature`: Override softmax temperature (default: from settings)
- `ignore_zero`: Override zero-score filtering (default: from settings)
- `llm_tools_cutoff`: Override cutoff percentage (default: from settings)

**Returns:**
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
            "runtime": dict,
            "artifact": dict,
            "params": dict,
            "bm25_score": float,
            "softmax_score": float,
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

##### `add_documents(documents: List[Document]) -> None`

Add new documents and rebuild index.

**Parameters:**
- `documents`: List of Document objects

##### `rebuild_index(documents: List[Document] = None) -> None`

Rebuild the BM25S index.

**Parameters:**
- `documents`: Optional document list (if not provided, reloads from source)

##### `get_document_count() -> int`

Get number of indexed documents.

**Returns:** Integer count

##### `get_settings() -> BM25SSettings`

Get current settings.

**Returns:** BM25SSettings object

##### `update_settings(settings: BM25SSettings) -> None`

Update settings.

**Parameters:**
- `settings`: New BM25SSettings object

##### `refresh_local_yaml_cache() -> int`

Replace local YAML entries in Redis with current YAML file.

**Returns:** Number of cached documents

##### `reload_cache_if_changed() -> bool`

Reload in-memory index when external Redis catalog changes.

**Returns:** True if reloaded, False if unchanged

### Document

#### Constructor

```python
Document(
    id: str,
    title: str,
    content: str,
    keywords: List[str] = None,
    metadata: Dict[str, Any] = None,
    runtime: Dict[str, Any] = None,
    artifact: Dict[str, Any] = None,
    params: Dict[str, Any] = None,
)
```

**Parameters:**
- `id`: Unique document identifier
- `title`: Document title
- `content`: Document content/description
- `keywords`: List of searchable keywords
- `metadata`: Arbitrary metadata dictionary
- `runtime`: Runtime execution metadata (transport, endpoint, etc.)
- `artifact`: Artifact data
- `params`: Parameter schema

#### Methods

##### `copy() -> Dict[str, Any]`

Return a copy of document data as dictionary.

### BM25SSettings

#### Constructor

```python
BM25SSettings(
    temperature: float = 0.5,
    ignore_zero: bool = True,
    llm_tools_cutoff: float = 12.0,
)
```

**Parameters:**
- `temperature`: Softmax temperature (0.1-1.5, lower = more selective)
- `ignore_zero`: Filter out zero-score results
- `llm_tools_cutoff`: Minimum softmax score percentage (5-15%)

#### Methods

##### `to_dict() -> Dict[str, Any]`

Convert to dictionary.

##### `from_dict(data: Dict[str, Any]) -> BM25SSettings`

Create from dictionary (class method).

### BM25SClient

#### Constructor

```python
BM25SClient(base_url: str)
```

**Parameters:**
- `base_url`: Base URL of AxioLex REST service (e.g., "http://localhost:9700")

#### Methods

##### `retrieve(query: str, **kwargs) -> Dict[str, Any]`

Search documents remotely.

**Parameters:**
- `query`: Search query
- `temperature`: Override temperature
- `ignore_zero`: Override zero-score filtering
- `llm_tools_cutoff`: Override cutoff percentage

**Returns:** Same format as `BM25SRetriever.retrieve_documents()`

##### `add_document(document: Dict[str, Any]) -> Dict[str, Any]`

Add a document remotely.

**Parameters:**
- `document`: Document dictionary with id, title, content, keywords, metadata

**Returns:**
```python
{
    "success": bool,
    "message": str,
}
```

##### `get_documents() -> Dict[str, Any]`

Get all documents from cache.

**Returns:**
```python
{
    "success": bool,
    "documents": list,
    "count": int,
}
```

##### `delete_document(document_id: str) -> Dict[str, Any]`

Delete a document by ID.

**Parameters:**
- `document_id`: Document identifier

**Returns:**
```python
{
    "success": bool,
    "message": str,
}
```

##### `get_settings() -> Dict[str, Any]`

Get current settings.

**Returns:**
```python
{
    "success": bool,
    "settings": BM25SSettings dict,
}
```

##### `update_settings(settings: Dict[str, Any]) -> Dict[str, Any]`

Update settings.

**Parameters:**
- `settings`: Settings dictionary

**Returns:**
```python
{
    "success": bool,
    "settings": BM25SSettings dict,
}
```

### ToolDiscoveryService

#### Constructor

```python
ToolDiscoveryService(
    retriever: BM25SRetriever = None,
)
```

**Parameters:**
- `retriever`: Optional custom retriever instance

#### Methods

##### `discover_tools(query: str, max_tools: int = 5) -> List[Dict[str, Any]]`

Discover and rank tools by query.

**Parameters:**
- `query`: Search query
- `max_tools`: Maximum number of tools to return

**Returns:** List of tool dictionaries with execution metadata

### ToolIndexingService

#### Constructor

```python
ToolIndexingService(
    tools_file: str,
    providers_file: str,
    cache_manager: ToolCacheManager = None,
    allow_partial: bool = False,
)
```

**Parameters:**
- `tools_file`: Path to tools YAML file
- `providers_file`: Path to MCP providers YAML file
- `cache_manager`: Optional custom cache manager
- `allow_partial`: Allow partial catalog if provider returns no tools

#### Methods

##### `async refresh() -> IndexingResult`

Build and atomically replace the complete Redis tool catalog.

**Returns:** IndexingResult with counts

##### `status() -> Dict[str, Any]`

Return Redis catalog status without modification.

**Returns:**
```python
{
    "tool_count": int,
    "incomplete_runtime_tools": list[str],
    "catalog_version": str,
    "cache_stats": dict,
}
```

### Global Functions

##### `retrieve_documents(query: str, documents: List[Document] = None, **kwargs) -> Dict[str, Any]`

Convenience function for one-off retrieval.

**Parameters:**
- `query`: Search query
- `documents`: Optional document list (creates new retriever if provided)
- `**kwargs`: Settings overrides

**Returns:** Same format as `BM25SRetriever.retrieve_documents()`

##### `discover_tools(query: str, max_tools: int = 5) -> List[Dict[str, Any]]`

Convenience function for tool discovery.

**Parameters:**
- `query`: Search query
- `max_tools`: Maximum tools to return

**Returns:** List of tool dictionaries

## REST API Reference

### Base URL

```
http://localhost:9700
```

### Endpoints

#### POST /retrieve

Retrieve documents based on query.

**Request Body:**
```json
{
  "query": "string",
  "temperature": 0.5,
  "ignore_zero": true,
  "llm_tools_cutoff": 10.0
}
```

**Response:**
```json
{
  "success": true,
  "message": "Retrieved 3 documents",
  "documents": [
    {
      "id": "doc1",
      "title": "Document Title",
      "content": "Document content",
      "keywords": ["keyword1", "keyword2"],
      "metadata": {},
      "runtime": {},
      "artifact": {},
      "params": {},
      "bm25_score": 1.5,
      "softmax_score": 0.45
    }
  ],
  "total_retrieved": 3,
  "cutoff_percentage": 0.1,
  "settings": {
    "temperature": 0.5,
    "ignore_zero": true,
    "llm_tools_cutoff": 10.0
  }
}
```

#### POST /index

Build or rebuild BM25S index.

**Request Body:**
```json
{
  "documents": [
    {
      "id": "doc1",
      "title": "Document Title",
      "content": "Document content",
      "keywords": ["keyword1"],
      "metadata": {},
      "runtime": {},
      "artifact": {},
      "params": {}
    }
  ],
  "rebuild": false
}
```

**Response:**
```json
{
  "success": true,
  "message": "Index built successfully with 1 documents",
  "document_count": 1,
  "index_time_ms": 45.2
}
```

#### GET /settings

Get current BM25S settings.

**Response:**
```json
{
  "success": true,
  "settings": {
    "temperature": 0.5,
    "ignore_zero": true,
    "llm_tools_cutoff": 10.0
  }
}
```

#### POST /settings

Update BM25S settings.

**Request Body:**
```json
{
  "temperature": 0.6,
  "ignore_zero": true,
  "llm_tools_cutoff": 12.0
}
```

**Response:** Same as GET /settings

#### GET /documents

Get all documents from Redis cache.

**Response:**
```json
{
  "success": true,
  "documents": [...],
  "count": 10
}
```

#### POST /documents

Add a new document.

**Request Body:**
```json
{
  "id": "doc1",
  "title": "Document Title",
  "content": "Document content",
  "keywords": ["keyword1"],
  "metadata": {},
  "runtime": {},
  "artifact": {},
  "params": {}
}
```

**Response:**
```json
{
  "success": true,
  "message": "Document 'doc1' added successfully"
}
```

#### DELETE /documents/{document_id}

Delete a document by ID.

**Response:**
```json
{
  "success": true,
  "message": "Document 'doc1' deleted successfully"
}
```

#### POST /documents/reload

Reload documents from YAML file.

**Response:**
```json
{
  "success": true,
  "message": "Documents reloaded. 15 documents loaded."
}
```

#### POST /documents/reindex-bm25s

Rebuild the BM25S index from currently loaded documents.

**Response:**
```json
{
  "success": true,
  "message": "BM25S index rebuilt with 15 documents.",
  "document_count": 15,
  "index_time_ms": 123.4
}
```

#### GET /status

Get service status.

**Response:**
```json
{
  "status": "healthy",
  "document_count": 15,
  "retriever_initialized": true,
  "version": "1.0.0"
}
```

#### POST /reload

Reload the retriever instance.

**Response:**
```json
{
  "success": true,
  "message": "Retriever reloaded successfully"
}
```

#### GET /document-files

Get available document files and current file info.

**Response:**
```json
{
  "available_files": ["tools_list.yaml", "documents.yaml"],
  "current_file": "tools_list.yaml",
  "user_added_count": 3,
  "requires_warning": true
}
```

#### POST /switch-document-file

Switch to a different document file.

**Request Body:**
```json
{
  "filename": "documents.yaml",
  "confirmed": false
}
```

**Response:**
```json
{
  "success": true,
  "message": "Switched to documents.yaml"
}
```

#### GET /mcp-providers

Get all MCP providers.

**Response:**
```json
{
  "success": true,
  "providers": [...],
  "count": 2
}
```

#### POST /mcp-providers

Add a new MCP provider.

**Request Body:**
```json
{
  "id": "provider1",
  "name": "Provider Name",
  "transport": "http",
  "endpoint": "https://example.com/mcp",
  "auth": {
    "type": "api_key",
    "secret_env": "PROVIDER_API_KEY"
  },
  "enabled": true
}
```

**Response:**
```json
{
  "success": true,
  "message": "Provider provider1 added successfully"
}
```

#### PUT /mcp-providers/{provider_id}

Update an existing MCP provider.

**Request Body:** Same as POST /mcp-providers

**Response:**
```json
{
  "success": true,
  "message": "Provider provider1 updated successfully"
}
```

#### DELETE /mcp-providers/{provider_id}

Disable an MCP provider and clear its cached tools.

**Response:**
```json
{
  "success": true,
  "message": "Provider provider1 disabled and cached tools cleared",
  "provider_id": "provider1",
  "enabled": false,
  "cache_cleared": true
}
```

#### GET /mcp-providers/{provider_id}/discover

Discover tools from a specific MCP provider.

**Response:**
```json
{
  "success": true,
  "provider_id": "provider1",
  "tools": [...],
  "count": 5
}
```

## CLI Reference

### axiolex-server

Start the AxioLex REST service.

```bash
axiolex-server --config settings.yaml
```

**Options:**
- `--config`: Path to configuration file (default: settings.yaml)
- `--host`: Override server host (default: from config)
- `--port`: Override server port (default: from config)
- `--reload`: Enable auto-reload (default: from config)

### axiolex-index

Manage the Redis tool catalog.

#### refresh

Build and refresh the Redis tool catalog from YAML and MCP providers.

```bash
axiolex-index refresh \
  --tools-file /path/to/tools_list.yaml \
  --providers-file /path/to/mcp_providers.yaml
```

**Options:**
- `--tools-file`: Path to tools YAML file (or AXIOLEX_TOOLS_FILE env var)
- `--providers-file`: Path to MCP providers YAML file (or AXIOLEX_MCP_PROVIDERS_FILE env var)
- `--allow-partial`: Allow partial catalog if provider returns no tools

**Environment Variables:**
- `AXIOLEX_TOOLS_FILE`: Default tools file path
- `AXIOLEX_MCP_PROVIDERS_FILE`: Default providers file path
- `REDIS_HOST`: Redis host (default: localhost)
- `REDIS_PORT`: Redis port (default: 6379)

#### status

Inspect the current Redis catalog status.

```bash
axiolex-index status
```

**Output:**
```json
{
  "tool_count": 25,
  "incomplete_runtime_tools": [],
  "catalog_version": "a1b2c3d4",
  "cache_stats": {
    "connected": true,
    "total_keys": 50,
    "discovery_keys": 25,
    "runtime_keys": 25
  }
}
```

### axiolex-mcp-server

Start the AxioLex MCP discovery server.

```bash
axiolex-mcp-server --host 0.0.0.0 --port 9701
```

**Options:**
- `--host`: Server bind address (default: 0.0.0.0)
- `--port`: Server port (default: 9701)

**Endpoint:**
```
http://localhost:9701/mcp
```

**Exposed Tool:**
- `discover_tools`: Returns ranked downstream tools based on query

## Configuration Reference

### settings.yaml

```yaml
bm25s:
  temperature: 0.5          # Softmax temperature (0.1-1.5)
  ignore_zero: true         # Filter zero-score results
  llm_tools_cutoff: 10.0    # Minimum softmax score percentage

documents:
  source: "source_files/tools_list.yaml"
  auto_reload: true
  encoding: "utf-8"

mcp:
  providers_file: "source_files/mcp_providers.yaml"
  auto_discover: true
  cache_ttl: 3600           # Legacy MCP config field

server:
  host: "0.0.0.0"
  port: 9700
  reload: false
  log_level: "info"
```

Redis catalog entry TTLs are configured through environment variables:

```bash
AXIOLEX_REDIS_DISCOVERY_TTL_SECONDS=0
AXIOLEX_REDIS_RUNTIME_TTL_SECONDS=0
```

Use `0` to keep cached entries until explicit refresh, Redis eviction, or
provider/tool invalidation. Positive values expire per-entry cache writes after
that many seconds.

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
      enabled: true
    runtime:
      tool_name: "get_orders"
      transport: "http"
      endpoint:
        url: "https://api.example.com/orders"
        method: "GET"
      provider: "internal"
    params:
      customer_id:
        type: "string"
        description: "Customer identifier"
      status:
        type: "string"
        enum: ["open", "closed", "all"]
```

### mcp_providers.yaml

```yaml
providers:
  - id: "alphavantage_finance"
    name: "Alpha Vantage MCP"
    transport: "http"
    endpoint: "https://mcp.alphavantage.co/mcp"
    auth:
      type: "api_key"
      secret_env: "ALPHAVANTAGE_API_KEY"
    enabled: true
    features:
      supports_streaming: false
    limits:
      max_page_size: 100
      max_requests_per_minute: 60
      max_results: 100
      timeout_seconds: 10

  - id: "custom_provider"
    name: "Custom MCP Provider"
    transport: "streamable-http"
    endpoint: "https://custom.example.com/mcp"
    auth:
      type: "bearer"
      secret_env: "CUSTOM_TOKEN"
    enabled: true
    headers:
      X-Custom-Header: "value"
```

### Environment Variables

```bash
# Server configuration
BM25S_HOST=0.0.0.0
BM25S_PORT=9700
BM25S_RELOAD=false
BM25S_LOG_LEVEL=info

# Document configuration
BM25S_DOCUMENTS_PATH=./source_files/tools_list.yaml
BM25S_AUTO_RELOAD=true

# BM25S defaults
BM25S_TEMPERATURE=0.5
BM25S_IGNORE_ZERO=true
BM25S_CUTOFF=10.0

# Redis configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# Index CLI
AXIOLEX_TOOLS_FILE=./source_files/tools_list.yaml
AXIOLEX_MCP_PROVIDERS_FILE=./source_files/mcp_providers.yaml
```

## MCP Integration

### AxioLex as MCP Server

AxioLex can expose its tool selection as an MCP server.

**Start the MCP server:**
```bash
axiolex-mcp-server --host 0.0.0.0 --port 9701
```

**Connect as MCP client:**
```python
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

async def main():
    async with streamable_http_client("http://localhost:9701/mcp") as streams:
        async with ClientSession(*streams[:2]) as session:
            await session.initialize()
            
            # List tools (exposes discover_tools)
            tools = await session.list_tools()
            print(tools)
            
            # Call discover_tools
            result = await session.call_tool(
                "discover_tools",
                {"query": "get stock price history", "max_tools": 5},
            )
            print(result.structuredContent)

asyncio.run(main())
```

### MCP Tool Discovery

**Discover tools from MCP providers:**
```python
from axiolex import ToolIndexingService
import asyncio

result = asyncio.run(
    ToolIndexingService(
        tools_file="source_files/tools_list.yaml",
        providers_file="source_files/mcp_providers.yaml",
    ).refresh()
)
print(result.to_dict())
```

**Direct tool discovery:**
```python
from axiolex import discover_tools

tools = discover_tools("get stock price history", max_tools=5)
for tool in tools:
    print(f"{tool['title']}: {tool['description']}")
```

## Examples

### Example 1: Basic Document Search

```python
from axiolex import BM25SRetriever, Document

# Create retriever
retriever = BM25SRetriever()

# Add documents
retriever.add_documents([
    Document(
        id="doc1",
        title="Trading Guide",
        content="How to place buy and sell orders for stocks",
        keywords=["trading", "stocks", "orders"],
    ),
    Document(
        id="doc2",
        title="Market Analysis",
        content="Analyze market trends and patterns",
        keywords=["market", "analysis", "trends"],
    ),
])

# Search
results = retriever.retrieve_documents("how to trade stocks")
for doc in results["documents"]:
    print(f"{doc['title']}: {doc['score_percentage']:.1f}%")
```

### Example 2: Tool Routing for LLM

```python
from axiolex import BM25SRetriever, Document

# Define tools
tools = [
    Document(
        id="get_stock_price",
        title="Get Stock Price",
        content="Retrieve current stock price for a given symbol",
        keywords=["stock", "price", "quote"],
        runtime={
            "tool_name": "get_price",
            "transport": "http",
            "endpoint": {"url": "https://api.example.com/price"},
        },
    ),
    Document(
        id="place_order",
        title="Place Order",
        content="Place a buy or sell order",
        keywords=["order", "buy", "sell", "trade"],
        runtime={
            "tool_name": "execute_order",
            "transport": "http",
            "endpoint": {"url": "https://api.example.com/order"},
        },
    ),
]

# Index tools
retriever = BM25SRetriever()
retriever.add_documents(tools)

# Route user query to relevant tools
query = "I want to buy Apple stock"
results = retriever.retrieve_documents(query, temperature=0.5)

# Pass only relevant tools to LLM
relevant_tools = [doc["runtime"] for doc in results["documents"]]
print(f"Selected {len(relevant_tools)} tools for LLM context")
```

### Example 3: Remote Service Client

```python
from axiolex import BM25SClient

# Connect to remote service
client = BM25SClient("http://remote-server:9700")

# Search
results = client.retrieve("customer support workflows")

# Update settings
client.update_settings({"temperature": 0.3, "llm_tools_cutoff": 15.0})

# Add document
client.add_document({
    "id": "new_doc",
    "title": "New Workflow",
    "content": "Workflow description",
    "keywords": ["workflow"],
})
```

### Example 4: MCP Provider Integration

```python
from axiolex import ToolIndexingService
import asyncio

# Build catalog from YAML + MCP providers
result = asyncio.run(
    ToolIndexingService(
        tools_file="source_files/tools_list.yaml",
        providers_file="source_files/mcp_providers.yaml",
    ).refresh()
)

print(f"Indexed {result.total_tools} tools")
print(f"  - YAML: {result.yaml_tools}")
print(f"  - MCP: {result.mcp_tools} from {result.provider_count} providers")
```

### Example 5: Custom Settings

```python
from axiolex import BM25SRetriever, BM25SSettings

# Create custom settings
settings = BM25SSettings(
    temperature=0.3,      # More selective
    ignore_zero=True,
    llm_tools_cutoff=15.0, # Higher threshold
)

# Use custom settings
retriever = BM25SRetriever(settings=settings)

# Or update at runtime
retriever.update_settings(BM25SSettings(temperature=0.7))
```

### Example 6: Dynamic Document Injection

```python
from axiolex import BM25SRetriever, Document

# Load static tools from YAML
retriever = BM25SRetriever(document_file="tools_list.yaml")

# Inject MCP-discovered tools at runtime
mcp_tools = [
    Document(
        id="mcp_tool_1",
        title="MCP Tool",
        content="Description from MCP server",
        keywords=["mcp", "tool"],
        metadata={"source": "mcp", "server": "brokerage_tools"},
        runtime={
            "tool_name": "execute_mcp_tool",
            "transport": "mcp",
            "endpoint": {"server": "brokerage_tools"},
        },
    )
]

retriever.add_documents(mcp_tools)

# Search across both sources
results = retriever.retrieve_documents("trading actions")
```

### Example 7: Cache Management

```python
from axiolex import BM25SRetriever
from axiolex.core.cache import get_cache_manager

# Create retriever with cache
retriever = BM25SRetriever(use_cache=True)

# Refresh local YAML to Redis
retriever.refresh_local_yaml_cache()

# Get cache manager
cache_manager = get_cache_manager()

# Check cache status
stats = cache_manager.get_cache_stats()
print(f"Cache: {stats['discovery_keys']} discovery, {stats['runtime_keys']} runtime")

# Invalidate specific tool
cache_manager.invalidate_tool("tool_id")

# Invalidate entire provider
cache_manager.invalidate_provider("provider_id")
```

### Example 8: REST API with curl

```bash
# Start server
axiolex-server --config settings.yaml

# Search
curl -X POST http://localhost:9700/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query": "place order", "temperature": 0.5}'

# Add document
curl -X POST http://localhost:9700/documents \
  -H "Content-Type: application/json" \
  -d '{
    "id": "new_tool",
    "title": "New Tool",
    "content": "Tool description",
    "keywords": ["tool"]
  }'

# Get settings
curl http://localhost:9700/settings

# Update settings
curl -X POST http://localhost:9700/settings \
  -H "Content-Type: application/json" \
  -d '{"temperature": 0.3, "llm_tools_cutoff": 15.0}'

# List documents
curl http://localhost:9700/documents

# Delete document
curl -X DELETE http://localhost:9700/documents/new_tool

# Get status
curl http://localhost:9700/status
```

## Error Handling

### Common Errors

**Redis Connection Error:**
```python
# Error: Redis tool cache is unavailable
# Solution: Start Redis or disable cache
retriever = BM25SRetriever(use_cache=False)
```

**Empty Query Tokens:**
```python
# Error: Query tokens are empty after processing
# Solution: Use more specific query terms
results = retriever.retrieve_documents("specific terms")
```

**No Documents Indexed:**
```python
# Error: No documents indexed
# Solution: Add documents or check YAML file
retriever.add_documents([...])
# or
retriever.rebuild_index()
```

**Incomplete Runtime Metadata:**
```python
# Error: Tools missing required runtime metadata
# Solution: Ensure tools have tool_name, transport, endpoint
runtime = {
    "tool_name": "execute",
    "transport": "http",
    "endpoint": {"url": "https://api.example.com"},
}
```

## Performance Tuning

### Temperature Tuning

- **0.1-0.3**: Very selective, only exact matches
- **0.4-0.6**: Balanced (default: 0.5)
- **0.7-1.0**: Broader retrieval
- **1.0+**: Very broad, may include noisy results

### Cutoff Tuning

- **5-8%**: More results, lower precision
- **10-12%**: Balanced (default: 10-12%)
- **15-20%**: Fewer results, higher precision
- **20%+**: Only very strong matches

### Index Size Guidelines

- **<100 documents**: Sub-second indexing, instant search
- **100-1,000 documents**: 1-3 second indexing, <100ms search
- **1,000+ documents**: 3-10 second indexing, 100-500ms search

### Optimization Tips

1. Keep `content` focused and specific
2. Add realistic `keywords` matching user language
3. Use lower temperature for tool routing
4. Use cutoff filtering to reduce noise
5. Leverage `metadata` for client-side filtering
6. Enable Redis cache for multi-instance deployments
7. Use `ignore_zero=true` to filter irrelevant results
