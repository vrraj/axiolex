#!/usr/bin/env python3
"""
Sample script: REST API Document Management

This script demonstrates how to:
1. Use the BM25SClient for HTTP API operations
2. Add documents via REST API
3. Search documents via REST API
4. Manage documents (get, update, delete) via API
5. Handle API errors and responses

Note: Requires the BM25S server to be running on localhost:9200
Start server with: axiolex-server --config settings.yaml
"""

import sys
import time
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from axiolex import BM25SClient, Document


def check_server_connection(client):
    """Check if the server is running and accessible."""
    print("=== Checking Server Connection ===")
    
    try:
        settings = client.get_settings()
        print("✅ Server connection successful")
        print(f"Current settings: {settings}")
        return True
    except Exception as e:
        print(f"❌ Server connection failed: {e}")
        print("Make sure the server is running: axiolex-server --config settings.yaml")
        return False


def add_documents_via_api(client):
    """Example of adding documents via REST API."""
    print("\n=== Adding Documents via API ===")

    # Sample documents to add
    documents = [
        Document(
            id="api_search_products",
            title="Search Products API",
            content="REST API endpoint for searching products by name, category, or filters",
            keywords=["search", "products", "api", "filter", "catalog"],
            metadata={
                "endpoint": "/products/search",
                "method": "GET",
                "category": "api"
            }
        ),
        Document(
            id="api_create_order",
            title="Create Order API",
            content="REST endpoint for creating new customer orders with validation and inventory checks",
            keywords=["create", "order", "api", "purchase", "checkout"],
            metadata={
                "endpoint": "/orders",
                "method": "POST",
                "category": "api"
            }
        ),
        Document(
            id="api_user_auth",
            title="User Authentication API",
            content="Handle user login, logout, and token management for secure access",
            keywords=["auth", "login", "token", "security", "session"],
            metadata={
                "endpoint": "/auth",
                "method": "POST",
                "category": "security"
            }
        )
    ]

    added_count = 0
    for doc in documents:
        try:
            result = client.add_document(doc)
            if result.get('success'):
                print(f"✅ Added: {doc.title}")
                added_count += 1
            else:
                print(f"❌ Failed to add: {doc.title} - {result.get('message', 'Unknown error')}")
        except Exception as e:
            print(f"❌ Error adding {doc.title}: {e}")

    print(f"\nSuccessfully added {added_count}/{len(documents)} documents")
    return added_count


def search_via_api(client):
    """Example of searching documents via REST API."""
    print("\n=== Searching via API ===")

    search_queries = [
        "product search",
        "order creation",
        "user authentication",
        "api endpoints",
        "security tokens"
    ]

    for query in search_queries:
        try:
            # Basic search
            results = client.retrieve(query)

            print(f"\nQuery: '{query}'")
            print(f"Found {len(results.documents)} results")

            # Show top results
            for i, doc in enumerate(results.documents[:3]):
                print(f"  {i+1}. {doc.title}")
                print(f"     Score: {doc.bm25_score:.2f}")
                print(f"     ID: {doc.id}")

            # Show search settings
            if results.settings:
                settings = results.settings
                print(f"     Search temp: {settings.get('temperature', 'N/A')}")

        except Exception as e:
            print(f"❌ Search error for '{query}': {e}")


def advanced_search_examples(client):
    """Examples of advanced search with different parameters."""
    print("\n=== Advanced Search Examples ===")

    query = "user authentication"

    # Search with different temperatures
    temperatures = [0.3, 0.7, 1.5]

    print(f"\nComparing temperatures for query: '{query}'")
    for temp in temperatures:
        try:
            results = client.retrieve(query, temperature=temp)
            print(f"Temperature {temp}: {len(results.documents)} results")

            if results.documents:
                top_doc = results.documents[0]
                print(f"  Top: {top_doc.title} (Score: {top_doc.bm25_score:.2f})")

        except Exception as e:
            print(f"❌ Error with temperature {temp}: {e}")

    # Search with filtering
    print(f"\nSearch with zero-relevance filtering:")
    try:
        results = client.retrieve(query, ignore_zero=True, llm_tools_cutoff=10.0)
        print(f"Filtered results: {len(results.documents)} documents")
        print(f"Cutoff percentage: {results.cutoff_percentage}%")

    except Exception as e:
        print(f"❌ Error with filtered search: {e}")


def document_management_via_api(client):
    """Example of document management operations."""
    print("\n=== Document Management via API ===")

    try:
        # Get all documents
        all_docs = client.get_documents()
        print(f"Total documents in system: {all_docs.get('count', 0)}")

        # Show sample documents
        if 'documents' in all_docs and all_docs['documents']:
            print("\nSample documents:")
            for i, doc in enumerate(all_docs['documents'][:5]):
                print(f"  {i+1}. {doc['title']} (ID: {doc['id']})")

        # Update a document
        doc_to_update = "api_search_products"
        updated_doc = Document(
            id=doc_to_update,
            title="Search Products API (Updated)",
            content="Enhanced REST API endpoint for advanced product search with filtering and pagination",
            keywords=["search", "products", "api", "filter", "pagination", "enhanced"],
            metadata={
                "endpoint": "/products/search",
                "method": "GET",
                "category": "api",
                "version": "2.0"
            }
        )

        print(f"\nUpdating document: {doc_to_update}")
        result = client.add_document(updated_doc)  # add_document works as update if ID exists

        if result.get('success'):
            print("✅ Document updated successfully")
        else:
            print(f"❌ Update failed: {result.get('message', 'Unknown error')}")

        # Verify update
        updated_results = client.retrieve("product search")
        if updated_results.documents:
            for doc in updated_results.documents:
                if doc.id == doc_to_update:
                    print(f"Verified: {doc.title}")
                    break

    except Exception as e:
        print(f"❌ Document management error: {e}")


def batch_operations_example(client):
    """Example of batch document operations."""
    print("\n=== Batch Operations Example ===")

    # Prepare batch of documents
    batch_docs = []
    categories = ["payment", "shipping", "inventory", "analytics"]

    for category in categories:
        doc = Document(
            id=f"api_{category}_endpoint",
            title=f"{category.title()} Management API",
            content=f"REST API endpoints for managing {category} operations and data",
            keywords=[category, "api", "management", "operations"],
            metadata={
                "category": "api",
                "domain": category
            }
        )
        batch_docs.append(doc)

    print(f"Adding {len(batch_docs)} documents in batch...")

    # Add documents one by one (simulating batch)
    success_count = 0
    for doc in batch_docs:
        try:
            result = client.add_document(doc)
            if result.get('success'):
                success_count += 1
                print(f"✅ Added: {doc.title}")
            else:
                print(f"❌ Failed: {doc.title}")
        except Exception as e:
            print(f"❌ Error: {e}")

    print(f"\nBatch operation completed: {success_count}/{len(batch_docs)} successful")

    # Search across batch-added documents
    try:
        results = client.retrieve("api management")
        print(f"\nSearch across batch documents: {len(results.documents)} results")

        for doc in results.documents[:3]:
            print(f"  - {doc.title} ({doc.metadata.get('domain', 'N/A')})")

    except Exception as e:
        print(f"❌ Batch search error: {e}")


def error_handling_examples(client):
    """Examples of handling various error scenarios."""
    print("\n=== Error Handling Examples ===")

    # Test with non-existent document
    print("Testing non-existent document retrieval...")
    try:
        result = client.retrieve("nonexistent_document_xyz")
        print(f"Search completed: {len(result.documents)} results (expected: 0)")
    except Exception as e:
        print(f"Expected error handled: {e}")


if __name__ == "__main__":
    print("BM25S Retriever - REST API Usage Examples")
    print("=" * 50)
    print("Note: Make sure server is running with: axiolex-server --config settings.yaml")
    print("=" * 50)
    
    # Initialize client
    client = BM25SClient("http://localhost:9200")
    
    try:
        # Check server connection first
        if not check_server_connection(client):
            print("\n❌ Cannot proceed without server connection")
            sys.exit(1)
        
        # Run all examples
        add_documents_via_api(client)
        search_via_api(client)
        advanced_search_examples(client)
        document_management_via_api(client)
        batch_operations_example(client)
        error_handling_examples(client)
        
        print("\n" + "=" * 50)
        print("All API examples completed successfully!")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Examples interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
