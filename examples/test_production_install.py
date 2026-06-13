#!/usr/bin/env python3
"""
Test script for production PyPI installation.
Run this to verify that axiolex installs and works correctly.
"""

from axiolex import BM25SRetriever, Document

print("Testing axiolex production installation...")
print("=" * 60)

# Test 1: Import
print("\n1. Testing import...")
try:
    from axiolex import BM25SRetriever, Document
    print("✅ Import successful")
except Exception as e:
    print(f"❌ Import failed: {e}")
    exit(1)

# Test 2: Create retriever
print("\n2. Creating retriever...")
try:
    retriever = BM25SRetriever()
    print("✅ Retriever created")
except Exception as e:
    print(f"❌ Failed to create retriever: {e}")
    exit(1)

# Test 3: Add document
print("\n3. Adding document...")
try:
    doc = Document(
        id='test_doc',
        title='Test Document',
        content='This is a test document for BM25S retrieval',
        keywords=['test', 'document', 'bm25s']
    )
    retriever.add_documents([doc])
    print("✅ Document added")
except Exception as e:
    print(f"❌ Failed to add document: {e}")
    exit(1)

# Test 4: Search
print("\n4. Testing search...")
try:
    results = retriever.retrieve_documents('test document')
    print(f"✅ Search completed")
    print(f"   Found {len(results['documents'])} results")
    if results['documents']:
        print(f"   Top result: {results['documents'][0]['title']}")
except Exception as e:
    print(f"❌ Search failed: {e}")
    exit(1)

# Test 5: Check version
print("\n5. Checking version...")
try:
    from axiolex import __version__
    print(f"✅ Version: {__version__}")
except Exception as e:
    print(f"⚠️  Could not get version: {e}")

print("\n" + "=" * 60)
print("✅ All tests passed!")
print("=" * 60)
