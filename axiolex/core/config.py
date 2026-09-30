"""
Configuration management for BM25S retriever.
"""

import base64
import binascii
import ipaddress
import os
import ssl
import yaml
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class BM25SSettings:
    """BM25S retrieval settings."""
    temperature: float = 0.5
    ignore_zero: bool = True
    llm_tools_cutoff: float = 12.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "temperature": self.temperature,
            "ignore_zero": self.ignore_zero,
            "llm_tools_cutoff": self.llm_tools_cutoff,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BM25SSettings":
        """Create from dictionary."""
        return cls(
            temperature=data.get("temperature", 0.5),
            ignore_zero=data.get("ignore_zero", True),
            llm_tools_cutoff=data.get("llm_tools_cutoff", 12.0),
        )


@dataclass
class DocumentConfig:
    """Document configuration."""
    source: str = "documents.yaml"
    auto_reload: bool = True
    encoding: str = "utf-8"


@dataclass
class MCPConfig:
    """MCP provider configuration."""
    providers_file: str = "source_files/mcp_providers.yaml"
    auto_discover: bool = True
    cache_ttl: int = 3600  # 1 hour in seconds


@dataclass
class ServerConfig:
    """Inbound HTTP transport and authentication configuration."""
    host: str = "127.0.0.1"
    port: int = 9700
    reload: bool = False
    log_level: str = "info"
    protocol: str = "http"
    ssl_certfile: Optional[str] = None
    ssl_keyfile: Optional[str] = None
    auth_mode: str = "off"
    api_bearer_token: Optional[str] = None
    external_auth_gateway: Optional[str] = None
    operator_session_ttl_seconds: int = 3600
    operator_login_max_attempts: int = 5
    operator_login_window_seconds: int = 60


@dataclass
class Config:
    """Complete configuration."""
    bm25s: BM25SSettings = field(default_factory=BM25SSettings)
    documents: DocumentConfig = field(default_factory=DocumentConfig)
    mcp: MCPConfig = field(default_factory=MCPConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "bm25s": self.bm25s.to_dict(),
            "documents": {
                "source": self.documents.source,
                "auto_reload": self.documents.auto_reload,
                "encoding": self.documents.encoding,
            },
            "mcp": {
                "providers_file": self.mcp.providers_file,
                "auto_discover": self.mcp.auto_discover,
                "cache_ttl": self.mcp.cache_ttl,
            },
            "server": {
                "host": self.server.host,
                "port": self.server.port,
                "reload": self.server.reload,
                "log_level": self.server.log_level,
                "protocol": self.server.protocol,
                "ssl_certfile": self.server.ssl_certfile,
                "ssl_keyfile": self.server.ssl_keyfile,
                "auth_mode": self.server.auth_mode,
                "external_auth_gateway": self.server.external_auth_gateway,
                "operator_session_ttl_seconds": self.server.operator_session_ttl_seconds,
                "operator_login_max_attempts": self.server.operator_login_max_attempts,
                "operator_login_window_seconds": self.server.operator_login_window_seconds,
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        """Create from dictionary."""
        bm25s_data = data.get("bm25s", {})
        docs_data = data.get("documents", {})
        mcp_data = data.get("mcp", {})
        server_data = data.get("server", {})
        
        return cls(
            bm25s=BM25SSettings.from_dict(bm25s_data),
            documents=DocumentConfig(
                source=docs_data.get("source", "documents.yaml"),
                auto_reload=docs_data.get("auto_reload", True),
                encoding=docs_data.get("encoding", "utf-8"),
            ),
            mcp=MCPConfig(
                providers_file=mcp_data.get("providers_file", "source_files/mcp_providers.yaml"),
                auto_discover=mcp_data.get("auto_discover", True),
                cache_ttl=mcp_data.get("cache_ttl", 3600),
            ),
            server=ServerConfig(
                host=server_data.get("host", "127.0.0.1"),
                port=server_data.get("port", 9700),
                reload=server_data.get("reload", False),
                log_level=server_data.get("log_level", "info"),
                protocol=server_data.get("protocol", "http"),
                ssl_certfile=server_data.get("ssl_certfile"),
                ssl_keyfile=server_data.get("ssl_keyfile"),
                auth_mode=server_data.get("auth_mode", "off"),
                external_auth_gateway=server_data.get("external_auth_gateway"),
                operator_session_ttl_seconds=server_data.get("operator_session_ttl_seconds", 3600),
                operator_login_max_attempts=server_data.get("operator_login_max_attempts", 5),
                operator_login_window_seconds=server_data.get("operator_login_window_seconds", 60),
            )
        )


def _is_loopback_bind(host: str) -> bool:
    """Return whether a bind host is explicitly local-only."""
    normalized = host.strip().lower()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _is_strong_bearer_token(token: str) -> bool:
    """Validate the base64url form used for the shared static secret."""
    if not token or token.strip() != token or len(token) < 43:
        return False
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    except (ValueError, binascii.Error):
        return False
    return len(raw) >= 32


def validate_server_security(server: ServerConfig) -> None:
    """Fail closed for insecure inbound transport/authentication settings.

    This validation is intentionally separate from request authentication so
    every supported launcher can run it before binding a socket.
    """
    if server.protocol not in {"http", "https"}:
        raise ValueError("AXIOLEX_PROTOCOL must be exactly 'http' or 'https'.")
    if isinstance(server.port, bool) or not isinstance(server.port, int) or not 1 <= server.port <= 65535:
        raise ValueError("AXIOLEX_PORT must be an integer from 1 through 65535.")
    if not isinstance(server.host, str) or not server.host.strip():
        raise ValueError("AXIOLEX_HOST must be a nonempty bind address.")
    if server.auth_mode not in {"off", "static", "external"}:
        raise ValueError("AXIOLEX_AUTH_MODE must be 'off', 'static', or 'external'.")
    for name, value in (
        ("AXIOLEX_OPERATOR_SESSION_TTL_SECONDS", server.operator_session_ttl_seconds),
        ("AXIOLEX_OPERATOR_LOGIN_MAX_ATTEMPTS", server.operator_login_max_attempts),
        ("AXIOLEX_OPERATOR_LOGIN_WINDOW_SECONDS", server.operator_login_window_seconds),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{name} must be a positive integer.")
    if server.auth_mode == "off" and not _is_loopback_bind(server.host):
        raise ValueError("AXIOLEX_AUTH_MODE=off is allowed only with a loopback AXIOLEX_HOST.")
    if server.auth_mode == "static" and not _is_strong_bearer_token(server.api_bearer_token or ""):
        raise ValueError(
            "AXIOLEX_AUTH_MODE=static requires AXIOLEX_API_BEARER_TOKEN to be a "
            "base64url-encoded secret containing at least 32 random bytes."
        )
    if server.auth_mode == "external" and not (server.external_auth_gateway or "").strip():
        raise ValueError(
            "AXIOLEX_AUTH_MODE=external requires AXIOLEX_EXTERNAL_AUTH_GATEWAY "
            "to identify the trusted gateway boundary."
        )
    if server.protocol == "https":
        if not server.ssl_certfile or not server.ssl_keyfile:
            raise ValueError(
                "AXIOLEX_PROTOCOL=https requires both AXIOLEX_SSL_CERTFILE and "
                "AXIOLEX_SSL_KEYFILE."
            )
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(server.ssl_certfile, server.ssl_keyfile)
        except (OSError, ssl.SSLError) as exc:
            raise ValueError("Axiolex could not load the configured TLS certificate/key.") from exc


def uvicorn_tls_kwargs(server: ServerConfig) -> Dict[str, str]:
    """Return TLS parameters only after startup validation has succeeded."""
    if server.protocol == "https":
        return {"ssl_certfile": server.ssl_certfile, "ssl_keyfile": server.ssl_keyfile}
    return {}


def load_config(config_path: Optional[str] = None) -> Config:
    """
    Load configuration from file or environment variables.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Config object
    """
    # Start with defaults
    config = Config()
    
    # Load from file if provided
    if config_path and os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            if data:
                config = Config.from_dict(data)
    
    # Override with environment variables
    if os.getenv("BM25S_TEMPERATURE"):
        config.bm25s.temperature = float(os.getenv("BM25S_TEMPERATURE"))
    
    if os.getenv("BM25S_IGNORE_ZERO"):
        config.bm25s.ignore_zero = os.getenv("BM25S_IGNORE_ZERO").lower() == "true"
    
    if os.getenv("BM25S_CUTOFF"):
        config.bm25s.llm_tools_cutoff = float(os.getenv("BM25S_CUTOFF"))
    
    if os.getenv("BM25S_HOST"):
        config.server.host = os.getenv("BM25S_HOST")
    
    if os.getenv("BM25S_PORT"):
        config.server.port = int(os.getenv("BM25S_PORT"))
    
    if os.getenv("BM25S_LOG_LEVEL"):
        config.server.log_level = os.getenv("BM25S_LOG_LEVEL")

    # AXIOLEX_* is the canonical inbound transport/auth contract. Preserve the
    # old BM25S_* aliases above for compatibility, then override them here.
    if os.getenv("AXIOLEX_HOST"):
        config.server.host = os.getenv("AXIOLEX_HOST")
    if os.getenv("AXIOLEX_PORT"):
        try:
            config.server.port = int(os.getenv("AXIOLEX_PORT", ""))
        except ValueError as exc:
            raise ValueError("AXIOLEX_PORT must be an integer from 1 through 65535.") from exc
    if os.getenv("AXIOLEX_PROTOCOL"):
        config.server.protocol = os.getenv("AXIOLEX_PROTOCOL", "")
    if os.getenv("AXIOLEX_SSL_CERTFILE"):
        config.server.ssl_certfile = os.getenv("AXIOLEX_SSL_CERTFILE")
    if os.getenv("AXIOLEX_SSL_KEYFILE"):
        config.server.ssl_keyfile = os.getenv("AXIOLEX_SSL_KEYFILE")
    if os.getenv("AXIOLEX_AUTH_MODE"):
        config.server.auth_mode = os.getenv("AXIOLEX_AUTH_MODE", "")
    if os.getenv("AXIOLEX_API_BEARER_TOKEN"):
        config.server.api_bearer_token = os.getenv("AXIOLEX_API_BEARER_TOKEN")
    if os.getenv("AXIOLEX_EXTERNAL_AUTH_GATEWAY"):
        config.server.external_auth_gateway = os.getenv("AXIOLEX_EXTERNAL_AUTH_GATEWAY")
    for env_name, attribute in (
        ("AXIOLEX_OPERATOR_SESSION_TTL_SECONDS", "operator_session_ttl_seconds"),
        ("AXIOLEX_OPERATOR_LOGIN_MAX_ATTEMPTS", "operator_login_max_attempts"),
        ("AXIOLEX_OPERATOR_LOGIN_WINDOW_SECONDS", "operator_login_window_seconds"),
    ):
        if os.getenv(env_name):
            try:
                setattr(config.server, attribute, int(os.getenv(env_name, "")))
            except ValueError as exc:
                raise ValueError(f"{env_name} must be a positive integer.") from exc

    validate_server_security(config.server)
    
    return config


def save_config(config: Config, config_path: str):
    """
    Save configuration to file.
    
    Args:
        config: Configuration object
        config_path: Path to save configuration
    """
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config.to_dict(), f, default_flow_style=False, indent=2)
