# API Reference

Reference for programmatic usage, HTTP integration, and retrieval behavior tuning.

This document provides the complete API reference for the BM25S Retriever, including method signatures, parameter details, response structures, and common usage patterns.

> **New here?** Start with the project overview on the home page: **[Axiolex docs home](https://vrraj.github.io/axiolex/)**.
>
> **Source + releases:** GitHub repo and PyPI package are linked from the home page.

> **Note:** The package exposes a convenience singleton `get_retriever()` which returns a global `BM25SRetriever` instance. You can use this for quick integration or create your own `BM25SRetriever` instance for explicit configuration and isolation.

## Table of Contents

- [Core Classes](#core-classes)
- [Main API Methods](#main-api-methods)
- [Response Structures](#response-structures)
- [Error Handling](#error-handling)
- [Common Usage Patterns](#common-usage-patterns)
- [HTTP Client API](#http-client-api)

---

## Core Classes

### `BM25SRetriever`

The main retriever class that provides BM25S-based document retrieval with softmax scoring and cutoff filtering.

```python
class BM25SRetriever:
    def __init__(
        self,
        settings: Optional[BM25SSettings] = None,
        document_file: str = "source_files/tools_list.yaml"
    )
```

**Parameters:**
- `settings`: `BM25SSettings` - Custom settings instance (defaults to BM25SSettings with defaults)
- `document_file`: `str` - Path to YAML document file (defaults to "source_files/tools_list.yaml")

### `Document`

Document representation for BM25S indexing.

```python
@dataclass
class Document:
    id: str
    title: str
    content: str
    keywords: List[str] = None
    metadata: Dict[str, Any] = None
```

**Fields:**
- `id`: `str` - Unique document identifier (required)
- `title`: `str` - Document title (required, searchable)
- `content`: `str` - Document body or description (required, searchable)
- `keywords`: `List[str]` - Search terms and synonyms (optional, searchable with "keyword:" prefix)
- `metadata`: `Dict[str, Any]` - Additional metadata for categorization, timestamps, etc. (optional, not searchable)

### `BM25SSettings`

Configuration settings for BM25S retrieval behavior.

```python
@dataclass
class BM25SSettings:
    temperature: float = 0.5
    ignore_zero: bool = True
    llm_tools_cutoff: float = 10.0
```

**Fields:**
- `temperature`: `float` - Softmax temperature control (0.1-10.0, default: 0.5)
- `ignore_zero`: `bool` - Filter out zero-score results (default: True)
- `llm_tools_cutoff`: `float` - Minimum softmax percentage (0-100, default: 10.0)

---

## Main API Methods

### `retrieve_documents()`

Retrieve documents based on query using BM25S with softmax scoring.

```python
def retrieve_documents(
    self,
    query: str,
    **kwargs
) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | `str` | ✅ | Search query text |
| `temperature` | `float` | ❌ | Override softmax temperature (default: from settings) |
| `ignore_zero` | `bool` | ❌ | Override zero-score filtering (default: from settings) |
| `llm_tools_cutoff` | `float` | ❌ | Override cutoff percentage (default: from settings) |

**Returns:** `Dict[str, Any]` - Retrieval results with documents, scores, and metadata

**Example:**

```python
from axiolex import BM25SRetriever

retriever = BM25SRetriever()

# Basic usage with defaults
results = retriever.retrieve_documents("place a limit buy order")

# With custom parameters
results = retriever.retrieve_documents(
    "financial analysis tools",
    temperature=0.5,
    llm_tools_cutoff=15.0,
    ignore_zero=True
)

# Access results
for doc in results["documents"]:
    print(f"{doc['title']}: {doc['softmax_score']:.2%} (BM25: {doc['bm25_score']})")
```

### `add_documents()`

Add new documents to the retriever and rebuild the index.

```python
def add_documents(self, documents: List[Document]) -> None
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `documents` | `List[Document]` | ✅ | List of Document objects to add |

**Example:**
```python
from axiolex import BM25SRetriever, Document

retriever = BM25SRetriever()

new_docs = [
    Document(
        id="get_account_summary",
        title="Get Account Summary",
        content="Retrieve account balances, buying power, and positions",
        keywords=["account", "balances", "positions"],
        metadata={"category": "trading"}
    )
]

retriever.add_documents(new_docs)
```

### `rebuild_index()`

Rebuild the BM25S index from scratch.

```python
def rebuild_index(self, documents: Optional[List[Document]] = None) -> None
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `documents` | `List[Document]` | ❌ | Optional document list to replace current documents |

**Example:**
```python
# Rebuild with current documents
retriever.rebuild_index()

# Rebuild with new document set
retriever.rebuild_index(new_document_list)
```

### `get_document_count()`

Get the number of indexed documents.

```python
def get_document_count(self) -> int
```

**Returns:** `int` - Number of documents in the index

**Example:**
```python
count = retriever.get_document_count()
print(f"Indexed {count} documents")
```

### `get_settings()`

Get current settings.

```python
def get_settings(self) -> BM25SSettings
```

**Returns:** `BM25SSettings` - Current settings object

**Example:**
```python
settings = retriever.get_settings()
print(f"Temperature: {settings.temperature}")
print(f"Cutoff: {settings.llm_tools_cutoff}")
```

### `update_settings()`

Update settings.

```python
def update_settings(self, settings: BM25SSettings) -> None
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `settings` | `BM25SSettings` | ✅ | New settings object |

**Example:**
```python
from axiolex import BM25SSettings

new_settings = BM25SSettings(
    temperature=0.5,
    ignore_zero=True,
    llm_tools_cutoff=10.0
)

retriever.update_settings(new_settings)
```

---

## Response Structures

### Retrieval Response

The response from `retrieve_documents()` follows this structure:

```python
{
    "success": bool,
    "message": str,
    "documents": List[Dict[str, Any]],
    "total_retrieved": int,
    "cutoff_percentage": float,
    "settings": {
        "temperature": float,
        "ignore_zero": bool,
        "llm_tools_cutoff": float
    }
}
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | Whether retrieval succeeded |
| `message` | `str` | Status message |
| `documents` | `List[Dict]` | Retrieved documents with scores |
| `total_retrieved` | `int` | Total documents before cutoff filtering |
| `cutoff_percentage` | `float` | Cutoff threshold used (percentage, e.g. 10.0) |
| `settings` | `Dict` | Settings used for this retrieval |

### Document Structure

Each document in the `documents` array has this structure:

```python
{
    "id": str,
    "title": str,
    "content": str,
    "keywords": List[str],
    "metadata": Dict[str, Any],
    "bm25_score": float,
    "softmax_score": float
}
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Document identifier |
| `title` | `str` | Document title |
| `content` | `str` | Document content |
| `keywords` | `List[str]` | Keywords list |
| `metadata` | `Dict[str, Any]` | Metadata dictionary |
| `bm25_score` | `float` | Raw BM25 relevance score |
| `softmax_score` | `float` | Softmax probability (0.0-1.0) |

---

## Error Handling

The retriever returns error responses in the standard response format when errors occur:

```python
{
    "success": False,
    "message": "Error description",
    "documents": [],
    "total_retrieved": 0,
    "cutoff_percentage": 0.0,
    "settings": {...}
}
```

**Common Error Messages:**
- `"No documents indexed"` - No documents loaded
- `"Query tokens are empty after processing"` - Query produced no tokens after stemming/stopword removal
- `"Error during retrieval: ..."` - General retrieval error

**Example:**
```python
results = retriever.retrieve_documents("test query")

if not results["success"]:
    print(f"Error: {results['message']}")
else:
    for doc in results["documents"]:
        print(doc["title"])
```

---

## Common Usage Patterns

### 1. Basic Document Retrieval

```python
from axiolex import BM25SRetriever

retriever = BM25SRetriever()

results = retriever.retrieve_documents("place a limit buy order")

for doc in results["documents"]:
    print(f"{doc['title']}: {doc['softmax_score']:.2%}")
```

### 2. Custom Search Parameters

```python
# More selective search
results = retriever.retrieve_documents(
    "financial analysis",
    temperature=0.3,       # Lower temp = more focused
    llm_tools_cutoff=15.0, # Higher cutoff = only top results
    ignore_zero=True
)

# Broader search
results = retriever.retrieve_documents(
    "trading tools",
    temperature=2.0,       # Higher temp = more uniform
    llm_tools_cutoff=5.0,  # Lower cutoff = more results
    ignore_zero=False
)
```

### 3. Dynamic Document Addition

```python
from axiolex import BM25SRetriever, Document

retriever = BM25SRetriever()

# Add MCP-discovered tools at runtime (dynamic tool injection)
mcp_tools = [
    Document(
        id="mcp_get_account_summary",
        title="Get Account Summary",
        content="Retrieve account balances from MCP server",
        keywords=["account", "balances", "mcp"],
        metadata={"source": "mcp", "server": "brokerage"}
    )
]

retriever.add_documents(mcp_tools)

# Now search includes both YAML and MCP tools
results = retriever.retrieve_documents("account balances")
```

### 4. Settings Management

```python
from axiolex import BM25SRetriever, BM25SSettings

retriever = BM25SRetriever()

# Get current settings
current = retriever.get_settings()
print(f"Current temperature: {current.temperature}")

# Update settings for precision
new_settings = BM25SSettings(
    temperature=0.5,
    ignore_zero=True,
    llm_tools_cutoff=10.0
)
retriever.update_settings(new_settings)

# All subsequent queries use new settings
results = retriever.retrieve_documents("query")
```

### 5. Per-Query Override

```python
# Use default settings for most queries
results1 = retriever.retrieve_documents("general query")

# Override for specific precision-critical queries
results2 = retriever.retrieve_documents(
    "specific query",
    temperature=0.3,
    llm_tools_cutoff=20.0
)
```

### 6. Using the Global Singleton

```python
from axiolex import get_retriever

# Use the global retriever instance
retriever = get_retriever()
results = retriever.retrieve_documents("query")
```

### 7. Metadata-Based Post-Processing

```python
results = retriever.retrieve_documents("trading tools")

# Use metadata in the application layer for routing or filtering
admin_tools = [
    doc for doc in results["documents"]
    if doc["metadata"].get("access_level") == "admin"
]

public_tools = [
    doc for doc in results["documents"]
    if doc["metadata"].get("access_level") == "public"
]
```

---

## HTTP Client API

### `BM25SClient`

HTTP client for remote BM25S service integration.

```python
class BM25SClient:
    def __init__(self, base_url: str = "http://localhost:9200")
```

**Parameters:**
- `base_url`: `str` - Base URL of the BM25S service (default: "http://localhost:9200")

### Client Methods

#### `retrieve()`

Search documents via HTTP.

```python
def retrieve(
    self,
    query: str,
    temperature: Optional[float] = None,
    ignore_zero: Optional[bool] = None,
    llm_tools_cutoff: Optional[float] = None
) -> Dict[str, Any]
```

**Example:**

```python
from axiolex import BM25SClient

client = BM25SClient("http://localhost:9200")

results = client.retrieve(
    "place a limit buy order",
    temperature=0.5,
    llm_tools_cutoff=10.0
)

for doc in results["documents"]:
    print(f"{doc['title']}: {doc['softmax_score']:.2%}")
```

#### `add_document()`

Add a document via HTTP.

```python
def add_document(self, document: Dict[str, Any]) -> Dict[str, Any]
```

**Example:**
```python
client.add_document({
    "id": "new_tool",
    "title": "New Tool",
    "content": "Tool description",
    "keywords": ["keyword1", "keyword2"],
    "metadata": {"category": "trading"}
})
```

#### `get_documents()`

Get all documents via HTTP.

```python
def get_documents(self) -> Dict[str, Any]
```

**Example:**
```python
docs = client.get_documents()
print(f"Total documents: {docs['count']}")
```

#### `delete_document()`

Delete a document via HTTP.

```python
def delete_document(self, doc_id: str) -> Dict[str, Any]
```

**Example:**
```python
client.delete_document("tool_id")
```

#### `get_settings()`

Get current settings via HTTP.

```python
def get_settings(self) -> Dict[str, Any]
```

**Example:**
```python
settings = client.get_settings()
print(f"Temperature: {settings['temperature']}")
```

#### `update_settings()`

Update settings via HTTP.

```python
def update_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]
```

**Example:**
```python
client.update_settings({
    "temperature": 0.5,
    "llm_tools_cutoff": 10.0
})
```

---

## Configuration

### Environment Variables

The following environment variables override settings.yaml values:

| Variable | Type | Description |
|----------|------|-------------|
| `BM25S_TEMPERATURE` | float | Override temperature setting |
| `BM25S_IGNORE_ZERO` | bool | Override ignore_zero setting ("true"/"false") |
| `BM25S_CUTOFF` | float | Override llm_tools_cutoff (minimum softmax percentage) |
| `BM25S_HOST` | string | Override server host |
| `BM25S_PORT` | int | Override server port |
| `BM25S_LOG_LEVEL` | string | Override log level |

### settings.yaml Structure

```yaml
bm25s:
  temperature: 0.5          # Softmax temperature (0.1-10.0)
  ignore_zero: true         # Filter zero-relevance documents
  llm_tools_cutoff: 10.0    # Minimum softmax percentage (0-100)

documents:
  source: "source_files/tools_list.yaml"
  auto_reload: true
  encoding: "utf-8"

server:
  host: "0.0.0.0"
  port: 9200
  reload: false
  log_level: "info"
```

---

## Parameter Stability

### Stable Parameters

| Parameter | Stability | Notes |
|-----------|-----------|-------|
| `query` | ✅ Stable | Core parameter for retrieval |
| `temperature` | ✅ Stable | Softmax temperature control |
| `ignore_zero` | ✅ Stable | Zero-score filtering |
| `llm_tools_cutoff` | ✅ Stable | Cutoff percentage |

### Document Fields

| Field | Searchable | Stability |
|-------|-----------|-----------|
| `id` | ❌ No | ✅ Stable |
| `title` | ✅ Yes | ✅ Stable |
| `content` | ✅ Yes | ✅ Stable |
| `keywords` | ✅ Yes | ✅ Stable |
| `metadata` | ❌ No | ✅ Stable |

**Legend:**
- ✅ **Stable**: Guaranteed interface, won't change
