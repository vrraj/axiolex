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

    # Switch file and rebuild index
    retriever.document_file = file_path
    retriever._load_and_index_documents()

    return {
        "success": True,
        "message": f"Switched to {filename} and rebuilt index",
        "document_count": len(retriever.documents),
        "current_file": filename
    }
