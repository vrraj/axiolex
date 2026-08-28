#!/usr/bin/env python3
"""
End-to-end test for the installed axiolex package against a live Redis catalog.

Verifies that the published package can:
- import correctly from site-packages
- connect to Redis and load the tool catalog
- run discover_tools against the real catalog (lexical + hybrid)
- run direct BM25S retrieval against the real catalog

Quick start (5 minutes):

    1. Install the package:
       pip install axiolex

    2. Get a free Tavily API key (for the sample MCP provider):
       Sign up at https://tavily.com and copy your API key.

    3. Start Redis (any method). For example with Docker:
       docker run -d --name redis -p 6380:6379 redis:7

    4. Copy .env.example to .env and add your Tavily key:
       cp .env.example .env
       # Edit .env and set: TAVILY_API_KEY=tvly-xxxxxxxx

    5. Populate the catalog (uses shipped sample files by default):
       axiolex-index refresh

    6. Run this script:
       python test_axiolex_package.py
       # Or with your own query:
       python test_axiolex_package.py --query "search the web for AI news"

Environment variables (defaults shown):
    AXIOLEX_REDIS_HOST=localhost
    AXIOLEX_REDIS_PORT=6380
    AXIOLEX_REDIS_DB=0
"""

import argparse
import os
import sys

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import axiolex
from axiolex import discover_tools, __version__
from axiolex.core.retriever import get_tool_discovery_retriever


def _print_tools(query, result):
    print(f"\nQuery: {query}")
    print(f"Mode: {result.get('search_mode', 'unknown')}")
    print(f"Returned {result.get('count', 0)} tool(s)")
    for rank, tool in enumerate(result.get("tools", []), 1):
        score_parts = [f"bm25_score={tool.get('bm25_score')}"]
        if tool.get("colbert_score") is not None:
            score_parts.append(f"colbert_score={tool.get('colbert_score')}")
        if tool.get("hybrid_score") is not None:
            score_parts.append(f"hybrid_score={tool.get('hybrid_score')}")
        score_str = ", ".join(score_parts)
        print(f"  {rank}. {tool['name']} ({tool.get('provider', 'unknown')}) — {score_str}")


def main():
    parser = argparse.ArgumentParser(description="Axiolex package end-to-end test")
    parser.add_argument(
        "--query",
        default=None,
        help="Custom query to test with (default: runs built-in sample queries)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("AxioLex package end-to-end test")
    print(f"Version: {__version__}")
    print(f"Imported from: {axiolex.__file__}")
    print("=" * 60)

    # --- Connect to Redis-backed catalog ---
    redis_host = os.getenv("AXIOLEX_REDIS_HOST", "localhost")
    redis_port = os.getenv("AXIOLEX_REDIS_PORT", "6380")
    redis_db = os.getenv("AXIOLEX_REDIS_DB", "0")
    print(f"\nConnecting to Redis at {redis_host}:{redis_port}/{redis_db}...")

    try:
        retriever = get_tool_discovery_retriever()
        doc_count = retriever.get_document_count()
    except RuntimeError as e:
        print(f"\nERROR: {e}")
        print("\nRedis is not running or the catalog is empty.")
        print("Prerequisites:")
        print("  1. Start Redis")
        print("  2. Populate the catalog: axiolex-index refresh")
        print("  3. Re-run this script")
        sys.exit(1)

    print(f"Connected. Catalog has {doc_count} tools.")

    if doc_count == 0:
        print("\nERROR: Redis catalog is empty.")
        print("Run: axiolex-index refresh")
        sys.exit(1)

    # --- Determine queries to run ---
    if args.query:
        queries = [args.query]
    else:
        queries = [
            "get stock price history for AAPL",
            "earnings calendar",
        ]

    # --- Test 1: discover_tools (lexical) ---
    for i, query in enumerate(queries, 1):
        print(f"\n--- Test {i}: discover_tools (lexical) ---")
        result = discover_tools(query=query, max_tools=5, hybrid_search=False)
        _print_tools(query, result)
        assert result["count"] > 0, f"Expected at least one result for: {query}"
        print("PASS")

    # --- Test: direct BM25S lexical retrieval from catalog ---
    test_num = len(queries) + 1
    print(f"\n--- Test {test_num}: BM25S direct lexical retrieval ---")
    bm25_result = retriever.retrieve_documents(
        queries[0],
        hybrid_search=False,
        max_results=5,
    )
    assert bm25_result.get("success"), "Lexical retrieval failed"
    print(f"Total retrieved: {bm25_result.get('total_retrieved')}")
    for rank, doc in enumerate(bm25_result.get("documents", [])[:5], 1):
        print(
            f"  {rank}. {doc.get('id')} — "
            f"score={doc.get('bm25_score')}, softmax={doc.get('softmax_score')}"
        )
    assert len(bm25_result["documents"]) > 0, "Expected at least one document"
    print("PASS")

    # --- Test: hybrid retrieval (if fastembed is installed) ---
    test_num += 1
    print(f"\n--- Test {test_num}: BM25S hybrid retrieval ---")
    try:
        import fastembed  # noqa: F401
    except ImportError:
        print(
            "SKIP: fastembed not installed "
            "(install with `pip install axiolex[colbert]` to run hybrid)"
        )
    else:
        hybrid_result = retriever.retrieve_documents(
            queries[0],
            hybrid_search=True,
            max_results=5,
            bm25_weight=0.5,
            colbert_weight=0.5,
        )
        assert hybrid_result.get("success"), "Hybrid retrieval failed"
        print(f"Search mode: {hybrid_result.get('search_mode')}")
        for rank, doc in enumerate(hybrid_result.get("documents", [])[:5], 1):
            print(
                f"  {rank}. {doc.get('id')} — "
                f"hybrid_score={doc.get('hybrid_score')}, "
                f"bm25_score={doc.get('bm25_score')}"
            )
        assert len(hybrid_result["documents"]) > 0, "Expected at least one document"
        print("PASS")

    print("\n" + "=" * 60)
    print("All tests passed")
    print("=" * 60)


if __name__ == "__main__":
    main()
