"""Register YAML-backed prompts onto a FastMCP server.

This module bridges the local ``PromptCatalog`` (YAML-backed) to FastMCP's
prompt system. For each prompt in the catalog, it dynamically creates a
function with a proper ``inspect.Signature`` (so FastMCP can extract the
argument schema) and registers it via ``server.add_prompt()``.

The function body delegates to ``catalog.get_prompt(name, arguments)``,
which performs literal ``{{arg}}`` substitution and returns rendered messages.
"""

import inspect
from typing import Any, Callable, Dict, List, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts import Prompt

from .catalog import PromptCatalog


def _make_prompt_fn(
    catalog: PromptCatalog,
    prompt_name: str,
    arguments: List[Dict[str, Any]],
) -> Callable[..., List[Dict[str, Any]]]:
    """Create a function with a dynamic signature for a YAML prompt.

    The function's parameters are built from the prompt's argument
    definitions so FastMCP's ``func_metadata`` can extract them correctly.
    Required arguments have no default; optional arguments use their
    declared default.

    The function body calls ``catalog.get_prompt`` and returns the
    rendered messages as a list of dicts (FastMCP converts these to
    Message objects).
    """
    # Build inspect.Parameter objects for each argument
    params: List[inspect.Parameter] = []
    for arg in arguments:
        if arg.get("required", False):
            default = inspect.Parameter.empty
        else:
            default = arg.get("default")
        params.append(
            inspect.Parameter(
                arg["name"],
                kind=inspect.Parameter.KEYWORD_ONLY,
                default=default,
                annotation=str,
            )
        )

    # If no arguments, add a no-op **kwargs to avoid empty-signature edge cases
    # Actually, FastMCP handles zero-arg functions fine, so don't add kwargs.

    def render_fn(**kwargs: Any) -> List[Dict[str, Any]]:
        result = catalog.get_prompt(prompt_name, kwargs)
        return result["messages"]

    # Set the function name, signature, and annotations so pydantic's
    # validate_call (used by FastMCP's Prompt.from_function) can resolve
    # type hints for the synthetic parameters.
    render_fn.__name__ = prompt_name
    render_fn.__signature__ = inspect.Signature(parameters=params)  # type: ignore[misc]
    render_fn.__annotations__ = {p.name: str for p in params}
    render_fn.__doc__ = (
        catalog._prompts[prompt_name].description or ""
    )

    return render_fn


def register_prompts(
    server: FastMCP,
    catalog: Optional[PromptCatalog] = None,
    yaml_path: Optional[str] = None,
) -> int:
    """Register all prompts from the YAML catalog onto the FastMCP server.

    Args:
        server: The FastMCP server instance.
        catalog: An existing PromptCatalog. If None, loads from yaml_path
                 or the default path.
        yaml_path: Path to prompts_list.yaml. Ignored if catalog is provided.

    Returns:
        Number of prompts registered.

    Note:
        If the YAML file doesn't exist, this is a no-op (returns 0). The
        server starts normally without prompts advertised. This ensures
        the feature is opt-in and doesn't break existing deployments.
    """
    if catalog is None:
        try:
            catalog = PromptCatalog(yaml_path=yaml_path)
        except FileNotFoundError:
            # Prompts are optional — don't break the server if the file
            # doesn't exist.
            return 0

    count = 0
    for name in catalog.names():
        prompt_def = catalog._prompts[name]
        # Build argument metadata for the function signature
        arg_metadata = [
            {
                "name": arg.name,
                "required": arg.required,
                "default": arg.default,
            }
            for arg in prompt_def.arguments
        ]

        fn = _make_prompt_fn(catalog, name, arg_metadata)
        mcp_prompt = Prompt.from_function(
            fn,
            name=name,
            title=prompt_def.title,
            description=prompt_def.description,
        )
        server.add_prompt(mcp_prompt)
        count += 1

    return count
