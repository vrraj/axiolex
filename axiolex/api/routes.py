"""
FastAPI routes for BM25S retriever service.
"""

import time
import os
import json
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from ..core.retriever import BM25SRetriever, Document, get_retriever
from ..core.config import Config, load_config
from .models import (
    Document as DocumentModel,
    RetrieveRequest,
    RetrieveResponse,
    IndexRequest,
    IndexResponse,
    SettingsResponse,
    ErrorResponse,
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
                    parameters=doc.get("parameters", {}),
                    bm25_score=doc["bm25_score"],
                    softmax_score=doc["softmax_score"]
                ))
            
            return RetrieveResponse(
                success=result["success"],
                message=result["message"],
                documents=documents,
                total_retrieved=result["total_retrieved"],
                cutoff_percentage=result["cutoff_percentage"],
                settings=result["settings"]
            )
            
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
                    parameters=doc.parameters
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
    async def get_settings():
        """Get current settings."""
        try:
            retriever = get_retriever()
            settings = retriever.get_settings()
            
            return SettingsResponse(
                bm25s=BM25SSettingsModel(
                    temperature=settings.temperature,
                    ignore_zero=settings.ignore_zero,
                    llm_tools_cutoff=settings.llm_tools_cutoff
                ),
                documents={
                    "source": config.documents.source,
                    "auto_reload": config.documents.auto_reload,
                    "encoding": config.documents.encoding
                },
                server={
                    "host": config.server.host,
                    "port": config.server.port,
                    "reload": config.server.reload,
                    "log_level": config.server.log_level
                }
            )
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/settings", response_model=SettingsResponse)
    async def update_settings(settings: BM25SSettingsModel):
        """Update BM25S settings."""
        try:
            from ..core.config import BM25SSettings
            
            retriever = get_retriever()
            new_settings = BM25SSettings(
                temperature=settings.temperature,
                ignore_zero=settings.ignore_zero,
                llm_tools_cutoff=settings.llm_tools_cutoff
            )
            retriever.update_settings(new_settings)
            
            # Return updated settings
            updated = retriever.get_settings()
            
            return SettingsResponse(
                bm25s=BM25SSettingsModel(
                    temperature=updated.temperature,
                    ignore_zero=updated.ignore_zero,
                    llm_tools_cutoff=updated.llm_tools_cutoff
                ),
                documents={
                    "source": config.documents.source,
                    "auto_reload": config.documents.auto_reload,
                    "encoding": config.documents.encoding
                },
                server={
                    "host": config.server.host,
                    "port": config.server.port,
                    "reload": config.server.reload,
                    "log_level": config.server.log_level
                }
            )
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/documents")
    async def get_documents():
        """Get all documents."""
        try:
            retriever = get_retriever()
            
            documents = []
            for doc in retriever.documents:
                documents.append({
                    "id": doc.id,
                    "title": doc.title,
                    "content": doc.content,
                    "keywords": doc.keywords,
                    "metadata": doc.metadata,
                    "runtime": doc.runtime,
                    "artifact": doc.artifact,
                    "parameters": doc.parameters
                })
            
            return {
                "success": True,
                "documents": documents,
                "count": len(documents)
            }
            
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
                parameters=document.parameters
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
                "version": "1.0.0"
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/reload")
    async def reload_index():
        """Reload the retriever instance."""
        try:
            from ..core.retriever import _retriever_instance
            
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
            
            # Scan source_files directory for .yaml and .json files
            source_dir = "source_files"
            available_files = []
            
            if os.path.exists(source_dir):
                for file in os.listdir(source_dir):
                    if file.endswith(('.yaml', '.yml', '.json')):
                        available_files.append(file)
            
            # Count user-added documents
            user_added_count = sum(1 for doc in retriever.documents 
                                 if doc.metadata and doc.metadata.get('source') == 'ui')
            
            # Extract current filename from full path
            current_file = os.path.basename(retriever.document_file)
            
            # Warning required if there are user-added documents
            requires_warning = user_added_count > 0
            
            return FileInfo(
                available_files=sorted(available_files),
                current_file=current_file,
                user_added_count=user_added_count,
                requires_warning=requires_warning
            )
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/switch-document-file")
    async def switch_document_file(request: SwitchFileRequest):
        """Switch to a different document file."""
        try:
            retriever = get_retriever()
            
            # Validate file exists
            source_dir = "source_files"
            file_path = os.path.join(source_dir, request.filename)
            
            if not os.path.exists(file_path):
                raise HTTPException(status_code=404, detail=f"File '{request.filename}' not found")
            
            # Count user-added documents for warning
            user_added_count = sum(1 for doc in retriever.documents 
                                 if doc.metadata and doc.metadata.get('source') == 'ui')
            
            # If not confirmed and there are user-added docs, return warning
            if not request.confirmed and user_added_count > 0:
                return {
                    "requires_warning": True,
                    "warning_message": f"This will delete {user_added_count} user-added documents and rebuild index from {request.filename}",
                    "user_added_count": user_added_count
                }
            
            # Switch file and rebuild index
            retriever.document_file = file_path
            retriever._load_and_index_documents()
            
            return {
                "success": True,
                "message": f"Switched to {request.filename} and rebuilt index",
                "document_count": len(retriever.documents),
                "current_file": request.filename
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Global exception handler."""
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {str(exc)}")
    
    return app
