"""Tests for MCP Prompts Phase 1 (local YAML catalog).

Covers:
  - Catalog loading from YAML
  - Duplicate prompt name rejection
  - list_prompts (pagination, metadata without template bodies)
  - get_prompt (rendering, defaults, required arg validation)
  - Unknown prompt name errors
  - Literal substitution (no HTML escaping, no recursion)
  - Empty/missing YAML file handling
  - register_prompts wiring onto FastMCP server
"""

import inspect
import textwrap

import pytest
import yaml

from axiolex.mcp.prompts import PromptCatalog, register_prompts
from axiolex.mcp.prompts.models import PromptDefinition, PromptMessage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_yaml(tmp_path, data):
    """Write a dict to prompts_list.yaml in tmp_path."""
    path = tmp_path / "prompts_list.yaml"
    path.write_text(yaml.dump(data, default_flow_style=False))
    return str(path)


def _sample_prompts():
    """Return a minimal valid prompts dict for tests."""
    return {
        "prompts": [
            {
                "name": "greet",
                "title": "Greet User",
                "description": "Greets the user by name.",
                "arguments": [
                    {"name": "name", "description": "User name", "required": True},
                    {"name": "tone", "description": "Greeting tone", "required": False, "default": "friendly"},
                ],
                "messages": [
                    {
                        "role": "user",
                        "content": {"type": "text", "text": "Say {{tone}} hello to {{name}}."},
                    }
                ],
            },
            {
                "name": "no_args",
                "title": "No Arguments",
                "description": "A prompt with no arguments.",
                "arguments": [],
                "messages": [
                    {
                        "role": "user",
                        "content": {"type": "text", "text": "Hello, world."},
                    }
                ],
            },
        ]
    }


# ---------------------------------------------------------------------------
# Catalog loading
# ---------------------------------------------------------------------------

class TestCatalogLoading:
    def test_loads_prompts_from_yaml(self, tmp_path):
        path = _write_yaml(tmp_path, _sample_prompts())
        catalog = PromptCatalog(yaml_path=path)
        assert catalog.count() == 2
        assert "greet" in catalog.names()
        assert "no_args" in catalog.names()

    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="not found"):
            PromptCatalog(yaml_path=str(tmp_path / "nonexistent.yaml"))

    def test_empty_yaml_file_loads_zero_prompts(self, tmp_path):
        path = tmp_path / "prompts_list.yaml"
        path.write_text("")
        catalog = PromptCatalog(yaml_path=str(path))
        assert catalog.count() == 0

    def test_empty_prompts_list_loads_zero(self, tmp_path):
        path = _write_yaml(tmp_path, {"prompts": []})
        catalog = PromptCatalog(yaml_path=path)
        assert catalog.count() == 0

    def test_duplicate_prompt_names_rejected(self, tmp_path):
        data = {
            "prompts": [
                {
                    "name": "dup",
                    "title": "First",
                    "arguments": [],
                    "messages": [{"role": "user", "content": {"type": "text", "text": "a"}}],
                },
                {
                    "name": "dup",
                    "title": "Second",
                    "arguments": [],
                    "messages": [{"role": "user", "content": {"type": "text", "text": "b"}}],
                },
            ]
        }
        path = _write_yaml(tmp_path, data)
        with pytest.raises(ValueError, match="Duplicate prompt name 'dup'"):
            PromptCatalog(yaml_path=path)

    def test_invalid_prompt_definition_rejected(self, tmp_path):
        data = {
            "prompts": [
                {
                    "name": "bad",
                    "arguments": [],
                    "messages": [
                        {"role": "user", "content": {"type": "image", "data": "abc"}},
                    ],
                }
            ]
        }
        # Non-text content type is rejected in Phase 1
        path = _write_yaml(tmp_path, data)
        with pytest.raises(ValueError, match="Invalid prompt definition"):
            PromptCatalog(yaml_path=path)


# ---------------------------------------------------------------------------
# list_prompts
# ---------------------------------------------------------------------------

class TestListPrompts:
    def test_returns_metadata_without_template_bodies(self, tmp_path):
        path = _write_yaml(tmp_path, _sample_prompts())
        catalog = PromptCatalog(yaml_path=path)
        result = catalog.list_prompts()

        assert "prompts" in result
        assert len(result["prompts"]) == 2
        # Names should be sorted
        assert result["prompts"][0]["name"] == "greet"
        assert result["prompts"][1]["name"] == "no_args"

        # Each entry should have name, title, description, arguments
        greet = result["prompts"][0]
        assert greet["title"] == "Greet User"
        assert greet["description"] == "Greets the user by name."
        assert len(greet["arguments"]) == 2
        assert greet["arguments"][0]["name"] == "name"
        assert greet["arguments"][0]["required"] is True
        assert greet["arguments"][1]["name"] == "tone"
        assert greet["arguments"][1]["required"] is False

    def test_template_bodies_not_in_list(self, tmp_path):
        path = _write_yaml(tmp_path, _sample_prompts())
        catalog = PromptCatalog(yaml_path=path)
        result = catalog.list_prompts()
        # list_prompts should NOT include message templates
        for p in result["prompts"]:
            assert "messages" not in p

    def test_pagination_with_cursor(self, tmp_path):
        path = _write_yaml(tmp_path, _sample_prompts())
        catalog = PromptCatalog(yaml_path=path)

        # Page 1: limit=1
        page1 = catalog.list_prompts(limit=1)
        assert len(page1["prompts"]) == 1
        assert page1["prompts"][0]["name"] == "greet"
        assert page1["nextCursor"] is not None

        # Page 2: use cursor
        page2 = catalog.list_prompts(cursor=page1["nextCursor"], limit=1)
        assert len(page2["prompts"]) == 1
        assert page2["prompts"][0]["name"] == "no_args"
        assert page2["nextCursor"] is None

    def test_default_limit_is_50(self, tmp_path):
        path = _write_yaml(tmp_path, _sample_prompts())
        catalog = PromptCatalog(yaml_path=path)
        result = catalog.list_prompts()
        # With only 2 prompts, all fit in default limit
        assert len(result["prompts"]) == 2
        assert result["nextCursor"] is None


# ---------------------------------------------------------------------------
# get_prompt (rendering)
# ---------------------------------------------------------------------------

class TestGetPrompt:
    def test_renders_required_and_optional_args(self, tmp_path):
        path = _write_yaml(tmp_path, _sample_prompts())
        catalog = PromptCatalog(yaml_path=path)
        result = catalog.get_prompt("greet", {"name": "Alice"})

        assert result["description"] == "Greets the user by name."
        assert len(result["messages"]) == 1
        msg = result["messages"][0]
        assert msg["role"] == "user"
        assert msg["content"]["type"] == "text"
        # Default "friendly" should be applied
        assert "Say friendly hello to Alice." in msg["content"]["text"]

    def test_overrides_default(self, tmp_path):
        path = _write_yaml(tmp_path, _sample_prompts())
        catalog = PromptCatalog(yaml_path=path)
        result = catalog.get_prompt("greet", {"name": "Bob", "tone": "formal"})
        assert "Say formal hello to Bob." in result["messages"][0]["content"]["text"]

    def test_no_args_prompt(self, tmp_path):
        path = _write_yaml(tmp_path, _sample_prompts())
        catalog = PromptCatalog(yaml_path=path)
        result = catalog.get_prompt("no_args")
        assert len(result["messages"]) == 1
        assert result["messages"][0]["content"]["text"] == "Hello, world."

    def test_unknown_prompt_raises(self, tmp_path):
        path = _write_yaml(tmp_path, _sample_prompts())
        catalog = PromptCatalog(yaml_path=path)
        with pytest.raises(ValueError, match="Unknown prompt: 'nonexistent'"):
            catalog.get_prompt("nonexistent")

    def test_missing_required_arg_raises(self, tmp_path):
        path = _write_yaml(tmp_path, _sample_prompts())
        catalog = PromptCatalog(yaml_path=path)
        with pytest.raises(ValueError, match="Missing required argument"):
            catalog.get_prompt("greet", {})

    def test_literal_substitution_no_html_escaping(self, tmp_path):
        data = {
            "prompts": [
                {
                    "name": "raw",
                    "title": "Raw",
                    "arguments": [
                        {"name": "text", "required": True},
                    ],
                    "messages": [
                        {
                            "role": "user",
                            "content": {"type": "text", "text": "Content: {{text}}"},
                        }
                    ],
                }
            ]
        }
        path = _write_yaml(tmp_path, data)
        catalog = PromptCatalog(yaml_path=path)
        result = catalog.get_prompt("raw", {"text": "<script>alert('xss')</script>"})
        # Should NOT be HTML-escaped
        assert "<script>alert('xss')</script>" in result["messages"][0]["content"]["text"]

    def test_no_recursive_template_evaluation(self, tmp_path):
        data = {
            "prompts": [
                {
                    "name": "recursive",
                    "title": "Recursive",
                    "arguments": [
                        {"name": "a", "required": True},
                    ],
                    "messages": [
                        {
                            "role": "user",
                            "content": {"type": "text", "text": "{{a}}"},
                        }
                    ],
                }
            ]
        }
        path = _write_yaml(tmp_path, data)
        catalog = PromptCatalog(yaml_path=path)
        # If a's value contains a {{b}} placeholder, it should NOT be evaluated
        result = catalog.get_prompt("recursive", {"a": "{{b}}"})
        assert result["messages"][0]["content"]["text"] == "{{b}}"

    def test_unknown_placeholder_left_as_is(self, tmp_path):
        data = {
            "prompts": [
                {
                    "name": "unknown_ph",
                    "title": "Unknown Placeholder",
                    "arguments": [
                        {"name": "known", "required": True},
                    ],
                    "messages": [
                        {
                            "role": "user",
                            "content": {"type": "text", "text": "{{known}} and {{unknown}}"},
                        }
                    ],
                }
            ]
        }
        path = _write_yaml(tmp_path, data)
        catalog = PromptCatalog(yaml_path=path)
        result = catalog.get_prompt("unknown_ph", {"known": "yes"})
        text = result["messages"][0]["content"]["text"]
        assert "yes" in text
        assert "{{unknown}}" in text  # left as-is

    def test_multiple_messages(self, tmp_path):
        data = {
            "prompts": [
                {
                    "name": "multi",
                    "title": "Multi",
                    "arguments": [
                        {"name": "topic", "required": True},
                    ],
                    "messages": [
                        {
                            "role": "user",
                            "content": {"type": "text", "text": "Research {{topic}}."},
                        },
                        {
                            "role": "assistant",
                            "content": {"type": "text", "text": "I'll research {{topic}}."},
                        },
                    ],
                }
            ]
        }
        path = _write_yaml(tmp_path, data)
        catalog = PromptCatalog(yaml_path=path)
        result = catalog.get_prompt("multi", {"topic": "AI"})
        assert len(result["messages"]) == 2
        assert result["messages"][0]["role"] == "user"
        assert result["messages"][1]["role"] == "assistant"
        assert "Research AI." in result["messages"][0]["content"]["text"]
        assert "I'll research AI." in result["messages"][1]["content"]["text"]


# ---------------------------------------------------------------------------
# Model validation
# ---------------------------------------------------------------------------

class TestModelValidation:
    def test_invalid_role_rejected(self):
        with pytest.raises(Exception):
            PromptMessage.model_validate({
                "role": "system",
                "content": {"type": "text", "text": "hi"},
            })

    def test_non_text_content_rejected(self):
        with pytest.raises(Exception):
            PromptMessage.model_validate({
                "role": "user",
                "content": {"type": "image", "data": "abc", "mimeType": "image/png"},
            })

    def test_prompt_definition_requires_messages(self):
        with pytest.raises(Exception):
            PromptDefinition.model_validate({"name": "test", "arguments": []})


# ---------------------------------------------------------------------------
# register_prompts (FastMCP wiring)
# ---------------------------------------------------------------------------

class TestRegisterPrompts:
    @pytest.mark.asyncio
    async def test_registers_prompts_onto_server(self, tmp_path):
        from mcp.server.fastmcp import FastMCP

        path = _write_yaml(tmp_path, _sample_prompts())
        server = FastMCP("test")
        count = register_prompts(server, yaml_path=path)
        assert count == 2

        # The server should now have 2 prompts
        prompts = await server.list_prompts()
        assert len(prompts) == 2

    @pytest.mark.asyncio
    async def test_no_op_when_file_missing(self, tmp_path):
        from mcp.server.fastmcp import FastMCP

        server = FastMCP("test")
        count = register_prompts(server, yaml_path=str(tmp_path / "nonexistent.yaml"))
        assert count == 0
        prompts = await server.list_prompts()
        assert len(prompts) == 0

    @pytest.mark.asyncio
    async def test_registered_prompt_has_correct_arguments(self, tmp_path):
        from mcp.server.fastmcp import FastMCP

        path = _write_yaml(tmp_path, _sample_prompts())
        server = FastMCP("test")
        register_prompts(server, yaml_path=path)

        prompts = await server.list_prompts()
        greet = next(p for p in prompts if p.name == "greet")
        assert greet.title == "Greet User"
        assert greet.description == "Greets the user by name."
        assert len(greet.arguments) == 2
        # Check required flag
        arg_names = {a.name: a.required for a in greet.arguments}
        assert arg_names["name"] is True
        assert arg_names["tone"] is False

    @pytest.mark.asyncio
    async def test_registered_prompt_renders_correctly(self, tmp_path):
        from mcp.server.fastmcp import FastMCP

        path = _write_yaml(tmp_path, _sample_prompts())
        server = FastMCP("test")
        register_prompts(server, yaml_path=path)

        # Render via the prompt manager (used by the MCP protocol handler)
        messages = await server._prompt_manager.render_prompt("greet", {"name": "Alice"})
        assert len(messages) == 1
        assert "Say friendly hello to Alice." in messages[0].content.text

    @pytest.mark.asyncio
    async def test_registered_prompt_validates_required_args(self, tmp_path):
        from mcp.server.fastmcp import FastMCP

        path = _write_yaml(tmp_path, _sample_prompts())
        server = FastMCP("test")
        register_prompts(server, yaml_path=path)

        with pytest.raises(ValueError, match="Missing required arguments"):
            await server._prompt_manager.render_prompt("greet", {})
