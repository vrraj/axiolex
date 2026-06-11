#!/usr/bin/env python3
"""
Test script for YAML document loading.
Run this to verify that YAML file loading works correctly.
"""

from axiolex import BM25SRetriever
import os

print("Testing YAML document loading...")
print("=" * 60)

# Test 1: Load from YAML file
print("\n1. Testing YAML file loading...")
yaml_file = "source_files/tools_list.yaml"

if not os.path.exists(yaml_file):
    print(f"❌ YAML file not found: {yaml_file}")
    print("   Create a YAML file or skip this test")
    exit(1)

try:
    retriever = BM25SRetriever(document_file=yaml_file)
    print(f"✅ Loaded {len(retriever.documents)} documents from YAML")
except Exception as e:
    print(f"❌ Failed to load from YAML: {e}")
    exit(1)

# Test 2: Search loaded documents
print("\n2. Testing search on YAML-loaded documents...")
try:
    results = retriever.retrieve_documents('customer profile')
    print(f"✅ Search completed")
    print(f"   Found {len(results['documents'])} results")
    if results['documents']:
        print(f"   Top result: {results['documents'][0]['title']}")
except Exception as e:
    print(f"❌ Search failed: {e}")
    exit(1)

print("\n" + "=" * 60)
print("✅ YAML loading test passed!")
print("=" * 60)
