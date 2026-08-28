"""
Thin HTTP SDK client for Axiolex.

This module has no heavy dependencies — only httpx and pydantic.
It is the default surface for `pip install axiolex` consumers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx


class Axiolex:
    """Lightweight HTTP client for a deployed Axiolex server.

    Args:
        base_url: Axiolex server URL (e.g. http://localhost:9700).
        timeout: Request timeout in seconds.
    """

    def __init__(self, base_url: str = "http://localhost:9700", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client: Optional[httpx.Client] = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self._timeout)
        return self._client

    def health(self) -> Dict[str, Any]:
        """Check server health."""
        response = self.client.get(f"{self.base_url}/status")
        response.raise_for_status()
        return response.json()

    def discover(
        self,
        query: str,
        top_k: Optional[int] = None,
        hybrid_search: bool = False,
        temperature: Optional[float] = None,
        min_hybrid_score: Optional[float] = None,
        bm25_weight: Optional[float] = None,
        colbert_weight: Optional[float] = None,
        candidate_limit: Optional[int] = None,
        namespaces: Optional[List[str]] = None,
        max_tools: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Discover tools relevant to a natural-language query.

        Args:
            query: Natural-language request.
            top_k: Maximum number of tools Axiolex returns. The calling
                application decides how many of these enter LLM context.
            hybrid_search: Use BM25 + ColBERT fusion.
            temperature: Softmax temperature for hybrid fusion.
            min_hybrid_score: Minimum fused hybrid score.
            bm25_weight: BM25 blend weight.
            colbert_weight: ColBERT blend weight.
            candidate_limit: Per-model candidate count before fusion.
            namespaces: Restrict discovery to these namespaces.
            max_tools: Alias for top_k (deprecated, use top_k).

        Returns:
            Dict with keys: query, tools, count, search_mode.
            Each tool has: name, rank, relevance_score, description,
            params, inputSchema, endpoint, transport, provider,
            namespaces, and detailed retrieval scores.
        """
        effective_top_k = top_k if top_k is not None else max_tools
        payload: Dict[str, Any] = {"query": query, "hybrid_search": hybrid_search}
        if effective_top_k is not None:
            payload["top_k"] = effective_top_k
        if temperature is not None:
            payload["temperature"] = temperature
        if min_hybrid_score is not None:
            payload["min_hybrid_score"] = min_hybrid_score
        if bm25_weight is not None:
            payload["bm25_weight"] = bm25_weight
        if colbert_weight is not None:
            payload["colbert_weight"] = colbert_weight
        if candidate_limit is not None:
            payload["candidate_limit"] = candidate_limit
        if namespaces is not None:
            payload["namespaces"] = namespaces

        response = self.client.post(
            f"{self.base_url}/discover",
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        hybrid_search: bool = False,
        temperature: Optional[float] = None,
        ignore_zero: Optional[bool] = None,
        llm_tools_cutoff: Optional[float] = None,
        bm25_weight: Optional[float] = None,
        colbert_weight: Optional[float] = None,
        candidate_limit: Optional[int] = None,
        min_hybrid_score: Optional[float] = None,
        namespaces: Optional[List[str]] = None,
        max_results: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Retrieve ranked documents from the Axiolex server.

        Args:
            top_k: Maximum number of results to return.
            max_results: Deprecated alias for top_k.

        Returns:
            Dict with keys: success, message, documents, total_retrieved, etc.
        """
        effective_top_k = top_k if top_k is not None else max_results
        payload: Dict[str, Any] = {"query": query, "hybrid_search": hybrid_search}
        if effective_top_k is not None:
            payload["top_k"] = effective_top_k
        if temperature is not None:
            payload["temperature"] = temperature
        if ignore_zero is not None:
            payload["ignore_zero"] = ignore_zero
        if llm_tools_cutoff is not None:
            payload["llm_tools_cutoff"] = llm_tools_cutoff
        if bm25_weight is not None:
            payload["bm25_weight"] = bm25_weight
        if colbert_weight is not None:
            payload["colbert_weight"] = colbert_weight
        if candidate_limit is not None:
            payload["candidate_limit"] = candidate_limit
        if min_hybrid_score is not None:
            payload["min_hybrid_score"] = min_hybrid_score
        if namespaces is not None:
            payload["namespaces"] = namespaces

        response = self.client.post(
            f"{self.base_url}/retrieve",
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    def list_namespaces(self) -> List[Dict[str, Any]]:
        """List all registered namespaces on the server."""
        response = self.client.get(f"{self.base_url}/namespaces")
        response.raise_for_status()
        return response.json()

    def close(self):
        """Close the underlying HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
