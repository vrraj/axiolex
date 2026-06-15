"""
FastAPI routes for BM25S retriever service.
"""

import time
import os
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from ..core.retriever import Document, get_retriever
from ..core.config import Config, load_config
from ..db.document_service import get_documents_from_cache
from ..utils.file_utils import get_available_document_files
from ..services.mcp_service import (
    get_all_providers,
    add_provider,
    update_provider,
    disable_provider,
    discover_provider_tools
)
from ..services.settings_service import get_settings, update_settings
from ..services.document_service import switch_document_file
from .models import (
    Document as DocumentModel,
    RetrieveRequest,
    RetrieveResponse,
    IndexRequest,
    IndexResponse,
    SettingsResponse,
    RetrievedDocument,
    BM25SSettings as BM25SSettingsModel
)


class SwitchFileRequest(BaseModel):
    filename: str
    confirmed: bool = False


class FileInfo(BaseModel):
    available_files: List[str]
    current_file: str
    user_added_count: int
    requires_warning: bool


def create_app(config: Config = None) -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(
        title="BM25S Retriever",
        description="A BM25S-based document retrieval service",
        version="1.0.0"
    )
    
    config = config or load_config()
    
    # Setup static files and templates
    app.mount("/static", StaticFiles(directory="axiolex/ui/static"), name="static")
    app.mount("/docs", StaticFiles(directory="docs"), name="docs")
    templates = Jinja2Templates(directory="axiolex/ui/templates")
    
    @app.get("/", response_class=HTMLResponse)
    async def root(request: Request):
        """Serve the main UI."""
        try:
            return templates.TemplateResponse("tool-router.html", {"request": request})
        except Exception as e:
            # Log the full error for debugging
            import traceback
            print(f"Template rendering error: {e}")
            print(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"Template rendering error: {str(e)}")
    
    @app.post("/retrieve", response_model=RetrieveResponse)
    async def retrieve_documents(request: RetrieveRequest):
        """Retrieve documents based on query."""
        try:
            retriever = get_retriever()
            
            # Override settings if provided
            kwargs = {}
            if request.temperature is not None:
                kwargs["temperature"] = request.temperature
            if request.ignore_zero is not None:
                kwargs["ignore_zero"] = request.ignore_zero
            if request.llm_tools_cutoff is not None:
                kwargs["llm_tools_cutoff"] = request.llm_tools_cutoff if request.llm_tools_cutoff else 0.0
            kwargs["hybrid_search"] = request.hybrid_search
            if request.max_results is not None:
                kwargs["max_results"] = request.max_results
            
            result = retriever.retrieve_documents(request.query, **kwargs)
            
            if not result["success"]:
                raise HTTPException(status_code=400, detail=result["message"])
            
            # Convert to response model
            documents = []
            for doc in result["documents"]:
                documents.append(RetrievedDocument(
                    id=doc["id"],
                    title=doc["title"],
                    content=doc["content"],
                    keywords=doc["keywords"],
                    metadata=doc["metadata"],
                    runtime=doc.get("runtime", {}),
                    artifact=doc.get("artifact", {}),
                    params=doc.get("params", {}),
                    bm25_score=doc.get("bm25_score"),
                    softmax_score=doc.get("softmax_score"),
                    bm25_rank=doc.get("bm25_rank"),
                    colbert_score=doc.get("colbert_score"),
                    colbert_rank=doc.get("colbert_rank"),
                    rrf_score=doc.get("rrf_score"),
                ))
            
            return RetrieveResponse(
                success=result["success"],
                message=result["message"],
                documents=documents,
                total_retrieved=result["total_retrieved"],
                cutoff_percentage=result["cutoff_percentage"],
                settings=result["settings"],
                search_mode=result.get("search_mode", "lexical"),
            )
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/index", response_model=IndexResponse)
    async def build_index(request: IndexRequest):
        """Build or rebuild BM25S index."""
        try:
            start_time = time.time()
            
            # Convert to Document objects
            documents = []
            for doc in request.documents:
                documents.append(Document(
                    id=doc.id,
                    title=doc.title,
                    content=doc.content,
                    keywords=doc.keywords,
                    metadata=doc.metadata,
                    runtime=doc.runtime,
                    artifact=doc.artifact,
                    params=doc.params
                ))
            
            # Build index
            retriever = get_retriever()
            if request.rebuild:
                retriever.rebuild_index(documents)
            else:
                retriever.add_documents(documents)
            
            index_time = (time.time() - start_time) * 1000
            
            return IndexResponse(
                success=True,
                message=f"Index built successfully with {len(documents)} documents",
                document_count=len(documents),
                index_time_ms=index_time
            )
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/settings", response_model=SettingsResponse)
    async def get_settings_endpoint():
        """Get current settings."""
        try:
            return get_settings(config)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/settings", response_model=SettingsResponse)
    async def update_settings_endpoint(settings: BM25SSettingsModel):
        """Update BM25S settings."""
        try:
            return update_settings(settings, config)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/documents")
    async def get_documents():
        """Get all documents from Redis cache."""
        try:
            return get_documents_from_cache()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/documents")
    async def add_document(document: DocumentModel):
        """Add a new document."""
        try:
            retriever = get_retriever()
            
            new_doc = Document(
                id=document.id,
                title=document.title,
                content=document.content,
                keywords=document.keywords,
                metadata=document.metadata,
                runtime=document.runtime,
                artifact=document.artifact,
                params=document.params
            )
            
            retriever.add_documents([new_doc])
            
            return {
                "success": True,
                "message": f"Document '{document.id}' added successfully"
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.delete("/documents/{document_id}")
    async def delete_document(document_id: str):
        """Delete a document."""
        try:
            retriever = get_retriever()
            
            # Remove document by ID
            original_count = len(retriever.documents)
            retriever.documents = [doc for doc in retriever.documents if doc.id != document_id]
            
            if len(retriever.documents) == original_count:
                raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")
            
            # Rebuild index
            retriever._load_and_index_documents()
            
            return {
                "success": True,
                "message": f"Document '{document_id}' deleted successfully"
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/documents/reload")
    async def reload_documents():
        """Reload documents from YAML file."""
        try:
            retriever = get_retriever()
            retriever._load_and_index_documents()
            
            return {
                "success": True,
                "message": f"Documents reloaded. {len(retriever.documents)} documents loaded."
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/documents/reindex-bm25s")
    async def reindex_retrieval_documents():
        """Rebuild enabled retrieval indexes from currently loaded documents."""
        try:
            start_time = time.time()
            retriever = get_retriever()
            retriever._load_and_index_documents()
            index_time = (time.time() - start_time) * 1000
            
            return {
                "success": True,
                "message": (
                    f"Retrieval indexes rebuilt with {len(retriever.documents)} "
                    "documents."
                ),
                "document_count": len(retriever.documents),
                "index_time_ms": index_time,
                "hybrid_search": retriever.get_hybrid_status(),
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/status")
    async def get_status():
        """Get service status."""
        try:
            retriever = get_retriever()
            doc_count = retriever.get_document_count()
            
            return {
                "status": "healthy",
                "document_count": doc_count,
                "retriever_initialized": retriever.retriever is not None,
                "version": "1.0.0",
                "hybrid_search": retriever.get_hybrid_status(),
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/reload")
    async def reload_index():
        """Reload the retriever instance."""
        try:
            # Clear global instance
            import importlib
            import axiolex.core.retriever
            importlib.reload(axiolex.core.retriever)
            
            return {
                "success": True,
                "message": "Retriever reloaded successfully"
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/document-files", response_model=FileInfo)
    async def get_document_files():
        """Get available document files and current file info."""
        try:
            retriever = get_retriever()
            
            # Get available files
            available_files = get_available_document_files()
            
            # Count user-added documents
            user_added_count = sum(1 for doc in retriever.documents 
                                 if doc.metadata and doc.metadata.get('source') == 'ui')
            
            # Extract current filename from full path
            current_file = os.path.basename(retriever.document_file)
            
            # Warning required if there are user-added documents
            requires_warning = user_added_count > 0
            
            return FileInfo(
                available_files=available_files,
                current_file=current_file,
                user_added_count=user_added_count,
                requires_warning=requires_warning
            )
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/switch-document-file")
    async def switch_document_file_endpoint(request: SwitchFileRequest):
        """Switch to a different document file."""
        try:
            return switch_document_file(request.filename, request.confirmed)
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # MCP Provider Management Endpoints
    @app.get("/mcp-providers")
    async def get_mcp_providers():
        """Get all MCP providers."""
        try:
            return get_all_providers()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/mcp-providers")
    async def add_mcp_provider(provider_data: Dict[str, Any]):
        """Add a new MCP provider."""
        try:
            return add_provider(provider_data)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.put("/mcp-providers/{provider_id}")
    async def update_mcp_provider(provider_id: str, provider_data: Dict[str, Any]):
        """Update an existing MCP provider."""
        try:
            return update_provider(provider_id, provider_data)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.delete("/mcp-providers/{provider_id}")
    async def disable_mcp_provider(provider_id: str):
        """Disable an MCP provider and clear its cached tools."""
        try:
            return disable_provider(provider_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/mcp-providers/{provider_id}/discover")
    async def discover_mcp_provider_tools(provider_id: str):
        """Discover tools from a specific MCP provider."""
        try:
            return await discover_provider_tools(provider_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Global exception handler."""
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {str(exc)}")
    
    return app
