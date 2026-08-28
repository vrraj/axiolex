"""Application-facing tool discovery service."""

import os
from typing import Any, Dict, List, Optional

from ..core.retriever import BM25SRetriever, get_tool_discovery_retriever
from ..mcp.discovery import load_namespaces
from ..retrieval.config import HybridSearchSettings


def _resolve_default_top_k() -> int:
    raw = os.getenv("AXIOLEX_TOP_K", "7")
    try:
        val = int(raw)
    except (TypeError, ValueError):
        return 7
    if val < 1:
        return 7
    return val


DEFAULT_TOP_K = _resolve_default_top_k()
MAX_TOOLS_LIMIT = 100


def _deployment_hybrid_enabled() -> bool:
    """True when the Axiolex deployment has hybrid search enabled."""
    return HybridSearchSettings.from_env().enabled


def _resolve_hybrid_search(hybrid_search: Optional[bool]) -> bool:
    """Resolve hybrid_search: explicit caller choice, else deployment default."""
    if hybrid_search is not None:
        return hybrid_search
    return _deployment_hybrid_enabled()


class ToolDiscoveryService:
    """Select execution-ready tool definitions for a natural-language query."""

    def __init__(
        self,
        retriever: Optional[BM25SRetriever] = None,
        provider_routes: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        self.retriever = retriever or get_tool_discovery_retriever()
        self.provider_routes = provider_routes

    def discover_tools(
        self,
        query: str,
        top_k: Optional[int] = None,
        hybrid_search: Optional[bool] = None,
        temperature: Optional[float] = None,
        min_hybrid_score: Optional[float] = None,
        bm25_weight: Optional[float] = None,
        colbert_weight: Optional[float] = None,
        candidate_limit: Optional[int] = None,
        min_rrf_score: Optional[float] = None,
        namespaces: Optional[List[str]] = None,
        max_tools: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Return the most relevant tool definitions and their execution metadata.

        Args:
            query: Natural-language request.
            top_k: Maximum number of tools Axiolex returns. The calling
                application decides how many of these enter LLM context.
            hybrid_search: None = use deployment default (hybrid if
                AXIOLEX_HYBRID_ENABLED=true, else lexical). True = force
                hybrid. False = force lexical.
            max_tools: Deprecated alias for top_k.
        """
        query = query.strip()
        if not query:
            raise ValueError("query must not be empty")

        effective_top_k = top_k if top_k is not None else max_tools
        limit = DEFAULT_TOP_K if effective_top_k is None else effective_top_k
        if limit < 1 or limit > MAX_TOOLS_LIMIT:
            raise ValueError(f"top_k must be between 1 and {MAX_TOOLS_LIMIT}")
        if min_hybrid_score is None:
            min_hybrid_score = min_rrf_score
        if temperature is not None and (temperature < 0.1 or temperature > 10.0):
            raise ValueError("temperature must be between 0.1 and 10.0")
        if min_hybrid_score is not None and min_hybrid_score < 0:
            raise ValueError("min_hybrid_score must be greater than or equal to 0")
        if bm25_weight is not None and bm25_weight < 0:
            raise ValueError("bm25_weight must be greater than or equal to 0")
        if colbert_weight is not None and colbert_weight < 0:
            raise ValueError("colbert_weight must be greater than or equal to 0")
        if (
            bm25_weight is not None
            and colbert_weight is not None
            and bm25_weight + colbert_weight <= 0
        ):
            raise ValueError("at least one hybrid weight must be greater than 0")
        if candidate_limit is not None and (
            candidate_limit < 1 or candidate_limit > MAX_TOOLS_LIMIT * 10
        ):
            raise ValueError("candidate_limit must be between 1 and 1000")
        if namespaces:
            valid = set(load_namespaces())
            if valid:
                invalid = [ns for ns in namespaces if ns not in valid]
                if invalid:
                    raise ValueError(
                        f"Unknown namespace(s): {', '.join(invalid)}"
                    )

        resolved_hybrid = _resolve_hybrid_search(hybrid_search)

        self.retriever.reload_cache_if_changed()
        result = self.retriever.retrieve_documents(
            query,
            ignore_zero=True,
            llm_tools_cutoff=0.0,
            hybrid_search=resolved_hybrid,
            temperature=temperature,
            min_hybrid_score=min_hybrid_score,
            bm25_weight=bm25_weight,
            colbert_weight=colbert_weight,
            candidate_limit=candidate_limit,
            namespaces=namespaces,
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
            "search_mode": result.get("search_mode", "lexical"),
        }

    def _to_tool_definition(self, document: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        runtime = document.get("runtime") or {}
        params = document.get("params") or runtime.get("params") or {}
        tool_name = runtime.get("tool_name")
        if not tool_name:
            return None

        provider = runtime.get("provider") or (document.get("metadata") or {}).get(
            "provider"
        )
        provider_route = {}
        if provider and (not runtime.get("endpoint") or not runtime.get("transport")):
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
            "namespaces": (document.get("metadata") or {}).get("namespaces", []),
            "rank": document.get("rank"),
            "relevance_score": document.get("relevance_score"),
            "bm25_score": document.get("bm25_score"),
            "softmax_score": document.get("softmax_score"),
            "bm25_rank": document.get("bm25_rank"),
            "bm25_softmax_score": document.get("bm25_softmax_score"),
            "colbert_score": document.get("colbert_score"),
            "colbert_rank": document.get("colbert_rank"),
            "colbert_softmax_score": document.get("colbert_softmax_score"),
            "hybrid_score": document.get("hybrid_score"),
        }

    def _get_provider_routes(self) -> Dict[str, Dict[str, Any]]:
        if self.provider_routes is None:
            self.provider_routes = {}

        return self.provider_routes


def discover_tools(
    query: str,
    top_k: Optional[int] = None,
    hybrid_search: Optional[bool] = None,
    retriever: Optional[BM25SRetriever] = None,
    temperature: Optional[float] = None,
    min_hybrid_score: Optional[float] = None,
    bm25_weight: Optional[float] = None,
    colbert_weight: Optional[float] = None,
    candidate_limit: Optional[int] = None,
    min_rrf_score: Optional[float] = None,
    namespaces: Optional[List[str]] = None,
    max_tools: Optional[int] = None,
) -> Dict[str, Any]:
    """Convenience API for package consumers."""
    return ToolDiscoveryService(retriever=retriever).discover_tools(
        query=query,
        top_k=top_k,
        hybrid_search=hybrid_search,
        temperature=temperature,
        min_hybrid_score=min_hybrid_score,
        bm25_weight=bm25_weight,
        colbert_weight=colbert_weight,
        candidate_limit=candidate_limit,
        min_rrf_score=min_rrf_score,
        namespaces=namespaces,
        max_tools=max_tools,
    )
