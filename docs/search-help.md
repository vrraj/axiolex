# BM25S Search Guide

This guide shows you how to use the search functionality in BM25S Retriever, both through the web interface and via API calls.

## Using the Search Tab

### Accessing the Search Interface

1. **Open the Web Interface**
   - Navigate to `http://localhost:9200` in your browser
   - Click on the "Search Testing" tab

### Search Query Interface

#### Basic Search

1. **Enter Your Query**
   - Type your search query in the "Query" text box
   - Example: "machine learning algorithms"

2. **Configure Search Parameters**
   - **Temperature**: Controls softmax uniformity (0.1-10.0)
     - Lower values (0.1-1.0): More focused results
     - Higher values (1.0-10.0): More uniform distribution
   - **Cutoff %**: Minimum softmax percentage (0-100)
     - Filters out results below this relevance threshold
   - **Filter zero-relevance documents**: 
     - When checked, excludes documents with BM25 score of 0

3. **Perform Search**
   - Click "Search Documents" button
   - Or press Enter in the query field

#### Understanding Search Results

The search results table displays:

- **Document ID**: Unique identifier for each document
- **Title**: Document title
- **Content**: First 150 characters of document content
- **BM25 Score**: Raw BM25 relevance score (higher = more relevant)
- **Softmax @ Temp 1.0**: Relevance percentage with temperature 1.0
- **Softmax @ Temp [Your Temp]**: Relevance percentage with your chosen temperature

#### Advanced Search Techniques

1. **Temperature Experiments**
   - Try different temperatures to see how it affects relevance distribution
   - Compare "Softmax @ Temp 1.0" vs "Softmax @ Temp [Your Temp]" columns
   - Lower temperature = more dramatic score differences
   - Higher temperature = more uniform scores

2. **Cutoff Adjustment**
   - Increase cutoff to get only highly relevant results
   - Decrease cutoff to include more documents
   - Set to 0 to include all documents with non-zero BM25 scores

3. **Zero-Relevance Filtering**
   - Keep checked to exclude documents that don't match your query
   - Uncheck to see all documents (useful for analysis)

### Search Tips

- **Specific Queries**: Use specific terms for better results
- **Multiple Terms**: Combine concepts like "python programming tutorial"
- **Experiment**: Try different temperatures to find your sweet spot
- **Compare Results**: Use the dual temperature display to understand score distribution

## Search API Calls

### Basic Search Endpoint

```bash
curl -X POST http://localhost:9200/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "query": "machine learning algorithms",
    "temperature": 0.7,
    "llm_tools_cutoff": 8.0,
    "ignore_zero": true
  }'
```

### Advanced Search Parameters

```bash
curl -X POST http://localhost:9200/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "query": "python data science",
    "temperature": 1.2,
    "llm_tools_cutoff": 5.0,
    "ignore_zero": false
  }'
```

### Python Search Implementation

```python
import requests
import json

class BM25SSearcher:
    def __init__(self, base_url="http://localhost:9200"):
        self.base_url = base_url
        self.retrieve_url = f"{base_url}/retrieve"
    
    def search(self, query, temperature=0.7, cutoff=8.0, ignore_zero=True):
        """Search documents with BM25S retriever."""
        
        payload = {
            "query": query,
            "temperature": temperature,
            "llm_tools_cutoff": cutoff,
            "ignore_zero": ignore_zero
        }
        
        try:
            response = requests.post(self.retrieve_url, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}
    
    def search_and_format(self, query, **kwargs):
        """Search and return formatted results."""
        result = self.search(query, **kwargs)
        
        if not result.get("success"):
            return f"Search failed: {result.get('error', 'Unknown error')}"
        
        output = [
            f"Found {len(result['documents'])} documents (from {result['total_retrieved']} total)",
            f"Using temperature: {result['settings']['temperature']}",
            f"Cutoff: {result['cutoff_percentage']}%",
            ""
        ]
        
        for i, doc in enumerate(result["documents"], 1):
            output.extend([
                f"--- Document {i} ---",
                f"ID: {doc['id']}",
                f"Title: {doc['title']}",
                f"Content: {doc['content'][:100]}{'...' if len(doc['content']) > 100 else ''}",
                f"Keywords: {', '.join(doc.get('keywords', []))}",
                f"BM25 Score: {doc['bm25_score']:.3f}",
                f"Softmax Score: {doc['softmax_score']*100:.2f}%",
                ""
            ])
        
        return "\n".join(output)

# Example usage
if __name__ == "__main__":
    searcher = BM25SSearcher()
    
    # Basic search
    print("=== Basic Search ===")
    print(searcher.search_and_format("machine learning"))
    
    # Search with custom parameters
    print("\n=== Advanced Search ===")
    print(searcher.search_and_format(
        "python programming",
        temperature=1.5,
        cutoff=10.0,
        ignore_zero=False
    ))
    
    # Compare temperatures
    print("\n=== Temperature Comparison ===")
    query = "data science"
    
    print(f"Results for '{query}' with temperature 0.5:")
    print(searcher.search_and_format(query, temperature=0.5))
    
    print(f"\nResults for '{query}' with temperature 2.0:")
    print(searcher.search_and_format(query, temperature=2.0))
```

### Batch Search Implementation

```python
def batch_search(queries, temperatures=[0.5, 1.0, 1.5]):
    """Perform multiple searches with different parameters."""
    searcher = BM25SSearcher()
    results = {}
    
    for query in queries:
        results[query] = {}
        
        for temp in temperatures:
            result = searcher.search(query, temperature=temp)
            if result.get("success"):
                results[query][f"temp_{temp}"] = {
                    "count": len(result["documents"]),
                    "top_doc": result["documents"][0]["id"] if result["documents"] else None,
                    "avg_score": sum(doc["softmax_score"] for doc in result["documents"]) / len(result["documents"]) if result["documents"] else 0
                }
    
    return results

# Example batch search
queries = ["machine learning", "python", "data science"]
batch_results = batch_search(queries)

for query, temps in batch_results.items():
    print(f"\nQuery: {query}")
    for temp_key, stats in temps.items():
        print(f"  {temp_key}: {stats['count']} docs, avg: {stats['avg_score']:.3f}")
```

## Document Structure and Indexing

### Which YAML Fields Are Indexed

The BM25S retriever indexes specific fields from your YAML documents to enable searching:

#### Indexed Fields (Searchable)
- **`title`** - Document title, fully searchable
- **`content`** - Document content/description, fully searchable  
- **`keywords`** - Keyword list, each keyword prefixed with "keyword:" for search

#### Stored Fields (Not Searchable)
- **`id`** - Document identifier, stored for retrieval but not searched
- **`parameters`** - Function parameters, stored in metadata only
- **`metadata`** - All metadata fields, stored but not indexed

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
4. **Avoid**: Don't put searchable content in `id`, `parameters`, or `metadata` fields

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
    parameters:
      customer_id: { type: "string" }
      product_id: { type: "string" }
      quantity: { type: "integer", minimum: 1 }
      price: { type: "number" }
    metadata:
      source: "yaml"
      category: "orders"
      provider: "internal"
      updated: "2025-04-07"
```

### Field Compatibility

- **New fields**: Additional YAML fields are ignored - won't break the system
- **Missing optional fields**: Uses defaults (empty list for keywords, empty dict for metadata)
- **Required fields**: Must be present or system will fail to load documents

## Search Parameters Reference

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `query` | string | required | - | Search query text |
| `temperature` | float | 0.7 | 0.1-10.0 | Softmax temperature control |
| `llm_tools_cutoff` | float | 8.0 | 0-100 | Minimum softmax percentage |
| `ignore_zero` | boolean | true | - | Filter zero BM25 scores |

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

#### Cutoff Percentage
- **0-5%**: Very inclusive, most documents pass
- **5-15%**: Standard range, good balance
- **15-30%**: Restrictive, only highly relevant documents
- **30%+**: Very restrictive, only top matches

## Response Format

```json
{
  "success": true,
  "message": "Documents retrieved successfully",
  "documents": [
    {
      "id": "doc1",
      "title": "Document Title",
      "content": "Full document content...",
      "keywords": ["keyword1", "keyword2"],
      "metadata": {},
      "bm25_score": 2.456,
      "softmax_score": 0.1234
    }
  ],
  "total_retrieved": 15,
  "cutoff_percentage": 8.0,
  "settings": {
    "temperature": 0.7,
    "ignore_zero": true,
    "llm_tools_cutoff": 8.0
  }
}
```

## Search Best Practices

### For Best Results

1. **Use Specific Terms**
   - Instead of: "programming"
   - Try: "python programming tutorial"

2. **Experiment with Temperature**
   - Start with 0.7 (default)
   - Increase for more uniform results
   - Decrease for more focused results

3. **Adjust Cutoff Appropriately**
   - Use higher cutoff for precision
   - Use lower cutoff for recall

4. **Compare Results**
   - Use the web interface to compare temperature effects
   - Look at both BM25 and softmax scores

### Common Use Cases

#### Research and Analysis
```python
# Comprehensive search with low cutoff
searcher.search_and_format(
    "machine learning algorithms",
    temperature=1.0,
    cutoff=2.0,
    ignore_zero=False
)
```

#### Quick Lookup
```python
# Focused search for best matches
searcher.search_and_format(
    "python lists",
    temperature=0.5,
    cutoff=15.0,
    ignore_zero=True
)
```

#### Exploration
```python
# Broad search with uniform scoring
searcher.search_and_format(
    "data science",
    temperature=3.0,
    cutoff=5.0,
    ignore_zero=True
)
```

## Troubleshooting

### Common Issues

1. **No Results Found**
   - Check query spelling
   - Try more general terms
   - Lower the cutoff percentage
   - Disable "ignore_zero" option

2. **Too Many Results**
   - Increase cutoff percentage
   - Use more specific query terms
   - Increase temperature for better score distribution

3. **Unexpected Rankings**
   - Try different temperature values
   - Check document content and keywords
   - Verify documents are properly indexed

4. **API Errors**
   - Verify server is running on port 9200
   - Check JSON payload format
   - Ensure all required parameters are provided

### Performance Tips

- **Index Size**: Larger indexes may be slower
- **Query Complexity**: Simple queries are faster
- **Temperature Effects**: Very low temperatures can be computationally intensive
- **Cutoff Filtering**: Higher cutoffs reduce processing time

For more advanced usage and integration examples, refer to the main documentation at `http://localhost:9200/docs`.
