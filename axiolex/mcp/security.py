"""Credential handling helpers for MCP provider integrations."""

from __future__ import annotations

import os
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_SENSITIVE_QUERY_NAMES = {
    "api_key",
    "apikey",
    "authorization",
    "key",
    "password",
    "secret",
    "token",
    "access_token",
}

_SENSITIVE_HEADER_NAMES = {"authorization", "cookie", "x-api-key"}


def resolve_secret(secret_env: Optional[str]) -> Optional[str]:
    """Read a provider secret only from the backend process environment."""
    return os.getenv(secret_env) if secret_env else None


def append_api_key(endpoint: str, api_key: str) -> str:
    """Add an API key to an outbound provider URL without persisting it."""
    parsed = urlsplit(endpoint)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    query.append(("apikey", api_key))
    return urlunsplit(parsed._replace(query=urlencode(query)))


def contains_inline_credential(endpoint: Optional[str], headers: dict[str, str]) -> bool:
    """Identify credentials embedded in provider configuration values."""
    if endpoint:
        query_names = {name.lower() for name, _ in parse_qsl(urlsplit(endpoint).query)}
        if query_names & _SENSITIVE_QUERY_NAMES:
            return True
    return any(name.lower() in _SENSITIVE_HEADER_NAMES for name in headers)


def redact_url(url: Optional[str]) -> str:
    """Return a URL safe for logs by replacing sensitive query values."""
    if not url:
        return ""
    parsed = urlsplit(url)
    query = [
        (name, "REDACTED" if name.lower() in _SENSITIVE_QUERY_NAMES else value)
        for name, value in parse_qsl(parsed.query, keep_blank_values=True)
    ]
    return urlunsplit(parsed._replace(query=urlencode(query)))
