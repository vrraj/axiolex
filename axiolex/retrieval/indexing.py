from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from axiolex.utils.file_utils import is_source_entry_enabled

from .colbert import ColBERTDocument, ColBERTIndex, ColBERTModelConfig


def load_documents_from_yaml(file_path: str) -> List[ColBERTDocument]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Document YAML file not found: {file_path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    documents = []
    for entry in data.get("documents", []):
        if not isinstance(entry, dict):
            continue
        if not is_source_entry_enabled(entry):
            continue
        documents.append(
            ColBERTDocument(
                id=str(entry.get("id") or ""),
                title=str(entry.get("title") or ""),
                text=_document_text(entry),
                metadata=dict(entry.get("metadata") or {}),
            )
        )
    return documents


def build_colbert_index_from_yaml(
    file_path: str,
    config: Optional[ColBERTModelConfig] = None,
) -> ColBERTIndex:
    return ColBERTIndex(
        documents=load_documents_from_yaml(file_path),
        config=config,
    )


def _document_text(entry: Dict[str, Any]) -> str:
    parts = [
        str(entry.get("title") or ""),
        str(entry.get("content") or ""),
    ]
    keywords = entry.get("keywords") or []
    if isinstance(keywords, list):
        parts.extend(f"keyword: {keyword}" for keyword in keywords if keyword)
    return "\n".join(part for part in parts if part).strip()
