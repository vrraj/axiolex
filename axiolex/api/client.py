"""
HTTP client for BM25S retriever API.
"""

import httpx
from typing import Dict, Any, Optional
from .models import (
    RetrieveRequest,
    RetrieveResponse,
    SettingsResponse
)


class BM25SClient:
    """HTTP client for BM25S retriever service."""
    
    def __init__(self, base_url: str = "http://localhost:8000", timeout: float = 30.0):
        """
        Initialize client.
        
        Args:
            base_url: Base URL of the BM25S service
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)
    
    def retrieve(self, query: str, **kwargs) -> RetrieveResponse:
        """
        Retrieve documents based on query.
        
        Args:
            query: Search query
            **kwargs: Optional settings overrides
            
        Returns:
            RetrieveResponse with results
        """
        request_data = RetrieveRequest(query=query, **kwargs)
        
        response = self.client.post(
            f"{self.base_url}/retrieve",
            json=request_data.model_dump(exclude_none=True)
        )
        response.raise_for_status()
        
        return RetrieveResponse(**response.json())

    def get_settings(self) -> SettingsResponse:
        """
        Get current settings.
        
        Returns:
            SettingsResponse with current configuration
        """
        response = self.client.get(f"{self.base_url}/settings")
        response.raise_for_status()
        
        return SettingsResponse(**response.json())
    
    def update_settings(self, temperature: Optional[float] = None,
                        ignore_zero: Optional[bool] = None,
                        llm_tools_cutoff: Optional[float] = None) -> SettingsResponse:
        """
        Update BM25S settings.
        
        Args:
            temperature: Softmax temperature
            ignore_zero: Filter zero-relevance documents
            llm_tools_cutoff: Cutoff percentage
            
        Returns:
            SettingsResponse with updated configuration
        """
        from .models import BM25SSettings
        
        settings_data = BM25SSettings(
            temperature=temperature,
            ignore_zero=ignore_zero,
            llm_tools_cutoff=llm_tools_cutoff
        )
        
        response = self.client.post(
            f"{self.base_url}/settings",
            json=settings_data.model_dump(exclude_none=True)
        )
        response.raise_for_status()
        
        return SettingsResponse(**response.json())
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get service status.
        
        Returns:
            Status information
        """
        response = self.client.get(f"{self.base_url}/status")
        response.raise_for_status()
        
        return response.json()
    
    def reload_index(self) -> Dict[str, Any]:
        """
        Reload the retriever instance.

        Returns:
            Reload status
        """
        response = self.client.post(f"{self.base_url}/reload")
        response.raise_for_status()

        return response.json()

    def get_documents(self) -> Dict[str, Any]:
        """
        Get all documents.

        Returns:
            Documents response
        """
        response = self.client.get(f"{self.base_url}/documents")
        response.raise_for_status()

        return response.json()

    def close(self):
        """Close the HTTP client."""
        self.client.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Convenience functions for quick usage
def retrieve_documents(query: str, base_url: str = "http://localhost:8000", **kwargs) -> RetrieveResponse:
    """
    Quick retrieve function.

    Args:
        query: Search query
        base_url: Base URL of the BM25S service
        **kwargs: Optional settings overrides

    Returns:
        RetrieveResponse with results
    """
    with BM25SClient(base_url) as client:
        return client.retrieve(query, **kwargs)
