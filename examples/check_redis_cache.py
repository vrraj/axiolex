"""
Script to check Redis cache contents.

This script allows you to:
- View cache statistics
- List all discovery keys
- List all runtime keys
- View specific tool data
- Clear cache
"""

from axiolex.core.cache import get_cache_manager, RedisConfig


def show_cache_stats():
    """Show cache statistics."""
    print("=" * 60)
    print("Redis Cache Statistics")
    print("=" * 60)
    
    cache_manager = get_cache_manager()
    stats = cache_manager.get_cache_stats()
    
    print(f"Connected: {stats['connected']}")
    print(f"Total keys: {stats['total_keys']}")
    print(f"Discovery keys: {stats['discovery_keys']}")
    print(f"Runtime keys: {stats['runtime_keys']}")
    
    if not stats['connected']:
        print("\n⚠️  Redis is not connected!")
        return


def list_discovery_tools():
    """List all discovery tools in cache."""
    print("\n" + "=" * 60)
    print("Discovery Tools in Cache")
    print("=" * 60)
    
    cache_manager = get_cache_manager()
    tools = cache_manager.get_all_discovery()
    
    if not tools:
        print("No discovery tools found in cache")
        return
    
    print(f"Total: {len(tools)} tools\n")
    
    for tool in tools:
        print(f"ID: {tool['id']}")
        print(f"  Title: {tool['title']}")
        print(f"  Category: {tool['category']}")
        print(f"  Provider: {tool['provider']}")
        print(f"  Params: {list(tool['params'].keys())}")
        print()


def list_runtime_tools():
    """List all runtime tools in cache."""
    print("\n" + "=" * 60)
    print("Runtime Tools in Cache")
    print("=" * 60)
    
    cache_manager = get_cache_manager()
    
    # Get all runtime keys
    import redis
    client = cache_manager.client
    pattern = f"{cache_manager.PROVIDER_PREFIX}{cache_manager.RUNTIME_PREFIX}*"
    keys = client.keys(pattern)
    
    if not keys:
        print("No runtime tools found in cache")
        return
    
    print(f"Total: {len(keys)} runtime keys\n")
    
    for key in keys:
        tool_id = key.replace(f"{cache_manager.PROVIDER_PREFIX}{cache_manager.RUNTIME_PREFIX}", "")
        runtime = cache_manager.get_runtime(tool_id)
        
        if runtime:
            print(f"ID: {tool_id}")
            print(f"  Transport: {runtime.get('transport', 'N/A')}")
            print(f"  Tool Name: {runtime.get('tool_name', 'N/A')}")
            print(f"  Endpoint: {runtime.get('endpoint', 'N/A')}")
            print()


def view_tool_details(tool_id: str):
    """View details for a specific tool."""
    print("\n" + "=" * 60)
    print(f"Tool Details: {tool_id}")
    print("=" * 60)
    
    cache_manager = get_cache_manager()
    
    # Get discovery data
    discovery = cache_manager.get_discovery(tool_id)
    if discovery:
        print("\n[Discovery Data]")
        print(f"  Title: {discovery['title']}")
        print(f"  Content: {discovery['content']}")
        print(f"  Category: {discovery['category']}")
        print(f"  Provider: {discovery['provider']}")
        print(f"  Params:")
        for param_name, param_def in discovery['params'].items():
            print(f"    - {param_name}: {param_def}")
    else:
        print("\n[Discovery Data] Not found")
    
    # Get runtime data
    runtime = cache_manager.get_runtime(tool_id)
    if runtime:
        print("\n[Runtime Data]")
        print(f"  Transport: {runtime.get('transport', 'N/A')}")
        print(f"  Tool Name: {runtime.get('tool_name', 'N/A')}")
        print(f"  Endpoint: {runtime.get('endpoint', 'N/A')}")
        print(f"  Params: {runtime.get('params', {})}")
    else:
        print("\n[Runtime Data] Not found")


def clear_cache():
    """Clear all cache."""
    print("\n" + "=" * 60)
    print("Clear Cache")
    print("=" * 60)
    
    cache_manager = get_cache_manager()
    
    # Show stats before
    stats_before = cache_manager.get_cache_stats()
    print(f"Before: {stats_before['total_keys']} keys")
    
    # Clear cache
    result = cache_manager.invalidate_all()
    
    # Show stats after
    stats_after = cache_manager.get_cache_stats()
    print(f"After: {stats_after['total_keys']} keys")
    
    if result:
        print("\n✓ Cache cleared successfully")
    else:
        print("\n✗ Failed to clear cache")


def main():
    """Main menu."""
    print("Redis Cache Inspector")
    print("=" * 60)
    
    while True:
        print("\nOptions:")
        print("1. Show cache statistics")
        print("2. List discovery tools")
        print("3. List runtime tools")
        print("4. View tool details")
        print("5. Clear cache")
        print("6. Exit")
        
        choice = input("\nEnter choice (1-6): ").strip()
        
        if choice == "1":
            show_cache_stats()
        elif choice == "2":
            list_discovery_tools()
        elif choice == "3":
            list_runtime_tools()
        elif choice == "4":
            tool_id = input("Enter tool ID: ").strip()
            if tool_id:
                view_tool_details(tool_id)
        elif choice == "5":
            confirm = input("Are you sure you want to clear all cache? (yes/no): ").strip().lower()
            if confirm == "yes":
                clear_cache()
        elif choice == "6":
            print("Goodbye!")
            break
        else:
            print("Invalid choice")


if __name__ == "__main__":
    main()
