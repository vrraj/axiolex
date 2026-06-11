"""
HTTP client for BM25S retriever API.
"""

import httpx
from typing import List, Dict, Any, Optional, Union
from .models import (
    Document as DocumentModel,
    RetrieveRequest,
    RetrieveResponse,
    IndexRequest,
    IndexResponse,
    SettingsResponse
)

# Import Document from core for type checking
from ..core.retriever import Document as CoreDocument


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
    
    def index_documents(self, documents: List[DocumentModel], rebuild: bool = True) -> IndexResponse:
        """
        Build or rebuild index with documents.
        
        Args:
            documents: List of documents to index
            rebuild: Whether to rebuild entire index
            
        Returns:
            IndexResponse with indexing results
        """
        request_data = IndexRequest(documents=documents, rebuild=rebuild)
        
        response = self.client.post(
            f"{self.base_url}/index",
            json=request_data.model_dump()
        )
        response.raise_for_status()
        
        return IndexResponse(**response.json())
    
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

    def add_document(self, document: Union[DocumentModel, CoreDocument]) -> Dict[str, Any]:
        """
        Add a single document.

        Args:
            document: Document to add (DocumentModel or Document dataclass)

        Returns:
            Add response
        """
        # Convert Document dataclass to dict if needed
        if hasattr(document, 'model_dump'):
            doc_data = document.model_dump(exclude_none=True)
        else:
            # Handle Document dataclass from core module
            doc_data = document.copy()

        response = self.client.post(
            f"{self.base_url}/documents",
            json=doc_data
        )
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

    def delete_document(self, document_id: str) -> Dict[str, Any]:
        """
        Delete a document by ID.

        Args:
            document_id: ID of document to delete

        Returns:
            Delete response
        """
        response = self.client.delete(f"{self.base_url}/documents/{document_id}")
        response.raise_for_status()

        return response.json()

    def reload_documents(self) -> Dict[str, Any]:
        """
        Reload documents from YAML file.

        Returns:
            Reload response
        """
        response = self.client.post(f"{self.base_url}/documents/reload")
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


def index_documents(documents: List[DocumentModel], base_url: str = "http://localhost:8000", 
                   rebuild: bool = True) -> IndexResponse:
    """
    Quick index function.
    
    Args:
        documents: List of documents to index
        base_url: Base URL of the BM25S service
        rebuild: Whether to rebuild entire index
        
    Returns:
        IndexResponse with indexing results
    """
    with BM25SClient(base_url) as client:
        return client.index_documents(documents, rebuild=rebuild)
