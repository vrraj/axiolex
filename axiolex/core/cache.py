"""
Redis cache manager for tool discovery and runtime execution.

This module provides caching for:
- Discovery index: Tool metadata for search and LLM prompts
- Runtime execution: Tool execution specs (transport, endpoints)
"""

import json
import os
import uuid
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import redis


@dataclass
class RedisConfig:
    """Redis configuration."""
    host: str = "localhost"
    port: int = 6380
    db: int = 0
    password: Optional[str] = None
    decode_responses: bool = True
    discovery_ttl_seconds: int = 3600
    runtime_ttl_seconds: int = 1800

    @classmethod
    def from_env(cls) -> "RedisConfig":
        """Load the shared Axiolex Redis connection from environment variables."""
        password_env = os.getenv("AXIOLEX_REDIS_PASSWORD_ENV")
        return cls(
            host=os.getenv("AXIOLEX_REDIS_HOST", "localhost"),
            port=int(os.getenv("AXIOLEX_REDIS_PORT", "6380")),
            db=int(os.getenv("AXIOLEX_REDIS_DB", "0")),
            password=os.getenv(password_env) if password_env else None,
            discovery_ttl_seconds=_env_int(
                "AXIOLEX_REDIS_DISCOVERY_TTL_SECONDS", 3600
            ),
            runtime_ttl_seconds=_env_int("AXIOLEX_REDIS_RUNTIME_TTL_SECONDS", 1800),
        )


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


class ToolCacheManager:
    """Redis cache manager for tool discovery and runtime execution."""
    
    # Cache key patterns
    DISCOVERY_PREFIX = "idx:tool:"
    RUNTIME_PREFIX = "run:tool:"
    PROVIDER_PREFIX = "axiolex:"
    CATALOG_VERSION_KEY = "axiolex:catalog:version"
    
    # TTL configuration (seconds)
    DISCOVERY_TTL = 3600  # 1 hour for discovery data
    RUNTIME_TTL = 1800    # 30 minutes for runtime data
    
    def __init__(self, config: RedisConfig = None):
        """Initialize Redis cache manager."""
        self.config = config or RedisConfig()
        self._client: Optional[redis.Redis] = None
        
    @property
    def client(self) -> redis.Redis:
        """Get Redis client (lazy initialization)."""
        if self._client is None:
            self._client = redis.Redis(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                password=self.config.password,
                decode_responses=self.config.decode_responses
            )
        return self._client
    
    def is_connected(self) -> bool:
        """Check if Redis is connected."""
        try:
            return self.client.ping()
        except Exception:
            return False
    
    # Discovery Index Methods
    
    def cache_discovery(self, tool_id: str, discovery_data: Dict[str, Any]) -> bool:
        """
        Cache tool discovery data for search and LLM prompts.
        
        Args:
            tool_id: Tool identifier
            discovery_data: Discovery data with keys:
                - title: Tool title
                - description: Tool description
                - tool_name: Tool name (for execution)
                - params: Parameter schema (semantic names only)
                - category: Tool category
                - provider: Tool provider
                
        Returns:
            True if cached successfully
        """
        try:
            key = f"{self.PROVIDER_PREFIX}{self.DISCOVERY_PREFIX}{tool_id}"
            self.client.hset(key, mapping={
                "title": discovery_data.get("title", ""),
                "description": discovery_data.get("description", discovery_data.get("content", "")),
                "tool_name": discovery_data.get("tool_name", ""),
                "params": json.dumps(discovery_data.get("params", {})),
                "category": discovery_data.get("category", "general"),
                "provider": discovery_data.get("provider", "unknown"),
                "source": discovery_data.get("source", "")
            })
            self._expire_if_enabled(key, self.discovery_ttl_seconds)
            return True
        except Exception as e:
            print(f"Error caching discovery data for {tool_id}: {e}")
            return False
    
    def get_discovery(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """
        Get tool discovery data from cache.
        
        Args:
            tool_id: Tool identifier
            
        Returns:
            Discovery data or None if not found
        """
        try:
            key = f"{self.PROVIDER_PREFIX}{self.DISCOVERY_PREFIX}{tool_id}"
            data = self.client.hgetall(key)
            if not data:
                return None
            
            return {
                "title": data.get("title", ""),
                "description": data.get("description", ""),
                "tool_name": data.get("tool_name", ""),
                "params": json.loads(data.get("params", "{}")),
                "category": data.get("category", "general"),
                "provider": data.get("provider", "unknown"),
                "source": data.get("source", "")
            }
        except Exception as e:
            print(f"Error getting discovery data for {tool_id}: {e}")
            return None
    
    def cache_all_discovery(self, tools: List[Dict[str, Any]]) -> int:
        """
        Cache multiple tools' discovery data.
        
        Args:
            tools: List of tool discovery data
            
        Returns:
            Number of tools cached successfully
        """
        success_count = 0
        for tool in tools:
            tool_id = tool.get("id")
            if tool_id and self.cache_discovery(tool_id, tool):
                success_count += 1
        return success_count
    
    def get_all_discovery(self) -> List[Dict[str, Any]]:
        """
        Get all discovery data from cache.
        
        Returns:
            List of all discovery data
        """
        try:
            pattern = f"{self.PROVIDER_PREFIX}{self.DISCOVERY_PREFIX}*"
            keys = self.client.keys(pattern)
            
            all_discovery = []
            for key in keys:
                tool_id = key.replace(f"{self.PROVIDER_PREFIX}{self.DISCOVERY_PREFIX}", "")
                discovery = self.get_discovery(tool_id)
                if discovery:
                    discovery["id"] = tool_id
                    all_discovery.append(discovery)
            
            return all_discovery
        except Exception as e:
            print(f"Error getting all discovery data: {e}")
            return []
    
    def delete_discovery(self, tool_id: str) -> bool:
        """Delete tool discovery data from cache."""
        try:
            key = f"{self.PROVIDER_PREFIX}{self.DISCOVERY_PREFIX}{tool_id}"
            return self.client.delete(key) > 0
        except Exception as e:
            print(f"Error deleting discovery data for {tool_id}: {e}")
            return False
    
    def delete_runtime(self, tool_id: str) -> bool:
        """Delete tool runtime data from cache."""
        try:
            key = f"{self.PROVIDER_PREFIX}{self.RUNTIME_PREFIX}{tool_id}"
            return self.client.delete(key) > 0
        except Exception as e:
            print(f"Error deleting runtime data for {tool_id}: {e}")
            return False
    
    def delete_discovery_by_source(self, source: str) -> int:
        """Delete discovery and runtime entries matching a source."""
        deleted_count = 0
        for discovery in self.get_all_discovery():
            if discovery.get("source") == source:
                tool_id = discovery.get("id")
                if tool_id:
                    if self.delete_discovery(tool_id):
                        deleted_count += 1
                    self.delete_runtime(tool_id)
        return deleted_count
    
    # Runtime Execution Methods
    
    def cache_runtime(self, tool_id: str, runtime_data: Dict[str, Any]) -> bool:
        """
        Cache tool runtime execution data.
        
        Args:
            tool_id: Tool identifier
            runtime_data: Runtime data with keys:
                - transport: Transport type (http, mcp, etc.)
                - tool_name: Tool name
                - endpoint: Endpoint configuration
                - params: Full parameter schema
                
        Returns:
            True if cached successfully
        """
        try:
            key = f"{self.PROVIDER_PREFIX}{self.RUNTIME_PREFIX}{tool_id}"
            self.client.hset(key, mapping={
                "runtime": json.dumps(runtime_data)
            })
            self._expire_if_enabled(key, self.runtime_ttl_seconds)
            return True
        except Exception as e:
            print(f"Error caching runtime data for {tool_id}: {e}")
            return False

    @property
    def discovery_ttl_seconds(self) -> int:
        return getattr(self.config, "discovery_ttl_seconds", self.DISCOVERY_TTL)

    @property
    def runtime_ttl_seconds(self) -> int:
        return getattr(self.config, "runtime_ttl_seconds", self.RUNTIME_TTL)

    def _expire_if_enabled(self, key: str, ttl_seconds: int) -> None:
        if ttl_seconds > 0:
            self.client.expire(key, ttl_seconds)
    
    def get_runtime(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """
        Get tool runtime execution data from cache.
        
        Args:
            tool_id: Tool identifier
            
        Returns:
            Runtime data or None if not found
        """
        try:
            key = f"{self.PROVIDER_PREFIX}{self.RUNTIME_PREFIX}{tool_id}"
            data = self.client.hgetall(key)
            if not data:
                return None
            
            return json.loads(data.get("runtime", "{}"))
        except Exception as e:
            print(f"Error getting runtime data for {tool_id}: {e}")
            return None
    
    def cache_all_runtime(self, tools: List[Dict[str, Any]]) -> int:
        """
        Cache multiple tools' runtime data.
        
        Args:
            tools: List of tool runtime data
            
        Returns:
            Number of tools cached successfully
        """
        success_count = 0
        for tool in tools:
            tool_id = tool.get("id")
            if tool_id and self.cache_runtime(tool_id, tool.get("runtime", {})):
                success_count += 1
        return success_count

    def replace_all_tools(
        self,
        discovery_tools: List[Dict[str, Any]],
        runtime_tools: List[Dict[str, Any]],
    ) -> int:
        """Atomically replace the complete Axiolex tool catalog."""
        discovery_by_id = {
            tool["id"]: tool for tool in discovery_tools if tool.get("id")
        }
        runtime_by_id = {
            tool["id"]: tool.get("runtime", {})
            for tool in runtime_tools
            if tool.get("id")
        }
        if set(discovery_by_id) != set(runtime_by_id):
            raise ValueError("Discovery and runtime tool IDs must match")

        existing_keys = self.client.keys(f"{self.PROVIDER_PREFIX}*")
        pipeline = self.client.pipeline(transaction=True)
        if existing_keys:
            pipeline.delete(*existing_keys)

        for tool_id, discovery in discovery_by_id.items():
            discovery_key = f"{self.PROVIDER_PREFIX}{self.DISCOVERY_PREFIX}{tool_id}"
            pipeline.hset(discovery_key, mapping={
                "title": discovery.get("title", ""),
                "description": discovery.get(
                    "description", discovery.get("content", "")
                ),
                "tool_name": discovery.get("tool_name", ""),
                "params": json.dumps(discovery.get("params", {})),
                "category": discovery.get("category", "general"),
                "provider": discovery.get("provider", "unknown"),
                "source": discovery.get("source", ""),
            })

            runtime_key = f"{self.PROVIDER_PREFIX}{self.RUNTIME_PREFIX}{tool_id}"
            pipeline.hset(
                runtime_key,
                mapping={"runtime": json.dumps(runtime_by_id[tool_id])},
            )

        pipeline.set(self.CATALOG_VERSION_KEY, uuid.uuid4().hex)
        pipeline.execute()
        return len(discovery_by_id)

    def get_catalog_version(self) -> Optional[str]:
        """Return the current externally managed catalog version."""
        return self.client.get(self.CATALOG_VERSION_KEY)
    
    # Cache Invalidation Methods
    
    def invalidate_tool(self, tool_id: str) -> bool:
        """
        Invalidate cache for a specific tool.
        
        Args:
            tool_id: Tool identifier
            
        Returns:
            True if invalidated successfully
        """
        try:
            discovery_key = f"{self.PROVIDER_PREFIX}{self.DISCOVERY_PREFIX}{tool_id}"
            runtime_key = f"{self.PROVIDER_PREFIX}{self.RUNTIME_PREFIX}{tool_id}"
            
            self.client.delete(discovery_key, runtime_key)
            return True
        except Exception as e:
            print(f"Error invalidating cache for {tool_id}: {e}")
            return False
    
    def invalidate_provider(self, provider: str) -> bool:
        """
        Invalidate cache for a specific provider.
        
        Args:
            provider: Provider name
            
        Returns:
            True if invalidated successfully
        """
        try:
            discovery_pattern = (
                f"{self.PROVIDER_PREFIX}{self.DISCOVERY_PREFIX}{provider}:*"
            )
            runtime_pattern = (
                f"{self.PROVIDER_PREFIX}{self.RUNTIME_PREFIX}{provider}:*"
            )
            keys = self.client.keys(discovery_pattern) + self.client.keys(runtime_pattern)
            if keys:
                self.client.delete(*set(keys))
            
            return True
        except Exception as e:
            print(f"Error invalidating cache for provider {provider}: {e}")
            return False
    
    def invalidate_all(self) -> bool:
        """
        Invalidate all cache.
        
        Returns:
            True if invalidated successfully
        """
        try:
            pattern = f"{self.PROVIDER_PREFIX}*"
            keys = self.client.keys(pattern)
            if keys:
                self.client.delete(*keys)
            return True
        except Exception as e:
            print(f"Error invalidating all cache: {e}")
            return False
    
    # Utility Methods
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        try:
            pattern = f"{self.PROVIDER_PREFIX}*"
            keys = self.client.keys(pattern)
            
            discovery_keys = [k for k in keys if self.DISCOVERY_PREFIX in k]
            runtime_keys = [k for k in keys if self.RUNTIME_PREFIX in k]
            
            return {
                "connected": self.is_connected(),
                "total_keys": len(keys),
                "discovery_keys": len(discovery_keys),
                "runtime_keys": len(runtime_keys),
                "redis_info": self.client.info() if self.is_connected() else None
            }
        except Exception as e:
            print(f"Error getting cache stats: {e}")
            return {
                "connected": False,
                "error": str(e)
            }


# Global cache manager instance
_cache_manager: Optional[ToolCacheManager] = None


def get_cache_manager(config: RedisConfig = None) -> ToolCacheManager:
    """Get the global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = ToolCacheManager(config or RedisConfig.from_env())
    return _cache_manager
