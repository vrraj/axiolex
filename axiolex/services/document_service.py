"""Document service for managing document operations."""

from typing import Dict, Any
from ..core.retriever import get_retriever
from ..utils.file_utils import validate_file_exists


def switch_document_file(filename: str, confirmed: bool = False) -> Dict[str, Any]:
    """Switch to a different document file."""
    retriever = get_retriever()
    
    # Validate file exists
    source_dir = "source_files"
    file_path = validate_file_exists(source_dir, filename)
    
    # Count user-added documents for warning
    user_added_count = sum(1 for doc in retriever.documents 
                         if doc.metadata and doc.metadata.get('source') == 'ui')
    
    # If not confirmed and there are user-added docs, return warning
    if not confirmed and user_added_count > 0:
        return {
            "requires_warning": True,
            "warning_message": f"This will delete {user_added_count} user-added documents and rebuild index from {filename}",
            "user_added_count": user_added_count
        }
    
    # Switch file and rebuild index
    retriever.document_file = file_path
    retriever._load_and_index_documents()
    
    return {
        "success": True,
        "message": f"Switched to {filename} and rebuilt index",
        "document_count": len(retriever.documents),
        "current_file": filename
    }
