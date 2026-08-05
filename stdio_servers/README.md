# stdio_servers/

Custom stdio MCP server scripts for Axiolex.

Each subfolder contains a standalone MCP server that Axiolex can discover tools
from via the stdio transport (subprocess communicating over stdin/stdout).

## How it works

1. Axiolex spawns the server as a subprocess using the `command` and `args`
   from `mcp_providers.yaml`.
2. The MCP SDK handles communication over stdin/stdout.
3. Axiolex calls `tools/list` to discover available tools.
4. The subprocess is terminated when discovery completes.

## Writing a custom server

Create a new subfolder and a `server.py` file:

```
stdio_servers/
  my_tools/
    server.py
```

Minimal template:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("my-tools")

@mcp.tool()
def my_tool(param: str) -> str:
    """Description of what the tool does."""
    return f"Result for {param}"

if __name__ == "__main__":
    mcp.run()
```

## Registering in Axiolex

Add an entry to `source_files/mcp_providers.yaml`:

```yaml
- id: my_tools
  name: My Tools
  transport: stdio
  command: python
  args: ["stdio_servers/my_tools/server.py"]
  auth:
    type: none
  enabled: true
```

Or add it from the UI:
- Transport: Stdio
- Command: `python`
- Args: `stdio_servers/my_tools/server.py`
- Auth Type: None

## Using pre-built servers

Pre-built MCP servers from PyPI or npm can be used directly without writing
any code. They are auto-downloaded by `uvx` or `npx` on first run.

### Fetch (web page fetching)

```yaml
- id: mcp_fetch
  name: Fetch Server
  transport: stdio
  command: uvx
  args: ["mcp-server-fetch"]
  auth:
    type: none
  enabled: true
```

### Time (timezone conversion)

```yaml
- id: mcp_time
  name: Time Server
  transport: stdio
  command: uvx
  args: ["mcp-server-time"]
  auth:
    type: none
  enabled: true
```

### Sequential Thinking (structured reasoning)

```yaml
- id: mcp_sequential_thinking
  name: Sequential Thinking
  transport: stdio
  command: npx
  args: ["-y", "@modelcontextprotocol/server-sequentialthinking"]
  auth:
    type: none
  enabled: true
```

## Prerequisites

- `python` must be on the PATH for custom Python servers.
- `uvx` (bundled with `uv`) must be on the PATH for PyPI-based pre-built servers.
- `npx` (bundled with Node.js) must be on the PATH for npm-based pre-built servers.

## Existing examples

- `text_tools/server.py` — word count, slug generator, keyword extraction, text truncation
