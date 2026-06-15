from __future__ import annotations

from typing import Any, Iterable

from .colbert import ColBERTDocument


def documents_to_colbert(documents: Iterable[Any]) -> list[ColBERTDocument]:
    """Map canonical Axiolex documents into semantic-search documents."""
    return [
        ColBERTDocument(
            id=str(document.id),
            title=str(document.title),
            text=document_semantic_text(document),
            metadata={"source_document_id": str(document.id)},
        )
        for document in documents
    ]


def document_semantic_text(document: Any) -> str:
    runtime = document.runtime or {}
    params = document.params or runtime.get("params") or {}
    parts = [
        str(document.title or ""),
        str(document.content or ""),
        f"tool name: {runtime.get('tool_name', '')}",
    ]
    parts.extend(f"keyword: {keyword}" for keyword in (document.keywords or []))
    parts.extend(_parameter_text(name, schema) for name, schema in params.items())
    return "\n".join(part for part in parts if part and part.strip()).strip()


def _parameter_text(name: str, schema: Any) -> str:
    if not isinstance(schema, dict):
        return f"parameter: {name}"
    description = schema.get("description", "")
    parameter_type = schema.get("type", "")
    return f"parameter: {name} {parameter_type} {description}".strip()
