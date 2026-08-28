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
from ..services.tool_discovery_service import _resolve_hybrid_search
from ..services.mcp_service import (
    get_all_providers,
    add_provider,
    update_provider,
    disable_provider,
    discover_provider_tools,
    set_provider_secret,
    get_provider_secret_status,
    delete_provider_secret,
    delete_provider_tools,
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
    BM25SSettings as BM25SSettingsModel,
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
        version="1.0.0",
    )

    config = config or load_config()

    @app.on_event("startup")
    def _eager_init_retriever():
        """Initialize the retriever at startup so the server fails fast
        if Redis is unreachable or the catalog is empty."""
        get_retriever()

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
            raise HTTPException(
                status_code=500, detail=f"Template rendering error: {str(e)}"
            )

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
                kwargs["llm_tools_cutoff"] = (
                    request.llm_tools_cutoff if request.llm_tools_cutoff else 0.0
                )
            kwargs["hybrid_search"] = _resolve_hybrid_search(request.hybrid_search)
            effective_top_k = request.top_k if request.top_k is not None else request.max_results
            if effective_top_k is not None:
                kwargs["max_results"] = effective_top_k
            if request.bm25_weight is not None:
                kwargs["bm25_weight"] = request.bm25_weight
            if request.colbert_weight is not None:
                kwargs["colbert_weight"] = request.colbert_weight
            if request.candidate_limit is not None:
                kwargs["candidate_limit"] = request.candidate_limit
            if request.min_hybrid_score is not None:
                kwargs["min_hybrid_score"] = request.min_hybrid_score
            if request.min_rrf_score is not None:
                kwargs["min_rrf_score"] = request.min_rrf_score
            if request.namespaces is not None:
                kwargs["namespaces"] = request.namespaces

            result = retriever.retrieve_documents(request.query, **kwargs)

            if not result["success"]:
                raise HTTPException(status_code=400, detail=result["message"])

            # Convert to response model
            documents = []
            for doc in result["documents"]:
                documents.append(
                    RetrievedDocument(
                        id=doc["id"],
                        title=doc["title"],
                        content=doc["content"],
                        keywords=doc["keywords"],
                        metadata=doc["metadata"],
                        runtime=doc.get("runtime", {}),
                        artifact=doc.get("artifact", {}),
                        params=doc.get("params", {}),
                        rank=doc.get("rank"),
                        relevance_score=doc.get("relevance_score"),
                        bm25_score=doc.get("bm25_score"),
                        softmax_score=doc.get("softmax_score"),
                        bm25_rank=doc.get("bm25_rank"),
                        bm25_softmax_score=doc.get("bm25_softmax_score"),
                        colbert_score=doc.get("colbert_score"),
                        colbert_rank=doc.get("colbert_rank"),
                        colbert_softmax_score=doc.get("colbert_softmax_score"),
                        hybrid_score=doc.get("hybrid_score"),
                        rrf_score=doc.get("rrf_score"),
                    )
                )

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

    @app.post("/discover")
    async def discover_tools(request: RetrieveRequest):
        """Discover execution-ready tools for a natural-language query."""
        try:
            from ..services.tool_discovery_service import ToolDiscoveryService
            retriever = get_retriever()
            service = ToolDiscoveryService(retriever=retriever)

            namespaces = request.namespaces
            effective_top_k = request.top_k if request.top_k is not None else request.max_results
            result = service.discover_tools(
                query=request.query,
                max_tools=effective_top_k,
                hybrid_search=request.hybrid_search,
                temperature=request.temperature,
                min_hybrid_score=request.min_hybrid_score,
                bm25_weight=request.bm25_weight,
                colbert_weight=request.colbert_weight,
                candidate_limit=request.candidate_limit,
                min_rrf_score=request.min_rrf_score,
                namespaces=namespaces,
            )
            return result
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/namespaces")
    async def list_namespaces():
        """List all registered namespaces (management — includes disabled)."""
        try:
            from ..services.namespace_service import list_namespaces as _list
            return _list()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/capabilities")
    async def list_capabilities():
        """Return the enterprise capability map for consuming applications.

        Returns only enabled namespaces with id, name, description.
        This is the clean consumer-facing endpoint — use this (or the SDK
        list_namespaces() method) to discover available capability areas,
        not the /namespaces management endpoint.
        """
        try:
            from ..services.namespace_service import list_consumable_namespaces
            return list_consumable_namespaces()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/namespaces")
    async def add_namespace(body: Dict[str, Any]):
        """Add a new namespace."""
        try:
            from ..services.namespace_service import add_namespace as _add
            return _add(
                ns_id=body.get("id", ""),
                name=body.get("name", ""),
                description=body.get("description", ""),
                enabled=body.get("enabled", True),
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.put("/namespaces/{ns_id}")
    async def update_namespace(ns_id: str, body: Dict[str, Any]):
        """Update an existing namespace."""
        try:
            from ..services.namespace_service import update_namespace as _update
            return _update(
                ns_id=ns_id,
                name=body.get("name"),
                description=body.get("description"),
                enabled=body.get("enabled"),
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/namespaces/{ns_id}")
    async def delete_namespace(ns_id: str):
        """Delete a namespace."""
        try:
            from ..services.namespace_service import delete_namespace as _delete
            return _delete(ns_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
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
                documents.append(
                    Document(
                        id=doc.id,
                        title=doc.title,
                        content=doc.content,
                        keywords=doc.keywords,
                        metadata=doc.metadata,
                        runtime=doc.runtime,
                        artifact=doc.artifact,
                        params=doc.params,
                    )
                )

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
                index_time_ms=index_time,
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
                params=document.params,
            )

            retriever.add_documents([new_doc])

            return {
                "success": True,
                "message": f"Document '{document.id}' added successfully",
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
            retriever.documents = [
                doc for doc in retriever.documents if doc.id != document_id
            ]

            if len(retriever.documents) == original_count:
                raise HTTPException(
                    status_code=404, detail=f"Document '{document_id}' not found"
                )

            # Rebuild index
            retriever._load_and_index_documents()

            return {
                "success": True,
                "message": f"Document '{document_id}' deleted successfully",
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
                "message": f"Documents reloaded. {len(retriever.documents)} documents loaded.",
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
            from ..services.tool_discovery_service import DEFAULT_TOP_K
            retriever = get_retriever()
            doc_count = retriever.get_document_count()

            return {
                "status": "healthy",
                "document_count": doc_count,
                "retriever_initialized": retriever is not None,
                "version": "1.0.0",
                "hybrid_search": retriever.get_hybrid_status(),
                "default_top_k": DEFAULT_TOP_K,
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

            return {"success": True, "message": "Retriever reloaded successfully"}

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
            user_added_count = sum(
                1
                for doc in retriever.documents
                if doc.metadata and doc.metadata.get("source") == "ui"
            )

            # Extract current filename from full path
            current_file = os.path.basename(retriever.document_file)

            # Warning required if there are user-added documents
            requires_warning = user_added_count > 0

            return FileInfo(
                available_files=available_files,
                current_file=current_file,
                user_added_count=user_added_count,
                requires_warning=requires_warning,
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
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.put("/mcp-providers/{provider_id}")
    async def update_mcp_provider(provider_id: str, provider_data: Dict[str, Any]):
        """Update an existing MCP provider."""
        try:
            return update_provider(provider_id, provider_data)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
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

    @app.delete("/mcp-providers/{provider_id}/tools")
    async def delete_mcp_provider_tools(provider_id: str):
        """Delete all cached tools for a provider without disabling it."""
        try:
            return delete_provider_tools(provider_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/mcp-providers/{provider_id}/secret")
    async def set_mcp_provider_secret(provider_id: str, body: Dict[str, Any]):
        """Encrypt and store a provider secret (API key / bearer token).

        The secret value is never persisted in YAML, Redis, or logs. It is
        encrypted with AES-256-GCM using the AXIOLEX_SECRET_MASTER_KEY env var
        and written to source_files/mcp_secrets.enc.
        """
        try:
            secret = body.get("secret")
            if not secret:
                raise ValueError("Request body must include a non-empty 'secret' field.")
            return set_provider_secret(provider_id, secret)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/mcp-providers/{provider_id}/secret")
    async def get_mcp_provider_secret_status(provider_id: str):
        """Return whether a stored secret exists (never the secret value)."""
        try:
            return get_provider_secret_status(provider_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/mcp-providers/{provider_id}/secret")
    async def delete_mcp_provider_secret(provider_id: str):
        """Remove a stored secret for the provider."""
        try:
            return delete_provider_secret(provider_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Global exception handler."""
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {str(exc)}")

    return app
