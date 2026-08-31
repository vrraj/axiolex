"""Build the Redis tool catalog from YAML and enabled MCP providers."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import yaml

from ..core.cache import ToolCacheManager, get_cache_manager
from ..mcp.discovery import MCPDiscovery, MCPProviderConfig, validate_provider_namespaces
from ..utils.file_utils import is_source_entry_enabled


@dataclass
class IndexingResult:
    """Summary of a completed catalog refresh."""

    yaml_tools: int
    mcp_tools: int
    provider_count: int
    total_tools: int

    def to_dict(self) -> Dict[str, int]:
        return {
            "yaml_tools": self.yaml_tools,
            "mcp_tools": self.mcp_tools,
            "provider_count": self.provider_count,
            "total_tools": self.total_tools,
        }


class ToolIndexingService:
    """Own write access to the externally managed Redis tool catalog."""

    def __init__(
        self,
        tools_file: str,
        providers_file: str,
        cache_manager: Optional[ToolCacheManager] = None,
        allow_partial: bool = False,
    ):
        self.tools_file = tools_file
        self.providers_file = providers_file
        self.cache_manager = cache_manager or get_cache_manager()
        self.allow_partial = allow_partial

    async def refresh(self) -> IndexingResult:
        """Build and atomically replace the complete Redis tool catalog."""
        if not self.cache_manager.is_connected():
            raise RuntimeError("Redis is unavailable")

        yaml_tools = self._load_yaml_tools()
        mcp_tools, provider_count = await self._discover_mcp_tools()
        tools = self._deduplicate(yaml_tools + mcp_tools)
        self._validate_tools(tools)

        discovery_entries = [self._to_discovery_entry(tool) for tool in tools]
        runtime_entries = [self._to_runtime_entry(tool) for tool in tools]
        replaced = self.cache_manager.replace_all_tools(
            discovery_entries,
            runtime_entries,
        )
        if replaced != len(tools):
            raise RuntimeError(
                f"Redis replacement wrote {replaced} of {len(tools)} tools"
            )

        return IndexingResult(
            yaml_tools=len(yaml_tools),
            mcp_tools=len(mcp_tools),
            provider_count=provider_count,
            total_tools=len(tools),
        )

    def status(self) -> Dict[str, Any]:
        """Return Redis catalog status without modifying it."""
        if not self.cache_manager.is_connected():
            raise RuntimeError("Redis is unavailable")
        stats = self.cache_manager.get_cache_stats()
        stats.pop("redis_info", None)
        discovery = self.cache_manager.get_all_discovery()
        incomplete = []
        for tool in discovery:
            runtime = self.cache_manager.get_runtime(tool["id"]) or {}
            if (
                not runtime.get("tool_name")
                or not runtime.get("transport")
                or not runtime.get("endpoint")
            ):
                incomplete.append(tool["id"])
        return {
            "tool_count": len(discovery),
            "incomplete_runtime_tools": incomplete,
            "catalog_version": self.cache_manager.get_catalog_version(),
            "cache_stats": stats,
        }

    def _load_yaml_tools(self) -> List[Dict[str, Any]]:
        with open(self.tools_file, "r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}

        tools = []
        for document in data.get("documents", []):
            if not is_source_entry_enabled(document):
                continue
            runtime = document.get("runtime") or {}
            metadata = document.get("metadata") or {}
            tools.append({
                "id": document.get("id", ""),
                "title": document.get("title", ""),
                "description": document.get("content", ""),
                "tool_name": runtime.get("tool_name", ""),
                "params": runtime.get("params", {}),
                "category": metadata.get("category", "general"),
                "provider": runtime.get("provider")
                or metadata.get("provider")
                or "yaml",
                "source": "yaml",
                "namespaces": metadata.get("namespaces", []),
                "runtime": runtime,
            })
        return tools

    async def _discover_mcp_tools(self) -> tuple[List[Dict[str, Any]], int]:
        discovery = MCPDiscovery(config_file=self.providers_file)
        validate_provider_namespaces(discovery.providers)
        enabled = [provider for provider in discovery.providers if provider.enabled]
        tools = []
        try:
            for provider in enabled:
                provider_tools = await discovery.discover_from_config(provider)
                if not provider_tools and not self.allow_partial:
                    raise RuntimeError(
                        f"Enabled MCP provider '{provider.id}' returned no tools"
                    )
                tools.extend(
                    self._attach_provider_runtime(tool, provider)
                    for tool in provider_tools
                )
        finally:
            discovery.close()
        return tools, len(enabled)

    @staticmethod
    def _attach_provider_runtime(
        tool: Dict[str, Any],
        provider: MCPProviderConfig,
    ) -> Dict[str, Any]:
        normalized = dict(tool)
        normalized["source"] = "mcp-discovery"
        endpoint = provider.endpoint
        if not endpoint and provider.transport == "stdio":
            endpoint = (provider.command or "") + (
                " " + " ".join(provider.args or []) if provider.args else ""
            )
            endpoint = endpoint.strip() or "stdio"

        normalized["runtime"] = {
            "tool_name": tool.get("tool_name", ""),
            "params": tool.get("params", {}),
            "transport": provider.transport,
            "endpoint": endpoint,
            "provider": provider.id,
            "command": provider.command,
            "args": provider.args,
            "auth": {
                "type": provider.auth.type,
                "secret_env": provider.auth.secret_env,
                "key_param": provider.auth.key_param,
            },
        }
        normalized["namespaces"] = list(provider.namespaces)
        return normalized

    @staticmethod
    def _deduplicate(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduplicated = {}
        for tool in tools:
            tool_id = tool.get("id")
            if tool_id and tool_id not in deduplicated:
                deduplicated[tool_id] = tool
        return list(deduplicated.values())

    @staticmethod
    def _validate_tools(tools: List[Dict[str, Any]]) -> None:
        if not tools:
            raise RuntimeError("No tools were loaded or discovered")

        incomplete = []
        for tool in tools:
            runtime = tool.get("runtime") or {}
            if (
                not tool.get("id")
                or not runtime.get("tool_name")
                or not runtime.get("transport")
                or not runtime.get("endpoint")
            ):
                incomplete.append(tool.get("id") or "<missing-id>")
        if incomplete:
            raise RuntimeError(
                "Tools are missing required runtime metadata "
                f"(tool_name, transport, endpoint): {', '.join(incomplete[:10])}"
            )

    @staticmethod
    def _to_discovery_entry(tool: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": tool["id"],
            "title": tool.get("title", ""),
            "description": tool.get("description", ""),
            "tool_name": tool.get("runtime", {}).get("tool_name", ""),
            "params": tool.get("params", {}),
            "category": tool.get("category", "general"),
            "provider": tool.get("provider", "unknown"),
            "source": tool.get("source", ""),
            "namespaces": tool.get("namespaces", []),
        }

    @staticmethod
    def _to_runtime_entry(tool: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": tool["id"],
            "runtime": tool.get("runtime", {}),
        }
