"""Application-facing tool discovery service."""

from typing import Any, Dict, Optional

from ..core.retriever import BM25SRetriever, get_retriever


DEFAULT_MAX_TOOLS = 10
MAX_TOOLS_LIMIT = 100


class ToolDiscoveryService:
    """Select execution-ready tool definitions for a natural-language query."""

    def __init__(
        self,
        retriever: Optional[BM25SRetriever] = None,
        provider_routes: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        self.retriever = retriever or get_retriever()
        self.provider_routes = provider_routes

    def discover_tools(
        self, query: str, max_tools: Optional[int] = None
    ) -> Dict[str, Any]:
        """Return the most relevant tool definitions and their execution metadata."""
        query = query.strip()
        if not query:
            raise ValueError("query must not be empty")

        limit = DEFAULT_MAX_TOOLS if max_tools is None else max_tools
        if limit < 1 or limit > MAX_TOOLS_LIMIT:
            raise ValueError(
                f"max_tools must be between 1 and {MAX_TOOLS_LIMIT}"
            )

        result = self.retriever.retrieve_documents(
            query,
            ignore_zero=True,
            llm_tools_cutoff=0.0,
        )
        if not result.get("success"):
            raise RuntimeError(result.get("message", "Tool discovery failed"))

        tools = []
        for document in result.get("documents", []):
            tool = self._to_tool_definition(document)
            if tool:
                tools.append(tool)
            if len(tools) == limit:
                break

        return {
            "query": query,
            "tools": tools,
            "count": len(tools),
        }

    def _to_tool_definition(
        self, document: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        runtime = document.get("runtime") or {}
        params = document.get("params") or runtime.get("params") or {}
        tool_name = runtime.get("tool_name")
        if not tool_name:
            return None

        provider = runtime.get("provider") or (
            document.get("metadata") or {}
        ).get("provider")
        provider_route = {}
        if provider and (
            not runtime.get("endpoint") or not runtime.get("transport")
        ):
            provider_route = self._get_provider_routes().get(provider, {})

        return {
            "name": tool_name,
            "description": document.get("content", ""),
            "params": params,
            "inputSchema": {
                "type": "object",
                "properties": params,
                "required": runtime.get("required", []),
            },
            "endpoint": runtime.get("endpoint") or provider_route.get("endpoint"),
            "transport": runtime.get("transport") or provider_route.get("transport"),
            "provider": provider,
        }

    def _get_provider_routes(self) -> Dict[str, Dict[str, Any]]:
        if self.provider_routes is None:
            from ..mcp.discovery import MCPDiscovery

            discovery = MCPDiscovery()
            self.provider_routes = {
                provider.id: {
                    "endpoint": provider.endpoint,
                    "transport": provider.transport,
                }
                for provider in discovery.providers
            }
            discovery.close()

        return self.provider_routes


def discover_tools(
    query: str,
    max_tools: Optional[int] = None,
    retriever: Optional[BM25SRetriever] = None,
) -> Dict[str, Any]:
    """Convenience API for package consumers."""
    return ToolDiscoveryService(retriever=retriever).discover_tools(query, max_tools)
