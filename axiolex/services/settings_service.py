"""Settings service for managing BM25S and application settings."""

from ..core.retriever import get_retriever
from ..core.config import BM25SSettings, Config, load_config
from ..api.models import BM25SSettings as BM25SSettingsModel, SettingsResponse


def get_settings(config: Config = None) -> SettingsResponse:
    """Get current settings."""
    if config is None:
        config = load_config()
    
    retriever = get_retriever()
    settings = retriever.get_settings()
    
    return SettingsResponse(
        bm25s=BM25SSettingsModel(
            temperature=settings.temperature,
            ignore_zero=settings.ignore_zero,
            llm_tools_cutoff=settings.llm_tools_cutoff
        ),
        documents={
            "source": config.documents.source,
            "auto_reload": config.documents.auto_reload,
            "encoding": config.documents.encoding
        },
        server={
            "host": config.server.host,
            "port": config.server.port,
            "reload": config.server.reload,
            "log_level": config.server.log_level
        }
    )


def update_settings(settings: BM25SSettingsModel, config: Config = None) -> SettingsResponse:
    """Update BM25S settings."""
    if config is None:
        config = load_config()
    
    retriever = get_retriever()
    new_settings = BM25SSettings(
        temperature=settings.temperature,
        ignore_zero=settings.ignore_zero,
        llm_tools_cutoff=settings.llm_tools_cutoff
    )
    retriever.update_settings(new_settings)
    
    # Return updated settings
    updated = retriever.get_settings()
    
    return SettingsResponse(
        bm25s=BM25SSettingsModel(
            temperature=updated.temperature,
            ignore_zero=updated.ignore_zero,
            llm_tools_cutoff=updated.llm_tools_cutoff
        ),
        documents={
            "source": config.documents.source,
            "auto_reload": config.documents.auto_reload,
            "encoding": config.documents.encoding
        },
        server={
            "host": config.server.host,
            "port": config.server.port,
            "reload": config.server.reload,
            "log_level": config.server.log_level
        }
    )
