"""MCP provider service."""

from typing import Dict, Any
from ..mcp.discovery import MCPDiscovery, MCPProviderConfig
from ..mcp.secret_store import SecretStoreError, get_secret_store


def get_all_providers() -> Dict[str, Any]:
    """Get all MCP providers."""
    discovery = MCPDiscovery()
    store = get_secret_store()

    providers = []
    for p in discovery.providers:
        has_secret = False
        try:
            has_secret = store.has_secret(p.id)
        except Exception:
            pass
        providers.append({
            "id": p.id,
            "name": p.name,
            "transport": p.transport,
            "endpoint": p.endpoint,
            "command": p.command,
            "args": p.args,
            "auth": {
                "type": p.auth.type,
                "secret_env": p.auth.secret_env,
                "key_param": p.auth.key_param,
            },
            "enabled": p.enabled,
            "has_secret": has_secret,
            "features": {
                "supports_streaming": p.features.supports_streaming
            },
            "limits": {
                "max_page_size": p.limits.max_page_size,
                "max_requests_per_minute": p.limits.max_requests_per_minute,
                "max_results": p.limits.max_results,
                "timeout_seconds": p.limits.timeout_seconds
            }
        })

    return {
        "success": True,
        "providers": providers,
        "count": len(providers)
    }


def add_provider(provider_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add a new MCP provider."""
    discovery = MCPDiscovery()
    
    # Create provider config
    config = MCPProviderConfig.from_dict(provider_data)
    discovery.add_provider(config)
    discovery.save_to_yaml()
    
    return {
        "success": True,
        "message": f"Provider {config.id} added successfully"
    }


def update_provider(provider_id: str, provider_data: Dict[str, Any]) -> Dict[str, Any]:
    """Update an existing MCP provider."""
    discovery = MCPDiscovery()
    
    # Remove existing provider
    discovery.remove_provider(provider_id)
    
    # Add updated provider
    provider_data["id"] = provider_id
    config = MCPProviderConfig.from_dict(provider_data)
    discovery.add_provider(config)
    discovery.save_to_yaml()
    
    return {
        "success": True,
        "message": f"Provider {provider_id} updated successfully"
    }


def disable_provider(provider_id: str) -> Dict[str, Any]:
    """Disable an MCP provider and clear its cached tools."""
    discovery = MCPDiscovery()
    provider = discovery.get_provider(provider_id)

    if not provider:
        raise ValueError(f"Provider {provider_id} not found")

    provider.enabled = False
    discovery.save_to_yaml()

    cache_cleared = False
    try:
        from ..core.cache import get_cache_manager

        cache_manager = get_cache_manager()
        if cache_manager.is_connected():
            cache_cleared = cache_manager.invalidate_provider(provider_id)
            if cache_cleared:
                from ..core.retriever import get_retriever

                get_retriever()._load_and_index_documents()
    except Exception as e:
        print(f"Error clearing cache for provider {provider_id}: {e}")
    
    message = f"Provider {provider_id} disabled"
    if cache_cleared:
        message += " and cached tools cleared"
    else:
        message += ", but cached tools could not be cleared"

    return {
        "success": True,
        "message": message,
        "provider_id": provider_id,
        "enabled": False,
        "cache_cleared": cache_cleared
    }


async def discover_provider_tools(provider_id: str) -> Dict[str, Any]:
    """Discover tools from a specific MCP provider and cache to Redis."""
    discovery = MCPDiscovery()
    provider = discovery.get_provider(provider_id)

    if not provider:
        raise ValueError(f"Provider {provider_id} not found")
    if not provider.enabled:
        raise ValueError(f"Provider {provider_id} is disabled")

    print(f"Discovering tools from provider: {provider_id}")
    print(f"  Endpoint: {provider.endpoint}")
    print(f"  Transport: {provider.transport}")
    print(f"  Auth type: {provider.auth.type}")
    print(f"  Auth secret_env: {provider.auth.secret_env}")

    tools = await discovery.discover_from_config(provider)

    print(f"Discovered {len(tools)} tools")

    # Cache discovered tools to Redis
    if tools:
        try:
            from ..core.cache import get_cache_manager

            cache_manager = get_cache_manager()
            if cache_manager.is_connected():
                discovery_list = []
                runtime_list = []

                for tool in tools:
                    # Cache discovery data for search
                    discovery_list.append({
                        "id": tool["id"],
                        "title": tool["title"],
                        "description": tool["description"],
                        "tool_name": tool.get("tool_name", ""),
                        "params": tool["params"],
                        "category": tool["category"],
                        "provider": tool["provider"]
                    })

                    # Cache runtime data for execution
                    runtime_list.append({
                        "id": tool["id"],
                        "runtime": {
                            "tool_name": tool.get("tool_name", ""),
                            "params": tool["params"],
                            "transport": provider.transport,
                            "endpoint": provider.endpoint,
                            "provider": provider.id,
                            "auth": {
                                "type": provider.auth.type,
                                "secret_env": provider.auth.secret_env
                            }
                        }
                    })

                # Cache to Redis
                cache_manager.cache_all_discovery(discovery_list)
                cache_manager.cache_all_runtime(runtime_list)

                print(f"Cached {len(tools)} tools to Redis")
            else:
                print("Redis not connected, skipping cache")
        except Exception as e:
            print(f"Error caching tools to Redis: {e}")
            import traceback
            traceback.print_exc()

    return {
        "success": True,
        "provider_id": provider_id,
        "tools": tools,
        "count": len(tools)
    }


def set_provider_secret(provider_id: str, secret: str) -> Dict[str, Any]:
    """Encrypt and store a provider secret in the encrypted secret store."""
    discovery = MCPDiscovery()
    provider = discovery.get_provider(provider_id)
    if not provider:
        raise ValueError(f"Provider {provider_id} not found")
    try:
        get_secret_store().set_secret(provider_id, secret)
    except SecretStoreError as e:
        raise RuntimeError(str(e)) from e
    return {
        "success": True,
        "provider_id": provider_id,
        "message": f"Secret stored for provider {provider_id}",
    }


def get_provider_secret_status(provider_id: str) -> Dict[str, Any]:
    """Return whether a stored secret exists for the provider (never the value)."""
    discovery = MCPDiscovery()
    provider = discovery.get_provider(provider_id)
    if not provider:
        raise ValueError(f"Provider {provider_id} not found")
    has_secret = False
    try:
        has_secret = get_secret_store().has_secret(provider_id)
    except Exception:
        pass
    return {
        "success": True,
        "provider_id": provider_id,
        "has_secret": has_secret,
    }


def delete_provider_secret(provider_id: str) -> Dict[str, Any]:
    """Remove a stored secret for the provider."""
    discovery = MCPDiscovery()
    provider = discovery.get_provider(provider_id)
    if not provider:
        raise ValueError(f"Provider {provider_id} not found")
    deleted = False
    try:
        deleted = get_secret_store().delete_secret(provider_id)
    except SecretStoreError as e:
        raise RuntimeError(str(e)) from e
    return {
        "success": True,
        "provider_id": provider_id,
        "deleted": deleted,
        "message": (
            f"Secret deleted for provider {provider_id}"
            if deleted
            else f"No stored secret found for provider {provider_id}"
        ),
    }
