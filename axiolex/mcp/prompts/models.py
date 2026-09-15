"""Pydantic models for MCP prompts.

These map directly to the MCP Prompts specification data types:
  - Prompt:          name, title, description, arguments, messages
  - PromptArgument:  name, description, required, default
  - PromptMessage:   role, content (text-only in Phase 1)

Reference: https://modelcontextprotocol.io/specification/2025-11-25/server/prompts
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class PromptArgument(BaseModel):
    """A single argument for a prompt (MCP spec: PromptArgument)."""

    name: str
    description: Optional[str] = None
    required: bool = False
    default: Optional[Any] = None


class PromptMessageContent(BaseModel):
    """Content block of a prompt message.

    Phase 1 supports text content only. Image, audio, and resource
    content types are deferred to a later phase.
    """

    type: str = Field(default="text", pattern="^text$")
    text: str

    @model_validator(mode="after")
    def _validate_text_type(self) -> "PromptMessageContent":
        if self.type != "text":
            raise ValueError(
                f"Phase 1 supports text content only, got type='{self.type}'"
            )
        return self


class PromptMessage(BaseModel):
    """A single message in a prompt (MCP spec: PromptMessage)."""

    role: str = Field(pattern="^(user|assistant)$")
    content: PromptMessageContent

    @model_validator(mode="after")
    def _validate_role(self) -> "PromptMessage":
        if self.role not in ("user", "assistant"):
            raise ValueError(
                f"Prompt message role must be 'user' or 'assistant', got '{self.role}'"
            )
        return self


class PromptDefinition(BaseModel):
    """A complete prompt definition (MCP spec: Prompt).

    The ``messages`` field contains the template bodies with ``{{argument_name}}``
    placeholders for literal substitution at render time.
    """

    name: str
    title: Optional[str] = None
    description: Optional[str] = None
    arguments: List[PromptArgument] = Field(default_factory=list)
    messages: List[PromptMessage]

    def required_argument_names(self) -> List[str]:
        """Return names of arguments that have ``required: true``."""
        return [arg.name for arg in self.arguments if arg.required]

    def argument_defaults(self) -> Dict[str, Any]:
        """Return a dict of argument_name -> default for optional arguments."""
        return {
            arg.name: arg.default
            for arg in self.arguments
            if arg.default is not None
        }

    def all_argument_names(self) -> List[str]:
        """Return names of all declared arguments."""
        return [arg.name for arg in self.arguments]
