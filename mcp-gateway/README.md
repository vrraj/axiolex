# @axiolex/mcp-gateway

A tiny stdio-to-HTTP proxy that connects Claude Desktop (and other stdio-only MCP clients) to a remote [Axiolex](https://github.com/vrraj/axiolex) server.

## Why

Claude Desktop and some MCP clients only support the `stdio` transport — they spawn a local subprocess and communicate over stdin/stdout. Axiolex serves MCP over HTTP at `/mcp` on the API server (port 9700). This proxy bridges the two: it speaks stdio to Claude and HTTP to Axiolex.

The proxy is **~120 lines of JavaScript** with one dependency (`@modelcontextprotocol/sdk`). No Python, no Redis, no ML libraries. IT can audit the entire source in 2 minutes.

## Install

No install needed — `npx` fetches and caches the package automatically:

```json
{
  "mcpServers": {
    "axiolex": {
      "command": "npx",
      "args": ["-y", "@axiolex/mcp-gateway", "--endpoint", "http://localhost:9700/mcp"]
    }
  }
}
```

Or install globally:

```bash
npm install -g @axiolex/mcp-gateway
```

## Claude Desktop config

```json
{
  "mcpServers": {
    "axiolex": {
      "command": "npx",
      "args": [
        "-y",
        "@axiolex/mcp-gateway",
        "--endpoint", "http://localhost:9700/mcp"
      ]
    }
  }
}
```

For a remote Axiolex server:

```json
{
  "mcpServers": {
    "axiolex": {
      "command": "npx",
      "args": [
        "-y",
        "@axiolex/mcp-gateway",
        "--endpoint", "https://axiolex.your-company.com:9700/mcp"
      ]
    }
  }
}
```

## Options

| Option | Env var | Default | Description |
|---|---|---|---|
| `--endpoint, -e` | `AXIOLEX_URL` | `http://localhost:9700/mcp` | Axiolex MCP HTTP endpoint |
| `--help, -h` | | | Show help |

## How it works

```
Claude Desktop
  └── spawns: npx @axiolex/mcp-gateway --endpoint http://localhost:9700/mcp
        ├── stdio server (stdin/stdout)  ← Claude sends JSON-RPC here
        ├── HTTP client (fetch)          → forwards to localhost:9700/mcp
        └── returns response via stdout  ← Claude receives result
```

The proxy connects to the Axiolex server on startup (MCP `initialize` handshake), then forwards `tools/list` and `tools/call` requests. All retrieval, ranking, and execution happens server-side — the proxy is just a pipe.

## Requirements

- Node.js 18+ (pre-installed on most developer machines)
- An Axiolex server running and reachable at the configured endpoint

## License

MIT
