"""
Debug script to check what's actually in Redis.
"""

from axiolex.core.cache import get_cache_manager


def main():
    print("Debugging Redis Cache")
    print("=" * 60)
    
    cache_manager = get_cache_manager()
    
    # Check connection
    print(f"Connected: {cache_manager.is_connected()}")
    
    # Get all keys with axiolex prefix
    pattern = f"{cache_manager.PROVIDER_PREFIX}*"
    all_keys = cache_manager.client.keys(pattern)
    
    print(f"\nAll keys with '{cache_manager.PROVIDER_PREFIX}' prefix:")
    print(f"Total: {len(all_keys)}")
    
    for key in all_keys:
        print(f"  - {key}")
    
    # Try to get discovery keys specifically
    discovery_pattern = f"{cache_manager.PROVIDER_PREFIX}{cache_manager.DISCOVERY_PREFIX}*"
    discovery_keys = cache_manager.client.keys(discovery_pattern)
    
    print(f"\nDiscovery keys:")
    print(f"Total: {len(discovery_keys)}")
    
    for key in discovery_keys:
        print(f"  - {key}")
        # Try to get the data
        data = cache_manager.client.hgetall(key)
        print(f"    Data: {data}")
    
    # Try to get runtime keys specifically
    runtime_pattern = f"{cache_manager.PROVIDER_PREFIX}{cache_manager.RUNTIME_PREFIX}*"
    runtime_keys = cache_manager.client.keys(runtime_pattern)
    
    print(f"\nRuntime keys:")
    print(f"Total: {len(runtime_keys)}")
    
    for key in runtime_keys:
        print(f"  - {key}")


if __name__ == "__main__":
    main()
