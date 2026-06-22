# AxioLex Search Guide

This guide shows you how to use the search functionality in AxioLex, both through the web interface and via API calls.

## Use Case Summary

AxioLex is designed for **agentic systems** that need to intelligently route user queries to the right tools, documents, or workflows. Here are the primary use cases:

### 1. LLM Tool Routing
**Problem:** Your LLM has access to 50+ tools, but only 2-3 are relevant for any given user request. Passing all tools to the LLM wastes tokens and degrades selection accuracy.

**Solution:** AxioLex retrieves only the most relevant tools based on the user's query, keeping the LLM context focused and efficient.

**Example:**
- User asks: "Show me Tesla's stock performance over the last 6 months"
- AxioLex retrieves: `get_stock_price_history` (finance tool)
- LLM receives: Only this tool with its parameters, not 50 irrelevant tools

### 2. MCP Tool Discovery and Filtering
**Problem:** MCP servers expose many tools, but you need to filter them before passing to the LLM based on user intent.

**Solution:** AxioLex indexes MCP-discovered tools and provides semantic retrieval to select the right subset.

**Example:**
- MCP server exposes: 30 finance tools, 20 weather tools, 15 calendar tools
- User asks: "What's the weather in Tokyo?"
- AxioLex retrieves: Only weather-related tools from the MCP catalog

### 3. Hybrid Lexical + Semantic Search
**Problem:** Pure keyword search misses semantic intent ("find purchases" vs "show orders"), while pure semantic search can miss exact tool names.

**Solution:** AxioLex combines BM25S lexical search with ColBERT semantic search, fusing scores for the best of both worlds.

**Example:**
- Query: "find purchases that have not completed"
- BM25S matches: "get_customer_orders", "order_history"
- ColBERT matches: "get_open_orders", "pending_purchases"
- Hybrid result: Ranked fusion of both approaches

### 4. Artifact-Aware Tool Routing
**Problem:** Some tools produce heavy UI artifacts (SVG charts, maps) that shouldn't be passed to the LLM as raw text.

**Solution:** AxioLex identifies artifact-producing tools and returns metadata so your gateway can render artifacts separately while sending compact summaries to the LLM.

**Example:**
- Tool: `get_stock_price_history` produces an SVG chart
- AxioLex returns: Artifact metadata (type: svg, key: svg)
- Gateway: Renders SVG in UI, sends only summary data to LLM
- LLM: Receives "TSLA 6M: $184.10, rebounding" instead of 50KB of SVG path data

### 5. Document and Knowledge Retrieval
**Problem:** You have large document collections and need fast, deterministic retrieval without running a vector database.

**Solution:** AxioLex provides BM25S lexical search with stemming, plus optional ColBERT semantic search for deeper understanding.

**Example:**
- Query: "how to process a refund"
- AxioLex retrieves: Refund policy document, refund process guide, billing procedures

### 6. Multi-Source Tool Aggregation
**Problem:** Tools come from multiple sources: YAML files, MCP servers, internal APIs, and you need unified search across all of them.

**Solution:** AxioLex indexes tools from YAML and MCP sources into a unified Redis catalog, with consistent retrieval across all sources.

**Example:**
- Static tools: `create_order`, `get_customer_profile` (from YAML)
- Dynamic tools: `get_stock_price_history` (from MCP Alpha Vantage)
- Unified search: "place a buy order" retrieves relevant tools from both sources

## Using the Search Tab

### Accessing the Search Interface

1. **Open the Web Interface**
   - Navigate to `http://localhost:9700` in your browser
   - Click on the "Discover" tab

### Search Query Interface

#### Basic Search

1. **Enter Your Query**
   - Type your search query in the "Query" text box
   - Example: "place a buy order" or "show customer profile"

2. **Configure Search Parameters**
   - **Hybrid Search**: Toggle to enable BM25S + ColBERT semantic search (requires `axiolex[colbert]`)
   - **Temperature**: Controls softmax uniformity (0.1-10.0)
     - Lower values (0.1-1.0): More focused results
     - Higher values (1.0-10.0): More uniform distribution
   - **Cutoff %**: Minimum softmax percentage (0-100)
     - Filters out results below this relevance threshold (lexical search only)
   - **Max Tools**: Maximum number of results to return
   - **Filter zero-relevance documents**: 
     - When checked, excludes documents with BM25 score of 0 (lexical search only)

3. **Perform Search**
   - Click "Search" button
   - Or press Enter in the query field

#### Understanding Search Results

The search results display:

**Lexical Search Results:**
- **Tool ID**: Unique identifier for each tool/document
- **Description**: Tool description or content
- **BM25 Score**: Raw BM25 relevance score (higher = more relevant)
- **Softmax Score**: Relevance percentage with your chosen temperature

**Hybrid Search Results:**
- **Tool ID**: Unique identifier for each tool/document
- **Description**: Tool description or content
- **BM25 Rank**: Lexical search ranking
- **ColBERT Rank**: Semantic search ranking
- **BM25 Score**: Lexical relevance score
- **ColBERT Score**: Semantic relevance score
- **Hybrid Score**: Fused relevance score (blended BM25 + ColBERT)
- **Match Status**: Strong match (>0.75), Possible match (0.40-0.75), Weak match (<0.40)

#### Advanced Search Techniques

1. **Hybrid Search (BM25S + ColBERT)**
   - Enable "Hybrid Search" toggle for semantic understanding
   - Combines exact keyword matching with semantic intent
   - Use when queries use different terminology than tool names
   - Example: "find purchases" matches "get_customer_orders" semantically

2. **Temperature Experiments**
   - Try different temperatures to see how it affects relevance distribution
   - Lower temperature = more dramatic score differences (focused)
   - Higher temperature = more uniform scores (exploratory)

3. **Cutoff Adjustment**
   - Increase cutoff to get only highly relevant results
   - Decrease cutoff to include more documents
   - Set to 0 to include all documents with non-zero BM25 scores

4. **Max Tools Limit**
   - Controls how many results are returned
   - Useful for limiting LLM context size
   - Default: 10, adjustable based on your needs

5. **Zero-Relevance Filtering**
   - Keep checked to exclude documents that don't match your query
   - Uncheck to see all documents (useful for analysis)

### Search Tips

- **Use Action Language**: AxioLex excels at matching tool names, commands, and domain-specific vocabulary
  - Good: "place buy order", "cancel transaction", "get customer profile"
  - Better: "show open orders", "process refund", "check inventory"
- **Combine Concepts**: Use natural language that combines intent with domain terms
  - Example: "find customer purchase history" instead of just "history"
- **Experiment with Hybrid Search**: Try both lexical and hybrid modes to see which works better for your queries
- **Adjust Temperature**: Start with 0.7, then adjust based on result quality
- **Use Max Tools**: Limit results to keep LLM context manageable (typically 5-10 tools)

## Search API Calls

### Basic Lexical Search Endpoint

```bash
curl -X POST http://localhost:9700/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "query": "place a buy order",
    "temperature": 0.7,
    "llm_tools_cutoff": 8.0,
    "ignore_zero": true,
    "max_results": 10
  }'
```

### Hybrid Search Endpoint (BM25S + ColBERT)

```bash
curl -X POST http://localhost:9700/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "query": "find purchases that have not completed",
    "hybrid_search": true,
    "temperature": 0.7,
    "bm25_weight": 0.4,
    "colbert_weight": 0.6,
    "candidate_limit": 100,
    "min_hybrid_score": 0.4,
    "max_results": 10
  }'
```

### Advanced Search Parameters

```bash
curl -X POST http://localhost:9700/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "query": "show customer order history",
    "temperature": 1.2,
    "llm_tools_cutoff": 5.0,
    "ignore_zero": false,
    "max_results": 15
  }'
```

### Python Search Implementation

#### Using the AxioLex Python Client

```python
from axiolex import BM25SClient

# Connect to AxioLex service
client = BM25SClient("http://localhost:9700")

# Lexical search
results = client.retrieve(
    query="place a buy order",
    temperature=0.7,
    llm_tools_cutoff=8.0,
    ignore_zero=True,
    max_results=10
)

print(f"Found {len(results['documents'])} matching tools")
for doc in results['documents']:
    print(f"  - {doc['id']}: {doc['title']} (score: {doc['softmax_score']:.2%})")

# Hybrid search (requires axiolex[colbert])
hybrid_results = client.retrieve(
    query="find purchases that have not completed",
    hybrid_search=True,
    temperature=0.7,
    bm25_weight=0.4,
    colbert_weight=0.6,
    candidate_limit=100,
    min_hybrid_score=0.4,
    max_results=10
)

print(f"\nHybrid search found {len(hybrid_results['documents'])} tools")
for doc in hybrid_results['documents']:
    print(f"  - {doc['id']}: hybrid_score={doc.get('hybrid_score', 0):.3f}")
```

#### Using the Python Retriever Directly

```python
from axiolex import BM25SRetriever, Document

# Create retriever and add documents
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
        id="get_customer_profile",
        title="Get Customer Profile",
        content="Returns customer account details, contact information, and profile settings.",
        keywords=["customer profile", "account details", "contact info"],
        metadata={"category": "crm", "type": "tool"},
    ),
])

# Lexical search
results = retriever.retrieve_documents("place a limit buy order")

for doc in results["documents"]:
    print(f"{doc['id']}: {doc['title']} (softmax: {doc['softmax_score']:.2%})")

# Hybrid search (requires axiolex[colbert])
hybrid_results = retriever.retrieve_documents(
    "find customer purchase history",
    hybrid_search=True,
    temperature=0.7,
    bm25_weight=0.4,
    colbert_weight=0.6,
    candidate_limit=100,
    min_hybrid_score=0.4
)

for doc in hybrid_results["documents"]:
    print(f"{doc['id']}: hybrid_score={doc.get('hybrid_score', 0):.3f}")
```

### Batch Search Implementation

```python
from axiolex import BM25SClient

def batch_search(queries, temperatures=[0.5, 1.0, 1.5]):
    """Perform multiple searches with different parameters."""
    client = BM25SClient("http://localhost:9700")
    results = {}
    
    for query in queries:
        results[query] = {}
        
        for temp in temperatures:
            result = client.retrieve(query, temperature=temp)
            results[query][f"temp_{temp}"] = {
                "count": len(result["documents"]),
                "top_doc": result["documents"][0]["id"] if result["documents"] else None,
                "avg_score": sum(doc["softmax_score"] for doc in result["documents"]) / len(result["documents"]) if result["documents"] else 0
            }
    
    return results

# Example batch search
queries = ["place order", "customer profile", "refund process"]
batch_results = batch_search(queries)

for query, temps in batch_results.items():
    print(f"\nQuery: {query}")
    for temp_key, stats in temps.items():
        print(f"  {temp_key}: {stats['count']} docs, avg: {stats['avg_score']:.3f}")
```

## Document Structure and Indexing

### Which YAML Fields Are Indexed

AxioLex indexes specific fields from your YAML documents to enable searching:

#### Indexed Fields (Searchable)
- **`title`** - Document title, fully searchable
- **`content`** - Document content/description, fully searchable  
- **`keywords`** - Keyword list, each keyword prefixed with "keyword:" for search

#### Stored Fields (Not Searchable)
- **`id`** - Document identifier, stored for retrieval but not searched
- **`metadata`** - All metadata fields, stored but not indexed
- **`runtime`** - Tool execution metadata (provider, transport, endpoint, params), stored but not indexed
- **`artifact`** - Artifact metadata for UI-rendering tools, stored but not indexed

### How Indexing Works

The system combines indexed fields into a single searchable text:

```python
# For each document, the search index contains:
title + " " + content + " keyword: keyword1 keyword: keyword2 ..."
```

**Example:**
```yaml
- id: "create_order"
  title: "Create New Order"
  content: "Start a new purchase, buy a product, or place a customer order."
  keywords: ["buy", "purchase", "place order", "checkout"]
```

This becomes searchable as:
```
"Create New Order Start a new purchase, buy a product, or place a customer order. keyword: buy keyword: purchase keyword: place order keyword: checkout"
```

### Search Optimization Tips

1. **Title**: Use descriptive, action-oriented titles that users might search for
2. **Content**: Include natural language descriptions with common search terms
3. **Keywords**: Add synonyms, abbreviations, and alternative phrasing users might type
4. **Avoid**: Don't put searchable content in `id`, `runtime`, `artifact`, or `metadata` fields

## YAML Structure Requirements

### Field Definitions and Usage

#### Required Fields
```yaml
- id: "unique_identifier"     # Required: Document ID
  title: "Document Title"     # Required: Searchable title
  content: "Description..."   # Required: Searchable content
```

#### Keywords vs Metadata

**Keywords** (Searchable):
- **Purpose**: Terms users actually type when searching
- **Format**: List of strings
- **Indexed**: ✅ Added to BM25S search index with "keyword:" prefix
- **Use for**: Synonyms, abbreviations, alternative phrasing, action verbs
- **Example**: 
  ```yaml
  keywords: ["buy", "purchase", "place order", "checkout", "start transaction"]
  ```

**Metadata** (Not Searchable):
- **Purpose**: Document context and reference information
- **Format**: Dictionary of key-value pairs
- **Indexed**: ❌ Stored but not searchable
- **Use for**: Categorization, provider info, timestamps, configuration data
- **Example**:
  ```yaml
  metadata:
    category: "orders"
    provider: "internal"
    updated: "2025-04-07"
    version: "1.2"
  ```

#### Runtime Metadata (Tool Execution)

**Runtime** (Not Searchable, Returned with Results):
- **Purpose**: Tool execution information for downstream gateways
- **Format**: Dictionary with provider, transport, endpoint, and params
- **Indexed**: ❌ Stored but not searchable
- **Use for**: Tool routing, execution endpoints, parameter schemas
- **Example**:
  ```yaml
  runtime:
    provider: "internal"              # Tool provider (internal or MCP provider name)
    tool_name: "create_order"          # Actual tool name for execution
    transport: "http"                 # Transport type: http, mcp, grpc, websocket
    endpoint: "/api/orders"            # Execution endpoint
    params:
      customer_id: { type: "string" }
      product_id: { type: "string" }
      quantity: { type: "integer", minimum: 1 }
  ```

#### Artifact Metadata (UI Rendering)

**Artifact** (Not Searchable, Returned with Results):
- **Purpose**: Identify tools that produce renderable UI artifacts
- **Format**: Dictionary with artifact configuration
- **Indexed**: ❌ Stored but not searchable
- **Use for**: Tools that produce SVG charts, maps, tables, or other visual assets
- **Example**:
  ```yaml
  artifact:
    produces_artifact: true           # Whether this tool produces an artifact
    injection_mode: verbatim            # How to inject the artifact
    artifact_type: svg                 # Type of artifact (svg, image, etc.)
    artifact_key: svg                  # Key in the response containing the artifact
    placeholder: "{{ARTIFACT:stock_chart_svg}}"  # Placeholder for LLM context
  ```

### Complete YAML Structure Example

```yaml
documents:
  - id: "create_order"
    title: "Create New Order"
    content: "Start a new purchase, buy a product, or place a customer order. Use this to initiate a checkout process for items."
    keywords:
      - "buy"
      - "purchase"
      - "place order"
      - "checkout"
      - "start transaction"
      - "order item"
      - "buy product"
      - "new sale"
    metadata:
      enabled: true
      source: "yaml"
      category: "orders"
      provider: "internal"
      updated: "2025-04-07"
    runtime:
      provider: "internal"
      tool_name: "create_order"
      transport: "http"
      endpoint: "/api/orders"
      params:
        customer_id: { type: "string" }
        product_id: { type: "string" }
        quantity: { type: "integer", minimum: 1 }
        price: { type: "number" }
    artifact:
      produces_artifact: false
      injection_mode: verbatim
      artifact_type:
      placeholder:

  - id: "get_stock_price_history"
    title: "Get Stock Price History"
    content: "Fetch historical stock price data for a given symbol over a specified time period. Returns price history data that can be visualized as sparkline charts."
    keywords:
      - "stock price"
      - "price history"
      - "stock chart"
      - "historical data"
      - "stock performance"
    metadata:
      enabled: true
      source: "mcp-discovery"
      category: "finance"
      provider: "alphavantage"
      updated: "2025-04-07"
    runtime:
      provider: "alphavantage"
      tool_name: "get_stock_price_history"
      transport: "mcp"
      endpoint:
        type: mcp
        url: http://localhost:9001/mcp
        tool: get_stock_price_history
      params:
        symbols: { type: "array", items: { type: "string" } }
        period: { type: "string" }
    artifact:
      produces_artifact: true
      injection_mode: verbatim
      artifact_type: svg
      artifact_key: svg
      placeholder: "{{ARTIFACT:stock_chart_svg}}"
```

### Field Compatibility

- **New fields**: Additional YAML fields are ignored - won't break the system
- **Missing optional fields**: Uses defaults (empty list for keywords, empty dict for metadata)
- **Required fields**: Must be present or system will fail to load documents

## Search Parameters Reference

### Lexical Search Parameters

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `query` | string | required | - | Search query text |
| `temperature` | float | 0.7 | 0.1-10.0 | Softmax temperature control |
| `llm_tools_cutoff` | float | 8.0 | 0-100 | Minimum softmax percentage |
| `ignore_zero` | boolean | true | - | Filter zero BM25 scores |
| `max_results` | integer | 10 | 1-100 | Maximum number of results to return |

### Hybrid Search Parameters (BM25S + ColBERT)

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `hybrid_search` | boolean | false | - | Enable hybrid BM25S + ColBERT search |
| `query` | string | required | - | Search query text |
| `temperature` | float | 0.7 | 0.1-10.0 | Softmax temperature control (applies to both models) |
| `bm25_weight` | float | 0.4 | 0.0-1.0 | Weight for BM25S lexical scores (normalized internally) |
| `colbert_weight` | float | 0.6 | 0.0-1.0 | Weight for ColBERT semantic scores (normalized internally) |
| `candidate_limit` | integer | 100 | 10-500 | Number of candidates to consider from each model |
| `min_hybrid_score` | float | 0.0 | 0.0-1.0 | Minimum hybrid score threshold |
| `max_results` | integer | 10 | 1-100 | Maximum number of results to return |

### Parameter Effects

#### Temperature Impact

**Understanding Temperature Effects**

Temperature controls how "sharp" or "flat" the softmax distribution is:

- **If you go above 1.0 (High Temp)**: You are "flattening" the distribution. You make it harder for the top choice to win. The probabilities get closer together (everything becomes more "random").

- **If you go below 1.0 (Low Temp)**: You are "sharpening" the distribution. You make the top choice stand out significantly more than the others.

**Practical Temperature Ranges**

- **0.1-0.5**: Very focused results, high contrast between top and lower scores
- **0.5-1.5**: Balanced results, good for most use cases  
- **1.5-5.0**: More uniform distribution, less dramatic score differences
- **5.0-10.0**: Very uniform scores, useful for exploration

#### Hybrid Search Weights

**BM25 Weight vs ColBERT Weight**

In hybrid search, weights control the balance between lexical precision and semantic recall:

- **bm25_weight=0.4, colbert_weight=0.6**: Recommended starting point - semantic-heavy with lexical precision
- **bm25_weight=0.6, colbert_weight=0.4**: Lexical-heavy with semantic awareness
- **bm25_weight=0.5, colbert_weight=0.5**: Balanced 50/50 approach

Weights are normalized internally, so `0.4 + 0.6`, `4 + 6`, and `40 + 60` all represent the same blend.

#### Cutoff Percentage (Lexical Search Only)
- **0-5%**: Very inclusive, most documents pass
- **5-15%**: Standard range, good balance
- **15-30%**: Restrictive, only highly relevant documents
- **30%+**: Very restrictive, only top matches

#### Min Hybrid Score (Hybrid Search Only)
- **0.0-0.25**: Very inclusive, include weak matches
- **0.25-0.40**: Standard range, good for exploration
- **0.40-0.60**: Restrictive, only plausible matches
- **0.60+**: Very restrictive, only strong matches

## Response Format

### Lexical Search Response

```json
{
  "success": true,
  "message": "Documents retrieved successfully",
  "documents": [
    {
      "id": "create_order",
      "title": "Create New Order",
      "content": "Start a new purchase, buy a product, or place a customer order.",
      "keywords": ["buy", "purchase", "place order", "checkout"],
      "metadata": {
        "category": "orders",
        "provider": "internal"
      },
      "runtime": {
        "provider": "internal",
        "tool_name": "create_order",
        "transport": "http",
        "endpoint": "/api/orders",
        "params": {
          "customer_id": {"type": "string"},
          "product_id": {"type": "string"}
        }
      },
      "artifact": {
        "produces_artifact": false
      },
      "bm25_score": 2.456,
      "softmax_score": 0.1234
    }
  ],
  "total_retrieved": 15,
  "cutoff_percentage": 8.0,
  "settings": {
    "temperature": 0.7,
    "ignore_zero": true,
    "llm_tools_cutoff": 8.0,
    "max_results": 10
  }
}
```

### Hybrid Search Response

```json
{
  "success": true,
  "message": "Documents retrieved successfully",
  "documents": [
    {
      "id": "get_customer_orders",
      "title": "Get Customer Orders",
      "content": "Returns a list of all historical purchases and transaction history.",
      "keywords": ["order history", "purchase history", "past orders"],
      "metadata": {
        "category": "orders",
        "provider": "internal"
      },
      "runtime": {
        "provider": "internal",
        "tool_name": "get_customer_orders",
        "transport": "http",
        "endpoint": "/api/customers/{customer_id}/orders"
      },
      "artifact": {
        "produces_artifact": false
      },
      "bm25_score": 1.234,
      "bm25_rank": 2,
      "bm25_softmax_score": 0.089,
      "colbert_score": 0.876,
      "colbert_rank": 1,
      "colbert_softmax_score": 0.234,
      "hybrid_score": 0.678
    }
  ],
  "total_retrieved": 15,
  "settings": {
    "hybrid_search": true,
    "temperature": 0.7,
    "bm25_weight": 0.4,
    "colbert_weight": 0.6,
    "candidate_limit": 100,
    "min_hybrid_score": 0.4,
    "max_results": 10
  }
}
```

## Search Best Practices

### For Best Results

1. **Use Action Language and Domain Terms**
   - AxioLex excels at matching tool names, commands, and domain-specific vocabulary
   - Instead of: "programming"
   - Try: "place buy order", "process refund", "check inventory"

2. **Experiment with Temperature**
   - Start with 0.7 (default)
   - Increase for more uniform results (exploration)
   - Decrease for more focused results (precision)

3. **Try Hybrid Search for Semantic Queries**
   - Enable hybrid search when queries use different terminology than tool names
   - Example: "find purchases" should match "get_customer_orders" semantically
   - Start with bm25_weight=0.4, colbert_weight=0.6

4. **Adjust Cutoff Appropriately**
   - Use higher cutoff for precision (lexical search)
   - Use lower cutoff for recall (lexical search)
   - Use min_hybrid_score for hybrid search filtering

5. **Use Max Tools to Limit Context**
   - Limit results to keep LLM context manageable
   - Typical range: 5-10 tools for most use cases

6. **Compare Results in the Web UI**
   - Use the Discover tab to compare temperature effects
   - Toggle hybrid search to see semantic vs lexical differences
   - Look at both BM25 and hybrid scores

### Common Use Cases

#### Tool Routing for LLM Context
```python
# Focused search for best tool matches
from axiolex import BM25SClient

client = BM25SClient("http://localhost:9700")
results = client.retrieve(
    "place a buy order",
    temperature=0.5,
    llm_tools_cutoff=15.0,
    ignore_zero=True,
    max_results=5  # Keep LLM context small
)

# Pass only the top tools to the LLM
tools_for_llm = [doc['runtime'] for doc in results['documents']]
```

#### Semantic Discovery with Hybrid Search
```python
# Hybrid search for semantic understanding
results = client.retrieve(
    "find purchases that have not completed",
    hybrid_search=True,
    temperature=0.7,
    bm25_weight=0.4,
    colbert_weight=0.6,
    candidate_limit=100,
    min_hybrid_score=0.4,
    max_results=10
)
```

#### Broad Exploration
```python
# Broad search with uniform scoring for exploration
results = client.retrieve(
    "customer order management",
    temperature=2.0,
    llm_tools_cutoff=2.0,
    ignore_zero=True,
    max_results=20
)
```

## Troubleshooting

### Common Issues

1. **No Results Found**
   - Check query spelling and terminology
   - Try more general terms or different phrasing
   - Lower the cutoff percentage (lexical search)
   - Disable "ignore_zero" option to see all documents
   - Try hybrid search if semantic understanding might help

2. **Too Many Results**
   - Increase cutoff percentage (lexical search)
   - Use more specific query terms with domain vocabulary
   - Increase temperature for better score distribution
   - Reduce max_results to limit output
   - Increase min_hybrid_score for hybrid search

3. **Unexpected Rankings**
   - Try different temperature values
   - Check document content and keywords
   - Verify documents are properly indexed
   - Try hybrid search for semantic matching
   - Adjust bm25_weight and colbert_weight in hybrid mode

4. **Hybrid Search Not Available**
   - Verify `axiolex[colbert]` is installed: `pip install "axiolex[colbert]"`
   - Check that `AXIOLEX_HYBRID_ENABLED=true` is set
   - Ensure ColBERT model has been downloaded and indexed
   - Check server logs for ColBERT initialization errors

5. **API Errors**
   - Verify server is running on port 9700 (not 9200)
   - Check JSON payload format
   - Ensure all required parameters are provided
   - Verify Redis is running if using MCP tool catalog

6. **MCP Tools Not Showing**
   - Check Redis connection: `axiolex-index status`
   - Refresh the catalog: `axiolex-index refresh`
   - Verify MCP providers are enabled in mcp_providers.yaml
   - Check MCP server connectivity and authentication

### Performance Tips

- **Index Size**: Larger indexes may be slower; consider filtering by category
- **Query Complexity**: Simple queries are faster
- **Temperature Effects**: Very low temperatures can be computationally intensive
- **Cutoff Filtering**: Higher cutoffs reduce processing time
- **Hybrid Search**: ColBERT adds semantic search overhead; use when needed
- **Candidate Limit**: Reduce candidate_limit in hybrid search for faster queries
- **Max Results**: Lower max_results reduces response size and processing

### Getting Help

For more advanced usage and integration examples, refer to:
- Main documentation: https://vrraj.github.io/axiolex/
- GitHub repository: https://github.com/vrraj/axiolex
- Demo Web UI: http://localhost:9700 (when running locally)
