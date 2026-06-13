"""File utility functions."""

import os
from typing import List


def get_available_document_files(source_dir: str = "source_files") -> List[str]:
    """Get available document files from source directory."""
    available_files = []
    
    if os.path.exists(source_dir):
        for file in os.listdir(source_dir):
            if file.endswith(('.yaml', '.yml', '.json')):
                available_files.append(file)
    
    return sorted(available_files)


def validate_file_exists(source_dir: str, filename: str) -> str:
    """Validate file exists and return full path."""
    file_path = os.path.join(source_dir, filename)
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File '{filename}' not found")
    
    return file_path
