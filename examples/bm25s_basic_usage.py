#!/usr/bin/env python3
"""
Basic usage example for BM25S Retriever package.

This example demonstrates:
1. Creating a retriever instance
2. Adding documents programmatically
3. Searching documents with BM25S
4. Using the client API for remote access
"""

from axiolex import BM25SRetriever, Document, BM25SClient


def basic_library_usage():
    """Example using the library directly."""
    print("=== BM25S Retriever - Library Usage ===")
    
    # Create retriever instance
    retriever = BM25SRetriever()
    
    # Add documents programmatically
    documents = [
        Document(
            id="doc1",
            title="Financial Planning Guide",
            content="A comprehensive guide to personal financial planning and investment strategies",
            keywords=["finance", "planning", "investment", "strategy"]
        ),
        Document(
            id="doc2", 
            title="Tax Optimization Tips",
            content="Effective tax optimization strategies for individuals and small businesses",
            keywords=["tax", "optimization", "business", "individual"]
        ),
        Document(
            id="doc3",
            title="Investment Portfolio Management",
            content="Best practices for managing diversified investment portfolios",
            keywords=["investment", "portfolio", "diversification", "management"]
        )
    ]
    
    retriever.add_documents(documents)
    print(f"Added {len(documents)} documents to retriever")
    
    # Search documents
    queries = [
        "investment strategies",
        "tax planning",
        "portfolio management"
    ]
    
    for query in queries:
        results = retriever.retrieve_documents(query)
        print(f"\nQuery: '{query}'")
        print(f"Found {len(results['documents'])} results:")
        for doc in results['documents']:
            print(f"  - {doc['title']}: {doc['bm25_score']:.2f}")


def client_api_usage(base_url="http://localhost:9200"):
    """Example using the client API (requires server running)."""
    print("\n=== BM25S Retriever - Client API Usage ===")
    
    try:
        client = BM25SClient(base_url)
        
        # Get current settings
        settings = client.get_settings()
        print(f"Current settings: {settings}")
        
        # Search documents
        results = client.retrieve("investment strategies")
        print(f"\nSearch results: {len(results['documents'])} documents found")
        for doc in results['documents']:
            print(f"  - {doc['title']}: {doc['bm25_score']:.2f}")
        
        # Add a new document
        new_doc = {
            "id": "example_doc",
            "title": "Example Document",
            "content": "This is an example document added via API",
            "keywords": ["example", "api", "document"]
        }
        
        result = client.add_document(new_doc)
        print(f"\nAdded document: {result['success']}")
        
    except Exception as e:
        print(f"Note: Client API requires server running at {base_url}")
        print(f"Error: {e}")


def document_management_example():
    """Example of document management operations."""
    print("\n=== Document Management Example ===")
    
    retriever = BM25SRetriever()
    
    # Create sample document
    doc = Document(
        id="sample_doc",
        title="Sample Technical Document",
        content="This document covers technical aspects of BM25S retrieval systems, including indexing, scoring, and search algorithms.",
        keywords=["bm25s", "retrieval", "indexing", "scoring", "search"],
        metadata={"category": "technical", "priority": "high"}
    )
    
    # Add document
    retriever.add_documents([doc])
    print(f"Added document: {doc.title}")
    
    # Search with different parameters
    search_params = [
        {"query": "bm25s retrieval", "temperature": 0.5},
        {"query": "indexing algorithms", "temperature": 1.0},
        {"query": "search scoring", "temperature": 0.7, "ignore_zero": True}
    ]
    
    for params in search_params:
        results = retriever.retrieve_documents(**params)
        print(f"\nSearch: '{params['query']}' (temp={params.get('temperature', 0.7)})")
        print(f"Results: {len(results['documents'])} documents")
        if results['documents']:
            print(f"Top result: {results['documents'][0]['title']} (score: {results['documents'][0]['bm25_score']:.2f})")


if __name__ == "__main__":
    print("BM25S Retriever - Basic Usage Examples")
    print("=" * 50)
    
    # Run examples
    basic_library_usage()
    document_management_example()
    client_api_usage()
    
    print("\n" + "=" * 50)
    print("Examples completed!")
    print("\nTo run the client API example:")
    print("1. Start the server: bm25s-server --config settings.yaml")
    print("2. Run this script again")
