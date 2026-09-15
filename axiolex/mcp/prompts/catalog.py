"""Prompt catalog: loads, validates, and renders prompts from a local YAML file.

Phase 1: local YAML catalog only. The storage interface (``list_prompts`` and
``get_prompt``) is designed so the backend can be swapped to Redis in Phase 2
without touching the MCP server layer.

Template rendering uses literal ``{{argument_name}}`` substitution:
  - No HTML escaping
  - No recursive template evaluation
  - Missing required arguments raise ValueError (caller maps to JSON-RPC -32602)
  - Optional arguments with defaults are filled if omitted
  - Unknown arguments in the template that are not in the argument list are
    left as-is (literal text, not substituted)
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .models import PromptDefinition, PromptMessage

# Literal {{arg}} placeholder pattern. Non-greedy, alphanumeric + underscore.
_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")

# Default limit for list_prompts pagination (MCP spec: server-defined default).
DEFAULT_LIMIT = 50


class PromptCatalog:
    """Loads and serves prompts from a local YAML file.

    The catalog is loaded once at construction. Restart the server to apply
    changes to the YAML file (no live reload in Phase 1).
    """

    def __init__(self, yaml_path: Optional[str] = None) -> None:
        """Load and validate the prompt catalog.

        Args:
            yaml_path: Path to the prompts YAML file. If None, uses the default
                      ``source_files/prompts_list.yaml`` relative to the project
                      root or the installed package location.

        Raises:
            FileNotFoundError: If the YAML file does not exist.
            ValueError: If the YAML contains duplicate prompt names or invalid
                prompt definitions.
        """
        self._yaml_path = yaml_path or self._default_yaml_path()
        self._prompts: Dict[str, PromptDefinition] = {}
        self._load()

    @staticmethod
    def _default_yaml_path() -> str:
        """Resolve the default YAML path.

        Checks (in order):
          1. CWD / source_files / prompts_list.yaml
          2. Package-shipped source_files / prompts_list.yaml
        """
        candidates = [
            Path("source_files") / "prompts_list.yaml",
            Path(__file__).resolve().parent.parent.parent.parent / "source_files" / "prompts_list.yaml",
            Path(__file__).resolve().parent.parent.parent / "source_files" / "prompts_list.yaml",
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        # Return the first candidate even if it doesn't exist — _load will
        # raise FileNotFoundError with a clear message.
        return str(candidates[0])

    def _load(self) -> None:
        """Load and validate the YAML file into ``self._prompts``."""
        path = Path(self._yaml_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Prompts YAML file not found: {path}. "
                f"Create it or remove the prompts_list.yaml reference."
            )

        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        prompt_list = raw.get("prompts", [])
        if not isinstance(prompt_list, list):
            raise ValueError(
                f"Invalid prompts YAML: 'prompts' must be a list, got {type(prompt_list).__name__}"
            )

        seen_names: set = set()
        for entry in prompt_list:
            try:
                prompt = PromptDefinition.model_validate(entry)
            except Exception as exc:
                raise ValueError(
                    f"Invalid prompt definition for '{entry.get('name', '<unknown>')}': {exc}"
                ) from exc

            if prompt.name in seen_names:
                raise ValueError(
                    f"Duplicate prompt name '{prompt.name}' in {path}. "
                    f"Prompt names must be unique."
                )
            seen_names.add(prompt.name)
            self._prompts[prompt.name] = prompt

    # ------------------------------------------------------------------
    # Public interface (designed to be backend-agnostic for Phase 2)
    # ------------------------------------------------------------------

    def list_prompts(
        self,
        cursor: Optional[str] = None,
        limit: int = DEFAULT_LIMIT,
    ) -> Dict[str, Any]:
        """Return a page of prompt definitions (without template bodies).

        This corresponds to the MCP ``prompts/list`` response. Returns names,
        titles, descriptions, and argument definitions — not the message
        templates.

        Args:
            cursor: Opaque pagination cursor (offset as string). None starts
                    from the beginning.
            limit: Maximum number of prompts to return.

        Returns:
            Dict with ``prompts`` (list of prompt metadata) and
            ``nextCursor`` (str or None if no more pages).
        """
        all_names = sorted(self._prompts.keys())
        offset = int(cursor) if cursor else 0
        page = all_names[offset : offset + limit]

        prompts_meta = []
        for name in page:
            p = self._prompts[name]
            prompts_meta.append(
                {
                    "name": p.name,
                    "title": p.title,
                    "description": p.description,
                    "arguments": [
                        {
                            "name": arg.name,
                            "description": arg.description,
                            "required": arg.required,
                        }
                        for arg in p.arguments
                    ],
                }
            )

        next_offset = offset + len(page)
        next_cursor = str(next_offset) if next_offset < len(all_names) else None

        return {"prompts": prompts_meta, "nextCursor": next_cursor}

    def get_prompt(
        self, name: str, arguments: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Render a prompt by name with the given arguments.

        This corresponds to the MCP ``prompts/get`` response. Validates
        arguments, applies defaults for omitted optional arguments, and
        performs literal ``{{arg}}`` substitution in message templates.

        Args:
            name: The prompt name.
            arguments: Caller-supplied argument values.

        Returns:
            Dict with ``description`` and ``messages`` (rendered).

        Raises:
            ValueError: If the prompt name is unknown or required arguments
                        are missing. The caller should map these to
                        JSON-RPC error -32602 (invalid params).
        """
        if name not in self._prompts:
            raise ValueError(f"Unknown prompt: '{name}'")

        prompt = self._prompts[name]
        arguments = arguments or {}

        # Validate required arguments
        required = set(prompt.required_argument_names())
        missing = required - set(arguments.keys())
        if missing:
            raise ValueError(
                f"Missing required argument(s) for prompt '{name}': "
                f"{', '.join(sorted(missing))}"
            )

        # Fill defaults for omitted optional arguments
        rendered_args = dict(prompt.argument_defaults())
        rendered_args.update(arguments)

        # Render messages with literal substitution
        rendered_messages = []
        for msg in prompt.messages:
            rendered_text = self._render_text(msg.content.text, rendered_args)
            rendered_messages.append(
                {
                    "role": msg.role,
                    "content": {"type": "text", "text": rendered_text},
                }
            )

        return {
            "description": prompt.description,
            "messages": rendered_messages,
        }

    @staticmethod
    def _render_text(template: str, args: Dict[str, Any]) -> str:
        """Literal ``{{arg}}`` substitution.

        - Only substitutes placeholders for keys present in ``args``.
        - Unknown placeholders (not in args) are left as-is.
        - No HTML escaping, no recursive evaluation.
        - Values are converted to string via ``str()``.
        """

        def replacer(match: re.Match) -> str:
            key = match.group(1)
            if key in args:
                return str(args[key])
            return match.group(0)

        return _PLACEHOLDER_RE.sub(replacer, template)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def count(self) -> int:
        """Return the number of loaded prompts."""
        return len(self._prompts)

    def names(self) -> List[str]:
        """Return sorted list of prompt names."""
        return sorted(self._prompts.keys())

    def has_prompt(self, name: str) -> bool:
        """Check if a prompt exists by name."""
        return name in self._prompts
