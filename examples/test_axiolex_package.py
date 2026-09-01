#!/usr/bin/env python3
"""
End-to-end test for the axiolex package.

Supports two modes:

  SDK mode (default):
    Tests the thin HTTP SDK against a running Axiolex server.
    Requires: pip install axiolex
    Requires: Axiolex server running (make start)

  Embedded mode (--embedded):
    Tests the in-process retriever against a live Redis catalog.
    Requires: pip install axiolex[server]
    Requires: Redis running + catalog populated (axiolex-index refresh)

Quick start (SDK mode, 5 minutes):

    1. Install the package:
       pip install axiolex

    2. Start the Axiolex server (from the repo):
       make start

    3. Run this script:
       python test_axiolex_package.py
       python test_axiolex_package.py --query "search the web for AI news"
       python test_axiolex_package.py --namespaces finance.market_data

Quick start (embedded mode):

    1. Install with server extras:
       pip install axiolex[server]

    2. Start Redis and populate the catalog:
       docker run -d --name redis -p 6380:6379 redis:7
       axiolex-index refresh

    3. Run this script:
       python test_axiolex_package.py --embedded

Environment variables (embedded mode defaults):
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


def _run_sdk_tests(args):
    """Test the thin HTTP SDK against a running Axiolex server."""
    import axiolex
    from axiolex import __version__

    base_url = args.base_url
    print("=" * 60)
    print("AxioLex SDK end-to-end test")
    print(f"Version: {__version__}")
    print(f"Imported from: {axiolex.__file__}")
    print(f"Server: {base_url}")
    print("=" * 60)

    client = axiolex.Axiolex(base_url=base_url)

    # --- Check server health ---
    print("\nConnecting to Axiolex server...")
    try:
        health = client.health()
        print(f"Connected. Server status: {health.get('status', 'unknown')}")
    except Exception as e:
        print(f"\nERROR: Cannot reach Axiolex server at {base_url}")
        print(f"  {e}")
        print("\nPrerequisites:")
        print("  1. Start the Axiolex server (make start)")
        print(f"  2. Ensure it's reachable at {base_url}")
        sys.exit(1)

    # --- Determine queries to run ---
    if args.query:
        queries = [args.query]
    else:
        queries = [
            "get stock price history for AAPL",
            "search the web for AI news",
        ]

    namespaces = args.namespaces.split(",") if args.namespaces else None

    # --- Test 1: discover (lexical) ---
    for i, query in enumerate(queries, 1):
        print(f"\n--- Test {i}: discover (lexical) ---")
        result = client.discover(
            query=query,
            top_k=5,
            hybrid_search=False,
            namespaces=namespaces,
        )
        _print_tools(query, result)
        assert result["count"] > 0, f"Expected at least one result for: {query}"
        print("PASS")

    # --- Test 2: discover (hybrid, if supported) ---
    test_num = len(queries) + 1
    print(f"\n--- Test {test_num}: discover (hybrid) ---")
    try:
        hybrid_result = client.discover(
            query=queries[0],
            top_k=5,
            hybrid_search=True,
            namespaces=namespaces,
        )
        print(f"Search mode: {hybrid_result.get('search_mode')}")
        _print_tools(queries[0], hybrid_result)
        assert hybrid_result["count"] > 0, "Expected at least one hybrid result"
        print("PASS")
    except Exception as e:
        print(f"SKIP: hybrid search not available on server ({e})")

    # --- Test 3: namespace-scoped discovery ---
    if not namespaces:
        test_num += 1
        print(f"\n--- Test {test_num}: discover with namespace filter ---")
        ns_result = client.discover(
            query="stock price",
            top_k=5,
            namespaces=["finance.market_data"],
        )
        _print_tools("stock price", ns_result)
        for tool in ns_result.get("tools", []):
            assert tool.get("provider") in ("alphavantage_finance", "aina_markets"), (
                f"Tool {tool['name']} from unexpected provider in finance.market_data namespace"
            )
        print("PASS")

    print("\n" + "=" * 60)
    print("All SDK tests passed")
    print("=" * 60)


def _run_embedded_tests(args):
    """Test the in-process retriever against a live Redis catalog."""
    import axiolex
    from axiolex import discover_tools, __version__
    from axiolex.core.retriever import get_tool_discovery_retriever

    redis_host = os.getenv("AXIOLEX_REDIS_HOST", "localhost")
    redis_port = os.getenv("AXIOLEX_REDIS_PORT", "6380")
    redis_db = os.getenv("AXIOLEX_REDIS_DB", "0")

    print("=" * 60)
    print("AxioLex embedded library end-to-end test")
    print(f"Version: {__version__}")
    print(f"Imported from: {axiolex.__file__}")
    print(f"Redis: {redis_host}:{redis_port}/{redis_db}")
    print("=" * 60)

    # --- Connect to Redis-backed catalog ---
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

    namespaces = args.namespaces.split(",") if args.namespaces else None

    # --- Test 1: discover_tools (lexical) ---
    for i, query in enumerate(queries, 1):
        print(f"\n--- Test {i}: discover_tools (lexical) ---")
        result = discover_tools(
            query=query,
            max_tools=5,
            hybrid_search=False,
            namespaces=namespaces,
        )
        # Verify unified contract fields are present
        if result["tools"]:
            assert "relevance_score" in result["tools"][0], "Missing relevance_score"
            assert "rank" in result["tools"][0], "Missing rank"
        _print_tools(query, result)
        assert result["count"] > 0, f"Expected at least one result for: {query}"
        print("PASS")

    # --- Test 2: direct BM25S lexical retrieval from catalog ---
    test_num = len(queries) + 1
    print(f"\n--- Test {test_num}: BM25S direct lexical retrieval ---")
    bm25_result = retriever.retrieve_documents(
        queries[0],
        hybrid_search=False,
        max_results=5,
        namespaces=namespaces,
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

    # --- Test 3: hybrid retrieval (if fastembed is installed) ---
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
            namespaces=namespaces,
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

    # --- Test 4: namespace-scoped retrieval ---
    if not namespaces:
        test_num += 1
        print(f"\n--- Test {test_num}: namespace-scoped retrieval ---")
        ns_result = retriever.retrieve_documents(
            "stock price",
            hybrid_search=False,
            max_results=5,
            namespaces=["finance.market_data"],
        )
        assert ns_result.get("success"), "Namespace retrieval failed"
        print(f"Total retrieved: {ns_result.get('total_retrieved')}")
        for rank, doc in enumerate(ns_result.get("documents", [])[:5], 1):
            print(f"  {rank}. {doc.get('id')} — score={doc.get('bm25_score')}")
        print("PASS")

    print("\n" + "=" * 60)
    print("All embedded tests passed")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Axiolex package end-to-end test")
    parser.add_argument(
        "--embedded",
        action="store_true",
        help="Test the embedded library (requires axiolex[server] + Redis)",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("AXIOLEX_BASE_URL", "http://localhost:9700"),
        help="Axiolex server URL for SDK mode (default: http://localhost:9700)",
    )
    parser.add_argument(
        "--query",
        default=None,
        help="Custom query to test with (default: runs built-in sample queries)",
    )
    parser.add_argument(
        "--namespaces",
        default=None,
        help="Comma-separated namespaces to filter (e.g. finance.market_data,research.web)",
    )
    args = parser.parse_args()

    if args.embedded:
        _run_embedded_tests(args)
    else:
        _run_sdk_tests(args)


if __name__ == "__main__":
    main()
