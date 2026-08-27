#!/usr/bin/env python3
"""
Smoke test for the installed axiolex package.

Tests:
- imports and version
- discover_tools for "get stock price history for AAPL" (lexical)
- discover_tools for "earnings calendar" (lexical)
- direct BM25S lexical retrieval
- direct BM25S hybrid retrieval (if fastembed is installed)

Run from the repo root with:
    uv run examples/test_axiolex_package.py

Or after a pip install with:
    python examples/test_axiolex_package.py
"""

import sys

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from axiolex import BM25SRetriever, Document, discover_tools, __version__

SAMPLE_TOOLS = [
    {
        "id": "alphavantage:TIME_SERIES_DAILY",
        "title": "Time Series Daily",
        "content": "Fetch daily time series data for a stock symbol, including open, high, low, close, and volume.",
        "keywords": ["stock", "daily", "price", "history", "symbol", "AAPL"],
        "runtime": {
            "tool_name": "TIME_SERIES_DAILY",
            "provider": "alphavantage_finance",
            "transport": "streamable-http",
            "endpoint": "https://mcp.alphavantage.co/mcp",
            "params": {
                "symbol": {"type": "string"},
                "outputsize": {"type": "string"},
            },
        },
    },
    {
        "id": "alphavantage:EARNINGS_CALENDAR",
        "title": "Earnings Calendar",
        "content": "Retrieve upcoming and historical earnings announcement dates for stocks.",
        "keywords": ["earnings", "calendar", "announcement", "stocks"],
        "runtime": {
            "tool_name": "EARNINGS_CALENDAR",
            "provider": "alphavantage_finance",
            "transport": "streamable-http",
            "endpoint": "https://mcp.alphavantage.co/mcp",
            "params": {"symbol": {"type": "string"}},
        },
    },
    {
        "id": "alphavantage:BALANCE_SHEET",
        "title": "Balance Sheet",
        "content": "Get annual and quarterly balance sheet reports for a company.",
        "keywords": ["balance", "sheet", "financials", "annual", "quarterly"],
        "runtime": {
            "tool_name": "BALANCE_SHEET",
            "provider": "alphavantage_finance",
            "transport": "streamable-http",
            "endpoint": "https://mcp.alphavantage.co/mcp",
            "params": {"symbol": {"type": "string"}},
        },
    },
    {
        "id": "tavily_mcp:search",
        "title": "Tavily Web Search",
        "content": "Search the web for recent information and research.",
        "keywords": ["search", "web", "research", "news"],
        "runtime": {
            "tool_name": "search",
            "provider": "tavily_mcp",
            "transport": "streamable-http",
            "endpoint": "https://mcp.tavily.com/mcp",
            "params": {"query": {"type": "string"}},
        },
    },
    {
        "id": "mcp_fetch:fetch",
        "title": "Fetch URL",
        "content": "Fetch and extract content from a URL.",
        "keywords": ["fetch", "url", "web", "content"],
        "runtime": {
            "tool_name": "fetch",
            "provider": "mcp_fetch",
            "transport": "stdio",
            "command": "uvx",
            "args": ["--with", "mcp==1.29.0", "mcp-server-fetch"],
            "params": {"url": {"type": "string"}},
        },
    },
]


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
    print("=" * 60)
    print("AxioLex package smoke test")
    print(f"Version: {__version__}")
    print("=" * 60)

    print("\nBuilding in-memory retriever with sample tools...")
    retriever = BM25SRetriever(use_cache=False, document_file="nonexistent.yaml")
    retriever.add_documents([Document(**doc) for doc in SAMPLE_TOOLS])
    print(f"Indexed {len(retriever.documents)} documents.")

    # --- Test 1: discover_tools lexical — stock price ---
    query1 = "get stock price history for AAPL"
    print("\n--- Test 1: discover_tools (lexical) ---")
    result1 = discover_tools(
        query=query1,
        retriever=retriever,
        max_tools=3,
        hybrid_search=False,
    )
    _print_tools(query1, result1)
    assert result1["count"] > 0, "Expected at least one result"
    top1 = result1["tools"][0]["name"]
    assert top1 == "TIME_SERIES_DAILY", f"Expected TIME_SERIES_DAILY, got {top1}"
    print("PASS")

    # --- Test 2: discover_tools lexical — earnings ---
    query2 = "earnings calendar"
    print("\n--- Test 2: discover_tools (lexical) ---")
    result2 = discover_tools(
        query=query2,
        retriever=retriever,
        max_tools=3,
        hybrid_search=False,
    )
    _print_tools(query2, result2)
    assert result2["count"] > 0, "Expected at least one result"
    top2 = result2["tools"][0]["name"]
    assert top2 == "EARNINGS_CALENDAR", f"Expected EARNINGS_CALENDAR, got {top2}"
    print("PASS")

    # --- Test 3: direct BM25S lexical retrieval ---
    print("\n--- Test 3: BM25S direct lexical retrieval ---")
    bm25_result = retriever.retrieve_documents(
        "get stock price history for AAPL",
        hybrid_search=False,
        max_results=3,
    )
    assert bm25_result.get("success"), "Lexical retrieval failed"
    print(f"Total retrieved: {bm25_result.get('total_retrieved')}")
    for rank, doc in enumerate(bm25_result.get("documents", [])[:3], 1):
        print(
            f"  {rank}. {doc.get('id')} — "
            f"score={doc.get('bm25_score')}, softmax={doc.get('softmax_score')}"
        )
    assert bm25_result["documents"][0]["id"] == "alphavantage:TIME_SERIES_DAILY"
    print("PASS")

    # --- Test 4: direct hybrid retrieval (if fastembed is installed) ---
    print("\n--- Test 4: BM25S hybrid retrieval ---")
    try:
        import fastembed  # noqa: F401
    except ImportError:
        print(
            "SKIP: fastembed not installed "
            "(install with `pip install axiolex[colbert]` to run hybrid)"
        )
    else:
        hybrid_result = retriever.retrieve_documents(
            "get stock price history for AAPL",
            hybrid_search=True,
            max_results=3,
            bm25_weight=0.5,
            colbert_weight=0.5,
        )
        assert hybrid_result.get("success"), "Hybrid retrieval failed"
        print(f"Search mode: {hybrid_result.get('search_mode')}")
        for rank, doc in enumerate(hybrid_result.get("documents", [])[:3], 1):
            print(
                f"  {rank}. {doc.get('id')} — "
                f"hybrid_score={doc.get('hybrid_score')}, "
                f"bm25_score={doc.get('bm25_score')}"
            )
        assert hybrid_result["documents"][0]["id"] == "alphavantage:TIME_SERIES_DAILY"
        print("PASS")

    print("\n" + "=" * 60)
    print("All tests passed")
    print("=" * 60)


if __name__ == "__main__":
    main()
