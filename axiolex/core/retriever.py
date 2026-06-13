"""
BM25S document retriever implementation.
"""

import bm25s
import Stemmer
import math
import yaml
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .config import BM25SSettings
from .cache import get_cache_manager, ToolCacheManager
from ..utils.file_utils import is_source_entry_enabled


@dataclass
class Document:
    """Document representation for BM25S indexing."""
    id: str
    title: str
    content: str
    keywords: List[str] = None
    metadata: Dict[str, Any] = None
    runtime: Dict[str, Any] = None
    artifact: Dict[str, Any] = None
    params: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []
        if self.metadata is None:
            self.metadata = {}
        if self.runtime is None:
            self.runtime = {}
        if self.artifact is None:
            self.artifact = {}
        if self.params is None:
            self.params = {}
    
    def copy(self) -> Dict[str, Any]:
        """Return a copy of document data as dict."""
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "keywords": self.keywords,
            "metadata": self.metadata,
            "runtime": self.runtime,
            "artifact": self.artifact,
            "params": self.params
        }


class BM25SRetriever:
    """BM25S-based document retrieval system with softmax scoring and cutoff filtering."""
    
    def __init__(self, settings: BM25SSettings = None, document_file: str = "source_files/tools_list.yaml", use_cache: bool = True):
        self.settings = settings or BM25SSettings()
        self.stemmer = Stemmer.Stemmer("english")
        self.documents: List[Document] = []
        self.retriever = None
        self.document_file = document_file
        self.use_cache = use_cache
        self.cache_manager: Optional[ToolCacheManager] = None
        
        if self.use_cache:
            try:
                self.cache_manager = get_cache_manager()
                if not self.cache_manager.is_connected():
                    print("Warning: Redis not connected, falling back to file-based loading")
                    self.cache_manager = None
            except Exception as e:
                print(f"Warning: Could not initialize cache manager: {e}")
                self.cache_manager = None
        
        self._load_and_index_documents()
    
    def _load_documents_from_yaml(self, file_path: str) -> List[Document]:
        """Load enabled documents from a YAML file."""
        if not os.path.exists(file_path):
            return []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            documents = []
            for doc_data in data.get('documents', []):
                if not is_source_entry_enabled(doc_data):
                    continue

                metadata = doc_data.get('metadata', {})
                runtime = doc_data.get('runtime', {})
                artifact = doc_data.get('artifact', {})
                params = runtime.get('params', {}) if isinstance(runtime, dict) else {}
                
                doc = Document(
                    id=doc_data['id'],
                    title=doc_data['title'],
                    content=doc_data['content'],
                    keywords=doc_data.get('keywords', []),
                    metadata=metadata,
                    runtime=runtime if isinstance(runtime, dict) else {},
                    artifact=artifact if isinstance(artifact, dict) else {},
                    params=params if isinstance(params, dict) else {}
                )
                documents.append(doc)
            
            return documents
        except Exception as e:
            print(f"Error loading documents from {file_path}: {e}")
            return []
    
    def _load_and_index_documents(self, documents: List[Document] = None):
        """Load documents and build BM25S index."""
        if documents is not None:
            self.documents = documents
        elif self.cache_manager:
            self.refresh_local_yaml_cache()
            cached_discovery = self.cache_manager.get_all_discovery()
            self.documents = self._convert_discovery_to_documents(cached_discovery)
        else:
            self.documents = self._load_documents_from_yaml(self.document_file)

        self._build_index_from_documents()
    
    def _convert_discovery_to_documents(self, discovery_list: List[Dict[str, Any]]) -> List[Document]:
        """Convert discovery data from Redis to Document objects."""
        documents = []
        for discovery in discovery_list:
            doc = Document(
                id=discovery.get("id", ""),
                title=discovery.get("title", ""),
                content=discovery.get("description", discovery.get("content", "")),
                keywords=[],
                metadata={
                    "category": discovery.get("category", "general"),
                    "provider": discovery.get("provider", "unknown"),
                    "source": discovery.get("source", "")
                },
                runtime={"tool_name": discovery.get("tool_name", "")},
                artifact={},
                params=discovery.get("params", {})
            )
            documents.append(doc)
        return documents
    
    def refresh_local_yaml_cache(self) -> int:
        """Replace local YAML entries in Redis with the current YAML file."""
        if not self.cache_manager:
            return 0
        
        self.cache_manager.delete_discovery_by_source("local_yaml")
        yaml_documents = self._load_documents_from_yaml(self.document_file)
        return self._cache_documents(yaml_documents, source="local_yaml", provider="yaml")
    
    def _cache_documents(self, documents: List[Document] = None, source: str = "local_yaml", provider: str = "yaml"):
        """Cache enabled documents to Redis."""
        if not self.cache_manager:
            return 0
        
        discovery_list = []
        runtime_list = []
        documents = documents if documents is not None else self.documents
        
        for doc in documents:
            if not is_source_entry_enabled({"metadata": doc.metadata}):
                continue

            # Cache discovery data
            discovery_list.append({
                "id": doc.id,
                "title": doc.title,
                "description": doc.content,
                "tool_name": doc.runtime.get("tool_name", ""),
                "params": doc.params,
                "category": doc.metadata.get("category", "general"),
                "provider": provider,
                "source": source
            })
            
            # Cache runtime data
            runtime_list.append({
                "id": doc.id,
                "runtime": {
                    "transport": doc.runtime.get("transport", ""),
                    "tool_name": doc.runtime.get("tool_name", ""),
                    "endpoint": doc.runtime.get("endpoint", {}),
                    "params": doc.params
                }
            })
        
        # Cache to Redis
        discovery_count = self.cache_manager.cache_all_discovery(discovery_list)
        runtime_count = self.cache_manager.cache_all_runtime(runtime_list)
        
        print(f"Cached {discovery_count} discovery entries and {runtime_count} runtime entries to Redis")
        return discovery_count
    
    def _calculate_softmax(self, scores: List[float], temperature: float = 1.0) -> List[float]:
        """Calculate softmax probabilities with temperature scaling."""
        if not scores:
            return []
        
        # Scale scores by temperature
        scaled_scores = [score / temperature for score in scores]
        
        # Subtract max for numerical stability
        max_score = max(scaled_scores)
        exp_scores = [math.exp(score - max_score) for score in scaled_scores]
        
        # Calculate softmax probabilities
        sum_exp = sum(exp_scores)
        if sum_exp == 0:
            return [0.0] * len(scores)
        
        return [exp_score / sum_exp for exp_score in exp_scores]
    
    def retrieve_documents(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Retrieve documents based on query using BM25S with softmax scoring.
        
        Args:
            query: Search query
            **kwargs: Optional overrides for settings
            
        Returns:
            Dictionary with retrieval results and metadata
        """
        try:
            if not self.retriever:
                return {
                    "success": False,
                    "message": "No documents indexed",
                    "documents": [],
                    "scores": [],
                    "softmax_scores": []
                }
            
            # Override settings with kwargs
            temperature = kwargs.get("temperature", self.settings.temperature)
            ignore_zero = kwargs.get("ignore_zero", self.settings.ignore_zero)
            llm_tools_cutoff = kwargs.get("llm_tools_cutoff", self.settings.llm_tools_cutoff)
            
            print(f"Debug: Starting retrieval with query: '{query}'")
            
            # Tokenize query
            query_tokens = bm25s.tokenize(query, stopwords="en", stemmer=self.stemmer)
            print(f"Debug: Query tokens: {query_tokens}")
            
            # Handle empty tokens
            if not query_tokens:
                return {
                    "success": False,
                    "message": "Query tokens are empty after processing",
                    "documents": [],
                    "total_retrieved": 0,
                    "cutoff_percentage": 0.0,
                    "settings": {
                        "temperature": temperature,
                        "ignore_zero": ignore_zero,
                        "llm_tools_cutoff": llm_tools_cutoff
                    }
                }
            
            # Retrieve scores using BM25S retrieve method
            results = self.retriever.retrieve(query_tokens, k=len(self.documents))
            print(f"Debug: BM25S retrieve results: {results}")
            print(f"Debug: Results type: {type(results)}")
            
            # Extract documents and scores from BM25S Results object
            if hasattr(results, 'documents') and hasattr(results, 'scores'):
                # Handle BM25S Results object
                indices = results.documents[0]  # Take first row
                scores = results.scores[0]     # Take first row
                print(f"Debug: Extracted indices: {indices}")
                print(f"Debug: Extracted scores: {scores}")
            else:
                # Fallback
                indices = list(range(len(self.documents)))
                scores = [0.0] * len(self.documents)
            
            print(f"Debug: Document IDs by index: {[self.documents[i].id for i in indices[:5]]}")
            
            # Prepare results
            results = []
            all_scores = []
            retrieved_docs = []
            
            print(f"Debug: Processing {len(scores)} results...")
            for i, (score, idx) in enumerate(zip(scores, indices)):
                print(f"Debug: Processing result {i}: score={score} (type: {type(score)}), idx={idx}")
                if idx < len(self.documents):
                    doc = self.documents[idx]
                    doc_dict = doc.copy()
                    score_float = float(score) if hasattr(score, 'item') else float(score)
                    print(f"Debug: Converted score to float: {score_float}")
                    doc_dict["bm25_score"] = score_float
                    retrieved_docs.append(doc_dict)
                    all_scores.append(score_float)
                else:
                    print(f"Debug: Index {idx} out of range (documents: {len(self.documents)})")
            
            print(f"Debug: Processed {len(all_scores)} scores")
            
            # Apply ignore_zero filter
            if ignore_zero:
                print("Debug: Applying ignore_zero filter...")
                filtered_docs = []
                filtered_scores = []
                for doc, score in zip(retrieved_docs, all_scores):
                    print(f"Debug: Checking score: {score} (type: {type(score)})")
                    score_float = float(score) if hasattr(score, 'item') else float(score)
                    if score_float > 0:
                        filtered_docs.append(doc)
                        filtered_scores.append(score_float)
                retrieved_docs = filtered_docs
                all_scores = filtered_scores
                print(f"Debug: After filtering: {len(all_scores)} documents")
            
            # Calculate softmax scores
            print(f"Debug: Calculating softmax with temperature: {temperature}")
            softmax_scores = self._calculate_softmax(all_scores, temperature)
            print(f"Debug: Softmax scores: {softmax_scores}")
            
            # Apply cutoff filtering
            cutoff_percentage = llm_tools_cutoff / 100.0
            print(f"Debug: Applying cutoff: {cutoff_percentage}")
            filtered_results = []
            
            for doc, score, softmax_score in zip(retrieved_docs, all_scores, softmax_scores):
                print(f"Debug: Checking softmax_score: {softmax_score} >= {cutoff_percentage}")
                doc["softmax_score"] = softmax_score
                if softmax_score >= cutoff_percentage:
                    filtered_results.append(doc)
            
            print(f"Debug: Final results: {len(filtered_results)} documents")
            
            # Sort by softmax score (descending)
            filtered_results.sort(key=lambda x: x["softmax_score"], reverse=True)
            
            return {
                "success": True,
                "message": f"Retrieved {len(filtered_results)} documents",
                "documents": filtered_results,
                "total_retrieved": len(retrieved_docs),
                "cutoff_percentage": cutoff_percentage,
                "settings": {
                    "temperature": temperature,
                    "ignore_zero": ignore_zero,
                    "llm_tools_cutoff": llm_tools_cutoff
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error during retrieval: {str(e)}",
                "documents": [],
                "total_retrieved": 0,
                "cutoff_percentage": 0.0,
                "settings": {
                    "temperature": temperature,
                    "ignore_zero": ignore_zero,
                    "llm_tools_cutoff": llm_tools_cutoff
                }
            }
    
    def add_documents(self, documents: List[Document]):
        """Add new documents and rebuild index."""
        self.documents.extend(documents)
        # Rebuild index with current documents (don't reload from YAML)
        self._build_index_from_documents()
    
    def _build_index_from_documents(self):
        """Build BM25S index from enabled documents in memory."""
        self.documents = [
            doc for doc in self.documents
            if is_source_entry_enabled({"metadata": doc.metadata})
        ]

        corpus = [
            " ".join(
                part
                for part in [
                    doc.title,
                    doc.content,
                    *(f"keyword: {keyword}" for keyword in doc.keywords),
                ]
                if part
            ).strip()
            for doc in self.documents
        ]

        if not corpus:
            self.retriever = None
            return

        corpus_tokens = bm25s.tokenize(corpus, stopwords="en", stemmer=self.stemmer)
        self.retriever = bm25s.BM25(method="lucene")
        self.retriever.index(corpus_tokens)
    
    def rebuild_index(self, documents: List[Document] = None):
        """Rebuild the BM25S index."""
        self._load_and_index_documents(documents)
    
    def get_document_count(self) -> int:
        """Get number of indexed documents."""
        return len(self.documents)
    
    def get_settings(self) -> BM25SSettings:
        """Get current settings."""
        return self.settings
    
    def update_settings(self, settings: BM25SSettings):
        """Update settings."""
        self.settings = settings


# Global retriever instance
_retriever_instance: Optional[BM25SRetriever] = None


def get_retriever() -> BM25SRetriever:
    """Get the global retriever instance."""
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = BM25SRetriever()
    return _retriever_instance


def retrieve_documents(query: str, documents: List[Document] = None, **kwargs) -> Dict[str, Any]:
    """
    Convenience function to retrieve documents based on query.
    
    Args:
        query: Search query
        documents: Optional document list (if provided, creates new retriever)
        **kwargs: Optional settings overrides
        
    Returns:
        Dictionary with retrieval results
    """
    if documents:
        retriever = BM25SRetriever()
        retriever.rebuild_index(documents)
        return retriever.retrieve_documents(query, **kwargs)
    else:
        retriever = get_retriever()
        return retriever.retrieve_documents(query, **kwargs)
