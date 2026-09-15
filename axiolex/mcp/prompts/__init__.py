"""MCP Prompts support (Phase 1: local YAML catalog)."""

from .catalog import PromptCatalog
from .models import PromptArgument, PromptDefinition, PromptMessage
from .registration import register_prompts

__all__ = [
    "PromptCatalog",
    "PromptArgument",
    "PromptDefinition",
    "PromptMessage",
    "register_prompts",
]
