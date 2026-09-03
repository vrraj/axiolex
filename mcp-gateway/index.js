#!/usr/bin/env node

/**
 * @axiolex/mcp-gateway — Stdio-to-HTTP proxy for Axiolex MCP.
 *
 * Connects Claude Desktop (and other stdio-only MCP clients) to a remote
 * Axiolex server that exposes the MCP streamable-http endpoint at /mcp.
 *
 * The proxy is stateless: it forwards tools/list and tools/call requests
 * to the upstream HTTP server and returns the responses. No Redis, no
 * BM25S, no ColBERT — just stdio <-> HTTP translation.
 *
 * Usage:
 *   axiolex-mcp-gateway --endpoint http://localhost:9700/mcp
 *
 * Claude Desktop config:
 *   "axiolex": {
 *     "command": "npx",
 *     "args": ["-y", "@axiolex/mcp-gateway", "--endpoint", "http://localhost:9700/mcp"]
 *   }
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";

// --- Parse CLI args ---------------------------------------------------------

function parseArgs() {
  const args = process.argv.slice(2);
  let endpoint = process.env.AXIOLEX_URL || "http://localhost:9700/mcp";

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--endpoint" || args[i] === "-e") {
      endpoint = args[i + 1];
      i++;
    } else if (args[i] === "--help" || args[i] === "-h") {
      console.error(`Usage: axiolex-mcp-gateway --endpoint <url>

Options:
  --endpoint, -e   Axiolex MCP HTTP endpoint (default: http://localhost:9700/mcp)
                   Can also be set via AXIOLEX_URL env var.
  --help, -h       Show this help message.

Claude Desktop config example:
  {
    "mcpServers": {
      "axiolex": {
        "command": "npx",
        "args": ["-y", "@axiolex/mcp-gateway", "--endpoint", "http://localhost:9700/mcp"]
      }
    }
  }
`);
      process.exit(0);
    }
  }

  return { endpoint };
}

// --- Main -------------------------------------------------------------------

async function main() {
  const { endpoint } = parseArgs();

  // Connect to the upstream Axiolex MCP server via streamable HTTP.
  // The Client handles the initialize handshake and session management.
  const client = new Client({
    name: "axiolex-mcp-gateway",
    version: "0.1.0",
  });

  const clientTransport = new StreamableHTTPClientTransport(new URL(endpoint));

  try {
    await client.connect(clientTransport);
  } catch (err) {
    console.error(`[axiolex-gateway] Failed to connect to ${endpoint}: ${err.message}`);
    console.error(`[axiolex-gateway] Make sure the Axiolex server is running.`);
    process.exit(1);
  }

  // Create the stdio server that Claude Desktop connects to.
  const server = new Server(
    { name: "axiolex", version: "0.1.0" },
    {
      capabilities: {
        tools: { listChanged: false },
      },
    },
  );

  // Proxy tools/list — forward to upstream and return the result.
  server.setRequestHandler(ListToolsRequestSchema, async () => {
    const result = await client.listTools();
    return result;
  });

  // Proxy tools/call — forward the tool name and arguments to upstream.
  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const result = await client.callTool(request.params);
    return result;
  });

  // Start listening on stdio.
  const transport = new StdioServerTransport();
  await server.connect(transport);

  // Log to stderr (stdout is reserved for MCP protocol).
  console.error(`[axiolex-gateway] Connected to ${endpoint}`);
  console.error(`[axiolex-gateway] Proxying stdio <-> HTTP for Claude Desktop`);
}

main().catch((err) => {
  console.error(`[axiolex-gateway] Fatal error: ${err.message}`);
  process.exit(1);
});
