"""Namespace registry service — CRUD over source_files/namespaces.yaml."""

import os
from typing import Any, Dict, List

import yaml


def _namespaces_path() -> str:
    """Resolve the namespaces.yaml path.

    Checks in order:
    1. AXIOLEX_NAMESPACES_FILE env var (explicit override)
    2. source_files/namespaces.yaml relative to CWD (Docker, repo root)
    3. source_files/namespaces.yaml relative to the package (installed wheel)
    """
    env_path = os.getenv("AXIOLEX_NAMESPACES_FILE")
    if env_path and os.path.exists(env_path):
        return env_path

    cwd_path = os.path.join("source_files", "namespaces.yaml")
    if os.path.exists(cwd_path):
        return cwd_path

    pkg_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "source_files",
        "namespaces.yaml",
    )
    return pkg_path


def _load_all() -> List[Dict[str, Any]]:
    path = _namespaces_path()
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        data = yaml.safe_load(f) or {}
    return data.get("namespaces", [])


def _save_all(namespaces: List[Dict[str, Any]]) -> None:
    path = _namespaces_path()
    with open(path, "w") as f:
        yaml.safe_dump(
            {"namespaces": namespaces},
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )


def list_namespaces() -> List[Dict[str, Any]]:
    """Return all namespace entries (enabled and disabled)."""
    return _load_all()


def list_consumable_namespaces() -> List[Dict[str, Any]]:
    """Return enabled namespaces with only the consumer-facing fields.

    This is the clean capability map for calling applications:
    id, name, description. No internal fields like 'enabled'.
    """
    return [
        {
            "id": ns["id"],
            "name": ns.get("name", ns["id"]),
            "description": ns.get("description", ""),
        }
        for ns in _load_all()
        if ns.get("enabled", True)
    ]


def get_namespace(ns_id: str) -> Dict[str, Any]:
    for ns in _load_all():
        if ns["id"] == ns_id:
            return ns
    raise ValueError(f"Namespace '{ns_id}' not found")


def add_namespace(ns_id: str, name: str, description: str = "", enabled: bool = True) -> Dict[str, Any]:
    """Add a new namespace. Fails if the ID already exists."""
    ns_id = ns_id.strip()
    if not ns_id:
        raise ValueError("Namespace ID is required")
    if "." not in ns_id:
        raise ValueError("Namespace ID must contain a dot (e.g. finance.market_data)")
    namespaces = _load_all()
    if any(ns["id"] == ns_id for ns in namespaces):
        raise ValueError(f"Namespace '{ns_id}' already exists")
    entry = {
        "id": ns_id,
        "name": name.strip() or ns_id,
        "description": description.strip(),
        "enabled": enabled,
    }
    namespaces.append(entry)
    _save_all(namespaces)
    return {"success": True, "message": f"Namespace '{ns_id}' added", "namespace": entry}


def update_namespace(ns_id: str, name: str = None, description: str = None, enabled: bool = None) -> Dict[str, Any]:
    """Update an existing namespace. ID cannot be changed."""
    namespaces = _load_all()
    for ns in namespaces:
        if ns["id"] == ns_id:
            if name is not None:
                ns["name"] = name.strip() or ns_id
            if description is not None:
                ns["description"] = description.strip()
            if enabled is not None:
                ns["enabled"] = enabled
            _save_all(namespaces)
            return {"success": True, "message": f"Namespace '{ns_id}' updated", "namespace": ns}
    raise ValueError(f"Namespace '{ns_id}' not found")


def delete_namespace(ns_id: str) -> Dict[str, Any]:
    """Delete a namespace from the registry."""
    namespaces = _load_all()
    before = len(namespaces)
    namespaces = [ns for ns in namespaces if ns["id"] != ns_id]
    if len(namespaces) == before:
        raise ValueError(f"Namespace '{ns_id}' not found")
    _save_all(namespaces)
    return {"success": True, "message": f"Namespace '{ns_id}' deleted"}
