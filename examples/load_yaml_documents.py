#!/usr/bin/env python3
"""
Sample script: External Context Loading via YAML

This script demonstrates how to:
1. Load a custom context registry (tools, documents, or chunks) from YAML
2. Plug it directly into the BM25S retrieval layer
3. Perform lexical search and ranking over external data
4. Mix static (YAML) and dynamic (programmatic) context sources

This enables:
- External tool registries for LLM routing
- Document/chunk loading for RAG pipelines
- Config-driven context injection without code changes
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from axiolex import BM25SRetriever, Document


def load_from_yaml_example():
    """Example of loading context items from a YAML file."""
    print("=== Loading Context Items from YAML File ===")
    
    # Load from the default YAML file
    retriever = BM25SRetriever(document_file="source_files/tools_list.yaml")
    
    print(f"Loaded {len(retriever.documents)} context items from YAML")
    
    # Show first few context items
    print("\nSample context items:")
    for i, doc in enumerate(retriever.documents[:3]):
        print(f"  {i+1}. {doc.title} (ID: {doc.id})")
        print(f"     Keywords: {', '.join(doc.keywords[:3])}...")
    
    return retriever


def search_examples(retriever):
    """Demonstrate different search queries and configurations."""
    print("\n=== Search Examples ===")
    
    queries = [
        "customer profile lookup",
        "order tracking", 
        "refund process",
        "inventory check",
        "support ticket"
    ]
    
    for query in queries:
        # Default search
        results = retriever.retrieve_documents(query)
        
        print(f"\nQuery: '{query}'")
        print(f"Found {len(results['documents'])} results:")
        
        for i, doc in enumerate(results['documents'][:3]):
            print(f"  {i+1}. {doc['title']}")
            print(f"     Score: {doc['bm25_score']:.2f}")
            print(f"     ID: {doc['id']}")


def temperature_comparison(retriever):
    """Compare search results with different temperature settings."""
    print("\n=== Temperature Comparison ===")
    
    query = "customer order"
    temperatures = [0.3, 0.7, 1.5]
    
    for temp in temperatures:
        results = retriever.retrieve_documents(query, temperature=temp)
        
        print(f"\nTemperature {temp}:")
        print(f"Results: {len(results['documents'])} documents")
        
        for i, doc in enumerate(results['documents'][:2]):
            print(f"  {i+1}. {doc['title']} (Score: {doc['bm25_score']:.2f})")


def custom_yaml_example():
    """Example with a custom YAML context registry structure."""
    print("\n=== Custom YAML Context Registry Example ===")
    
    # Create a sample custom YAML context registry structure.
    # These examples are tools, but the same schema can represent documents or chunks.
    custom_yaml_content = """
documents:
  - id: "search_products"
    title: "Search Products"
    content: "Find products by name, category, or specifications"
    keywords: ["find products", "product search", "browse items", "catalog"]
    metadata:
      item_type: "tool"
      category: "catalog"
      priority: "high"
      
  - id: "get_product_details"
    title: "Get Product Details"
    content: "Retrieve detailed information about a specific product including price, description, and availability"
    keywords: ["product info", "item details", "specifications", "pricing"]
    metadata:
      item_type: "tool"
      category: "catalog"
      priority: "medium"
      
  - id: "add_to_cart"
    title: "Add to Cart"
    content: "Add items to shopping cart for checkout"
    keywords: ["cart", "add item", "shopping", "checkout"]
    metadata:
      item_type: "tool"
      category: "ecommerce"
      priority: "high"
"""
    
    # Write to temporary file
    temp_file = "temp_custom_documents.yaml"
    with open(temp_file, 'w') as f:
        f.write(custom_yaml_content)
    
    try:
        # Load from custom file
        custom_retriever = BM25SRetriever(document_file=temp_file)
        print(f"Loaded {len(custom_retriever.documents)} custom context items")
        
        # Search in custom documents
        results = custom_retriever.retrieve_documents("product information")
        print(f"\nSearch 'product information': {len(results['documents'])} results")
        
        for doc in results['documents']:
            print(f"  - {doc['title']} (Score: {doc['bm25_score']:.2f})")
            
    finally:
        # Clean up temp file
        if os.path.exists(temp_file):
            os.remove(temp_file)


def document_management_example():
    """Example of mixing YAML-loaded and programmatic context items."""
    print("\n=== Context Registry Management Example ===")
    
    # Start with YAML documents
    retriever = BM25SRetriever(document_file="source_files/tools_list.yaml")
    initial_count = len(retriever.documents)
    print(f"Initially loaded: {initial_count} context items")
    
    # Add context items programmatically.
    # The public API uses Document as the storage object, but these can represent tools,
    # documents, chunks, workflow actions, or other retrievable context records.
    new_docs = [
        Document(
            id="custom_api_call",
            title="Custom API Integration",
            content="Call external APIs for data integration and processing",
            keywords=["api", "integration", "external", "data"],
            metadata={"item_type": "tool", "category": "integration"}
        ),
        Document(
            id="data_export",
            title="Export Data",
            content="Export data in various formats like CSV, JSON, or XML",
            keywords=["export", "csv", "json", "xml", "download"],
            metadata={"item_type": "tool", "category": "data"}
        )
    ]
    
    retriever.add_documents(new_docs)
    final_count = len(retriever.documents)
    print(f"Added {len(new_docs)} context items programmatically")
    print(f"Total context items: {final_count}")
    
    # Search across all documents
    results = retriever.retrieve_documents("data processing")
    print(f"\nSearch 'data processing': {len(results['documents'])} results")
    
    for doc in results['documents'][:3]:
        print(f"  - {doc['title']} (ID: {doc['id']})")


if __name__ == "__main__":
    print("BM25S Retriever - External YAML Context Examples")
    print("=" * 50)
    
    try:
        # Run all examples
        retriever = load_from_yaml_example()
        search_examples(retriever)
        temperature_comparison(retriever)
        custom_yaml_example()
        document_management_example()
        
        print("\n" + "=" * 50)
        print("All examples completed successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure the source_files/tools_list.yaml file exists")
        print("You can use the same YAML-driven pattern for tools, documents, chunks, or workflow context.")
        sys.exit(1)
