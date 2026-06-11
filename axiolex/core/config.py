"""
Configuration management for BM25S retriever.
"""

import os
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
class ServerConfig:
    """Server configuration."""
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False
    log_level: str = "info"


@dataclass
class Config:
    """Complete configuration."""
    bm25s: BM25SSettings = field(default_factory=BM25SSettings)
    documents: DocumentConfig = field(default_factory=DocumentConfig)
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
            "server": {
                "host": self.server.host,
                "port": self.server.port,
                "reload": self.server.reload,
                "log_level": self.server.log_level,
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        """Create from dictionary."""
        bm25s_data = data.get("bm25s", {})
        docs_data = data.get("documents", {})
        server_data = data.get("server", {})
        
        return cls(
            bm25s=BM25SSettings.from_dict(bm25s_data),
            documents=DocumentConfig(
                source=docs_data.get("source", "documents.yaml"),
                auto_reload=docs_data.get("auto_reload", True),
                encoding=docs_data.get("encoding", "utf-8"),
            ),
            server=ServerConfig(
                host=server_data.get("host", "0.0.0.0"),
                port=server_data.get("port", 8000),
                reload=server_data.get("reload", False),
                log_level=server_data.get("log_level", "info"),
            )
        )


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
