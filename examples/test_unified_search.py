"""
Test script for unified search with Redis cache and MCP discovery.

This script demonstrates:
1. Loading tools from YAML
2. Discovering tools from MCP providers
3. Merging tools from multiple sources
4. Caching to Redis
5. Building unified BM25S index
6. Searching across all tools
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from axiolex.core.retriever import BM25SRetriever
from axiolex.core.cache import get_cache_manager, RedisConfig
from axiolex.mcp.discovery import MCPDiscovery, MCPProviderConfig, MCPProvider
from axiolex.mcp.merger import ToolMerger, ToolMergeConfig


def test_yaml_only():
    """Test loading and searching YAML tools only."""
    print("=" * 60)
    print("Test 1: YAML Tools Only")
    print("=" * 60)
    
    retriever = BM25SRetriever(use_cache=False)
    
    # Search for stock-related tools
    results = retriever.retrieve_documents("stock price history")
    
    print(f"\nSearch: 'stock price history'")
    print(f"Found {len(results['documents'])} results")
    
    for doc in results['documents'][:3]:
        print(f"  - {doc['title']} (ID: {doc['id']})")
        print(f"    Provider: {doc['metadata'].get('provider', 'unknown')}")
    
    return len(results['documents']) > 0


def test_redis_cache():
    """Test Redis caching of tools."""
    print("\n" + "=" * 60)
    print("Test 2: Redis Cache")
    print("=" * 60)
    
    try:
        cache_manager = get_cache_manager()
        
        if not cache_manager.is_connected():
            print("Redis not connected, skipping cache test")
            return False
        
        # Get cache stats
        stats = cache_manager.get_cache_stats()
        print(f"Redis connected: {stats['connected']}")
        print(f"Total keys: {stats['total_keys']}")
        print(f"Discovery keys: {stats['discovery_keys']}")
        print(f"Runtime keys: {stats['runtime_keys']}")
        
        # Test caching a tool
        test_tool = {
            "id": "test_tool",
            "title": "Test Tool",
            "content": "A test tool for caching",
            "params": {"param1": {"type": "string"}},
            "category": "test",
            "provider": "test"
        }
        
        cache_manager.cache_discovery("test_tool", test_tool)
        print("\nCached test tool to Redis")
        
        # Retrieve it
        retrieved = cache_manager.get_discovery("test_tool")
        print(f"Retrieved tool: {retrieved['title'] if retrieved else 'None'}")
        
        # Clean up
        cache_manager.invalidate_tool("test_tool")
        print("Cleaned up test tool")
        
        return True
        
    except Exception as e:
        print(f"Redis test error: {e}")
        return False


def test_mcp_discovery():
    """Test MCP tool discovery with Alpha Vantage adapter using standard MCP client."""
    print("\n" + "=" * 60)
    print("Test 3: MCP Discovery (Alpha Vantage Adapter - Standard MCP)")
    print("=" * 60)

    api_key = os.getenv("ALPHAVANTAGE_API_KEY")
    if not api_key:
        print("No ALPHAVANTAGE_API_KEY found, skipping MCP discovery test")
        return False

    try:
        from axiolex.mcp.discovery import MCPProviderAuth, MCPLimits
        from axiolex.mcp.alphavantage_adapter import AlphaVantageAdapter

        config = MCPProviderConfig(
            id="alphavantage_finance",
            name="Alpha Vantage MCP",
            transport="streamable-http",
            endpoint="https://mcp.alphavantage.co/mcp",
            auth=MCPProviderAuth(type="api_key", secret_value=api_key),
            enabled=True,
            limits=MCPLimits(max_page_size=15)  # Test with 15 tools limit
        )

        adapter = AlphaVantageAdapter(config)
        tools = adapter.discover_tools()

        print(f"\nDiscovered {len(tools)} tools from Alpha Vantage")

        for tool in tools[:5]:
            print(f"  - {tool['title']} (ID: {tool['id']})")
            print(f"    Category: {tool['category']}")
            if tool['description']:
                print(f"    Description: {tool['description'][:100]}...")

        return len(tools) > 0

    except Exception as e:
        print(f"MCP discovery error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tool_merger():
    """Test merging YAML and MCP tools."""
    print("\n" + "=" * 60)
    print("Test 4: Tool Merger")
    print("=" * 60)
    
    try:
        api_key = os.getenv("ALPHAVANTAGE_API_KEY")
        
        mcp_providers = []
        if api_key:
            mcp_providers.append(MCPProviderConfig(
                provider=MCPProvider.ALPHAVANTAGE,
                base_url="https://mcp.alphavantage.co/mcp",
                api_key=api_key,
                transport="http"
            ))
        
        config = ToolMergeConfig(
            yaml_file="source_files/tools_list.yaml",
            mcp_providers=mcp_providers,
            use_cache=False  # Disable cache for this test
        )
        
        with ToolMerger(config) as merger:
            # Load and merge
            merged = merger.merge_and_cache()
            
            print(f"Merged {len(merged)} tools from all sources")
            
            # Count by source
            yaml_count = sum(1 for t in merged if t.get('source') == 'yaml')
            mcp_count = sum(1 for t in merged if t.get('source') == 'mcp-discovery')
            
            print(f"  YAML tools: {yaml_count}")
            print(f"  MCP tools: {mcp_count}")
            
            # Show sample tools
            print("\nSample merged tools:")
            for tool in merged[:3]:
                print(f"  - {tool['title']} (ID: {tool['id']}, Source: {tool.get('source', 'unknown')})")
        
        return len(merged) > 0
        
    except Exception as e:
        print(f"Tool merger error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_unified_search():
    """Test unified search across all tool sources."""
    print("\n" + "=" * 60)
    print("Test 5: Unified Search")
    print("=" * 60)
    
    try:
        api_key = os.getenv("ALPHAVANTAGE_API_KEY")
        
        mcp_providers = []
        if api_key:
            mcp_providers.append(MCPProviderConfig(
                provider=MCPProvider.ALPHAVANTAGE,
                base_url="https://mcp.alphavantage.co/mcp",
                api_key=api_key,
                transport="http"
            ))
        
        config = ToolMergeConfig(
            yaml_file="source_files/tools_list.yaml",
            mcp_providers=mcp_providers,
            use_cache=False
        )
        
        with ToolMerger(config) as merger:
            # Merge tools
            merged = merger.merge_and_cache()
            
            # Convert to documents
            documents = merger.convert_to_documents()
            
            # Build retriever with merged documents
            retriever = BM25SRetriever(use_cache=False)
            retriever.rebuild_index(documents)
            
            # Search for stock-related tools
            results = retriever.retrieve_documents("stock price history")
            
            print(f"\nSearch: 'stock price history'")
            print(f"Found {len(results['documents'])} results")
            
            for doc in results['documents'][:5]:
                print(f"  - {doc['title']} (ID: {doc['id']})")
                print(f"    Provider: {doc['metadata'].get('provider', 'unknown')}")
                print(f"    Source: {doc['metadata'].get('source', 'unknown')}")
        
        return len(results['documents']) > 0
        
    except Exception as e:
        print(f"Unified search error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("Unified Search Test Suite")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("YAML Only", test_yaml_only()))
    results.append(("Redis Cache", test_redis_cache()))
    results.append(("MCP Discovery", test_mcp_discovery()))
    results.append(("Tool Merger", test_tool_merger()))
    results.append(("Unified Search", test_unified_search()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test_name}: {status}")
    
    total_passed = sum(1 for _, passed in results if passed)
    print(f"\nTotal: {total_passed}/{len(results)} tests passed")


if __name__ == "__main__":
    main()
