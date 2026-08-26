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
    "tavilyapikey",
}

_SENSITIVE_HEADER_NAMES = {"authorization", "cookie", "x-api-key"}


def resolve_secret(
    secret_env: Optional[str],
    provider_id: Optional[str] = None,
) -> Optional[str]:
    """Resolve a provider secret from the environment, then the encrypted store.

    Resolution order:
    1. OS environment variable named by ``secret_env`` (``.env`` path).
    2. Encrypted secret store keyed by ``provider_id`` (frontend-onboarded path).
    3. ``None`` if neither source has a value.

    ``provider_id`` is optional so existing call sites that only use ``.env``
    continue to work unchanged.
    """
    if secret_env:
        value = os.getenv(secret_env)
        if value:
            return value
    if provider_id:
        try:
            from .secret_store import get_secret_store

            return get_secret_store().get_secret(provider_id)
        except Exception:
            # Store missing or master key absent — fall through to None.
            return None
    return None


def append_api_key(
    endpoint: str,
    api_key: str,
    param_name: str = "api_key",
) -> str:
    """Add an API key to an outbound provider URL without persisting it.

    ``param_name`` defaults to ``"api_key"`` but can be overridden for
    providers that use a different query-parameter name (e.g. Tavily uses
    ``tavilyApiKey``).
    """
    parsed = urlsplit(endpoint)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    query.append((param_name, api_key))
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
