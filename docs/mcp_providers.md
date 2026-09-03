---
title: "Providers Guide | Axiolex"
description: "Configure, manage, and discover tools from MCP and A2A providers in Axiolex."
---

# Providers Guide

This guide explains how to configure MCP and A2A providers for Axiolex and how to discover their tools into the searchable tool catalog.

Providers are external capability sources — MCP servers (Model Context Protocol) or A2A agents (Agent-to-Agent). Axiolex stores provider connection details in `source_files/mcp_providers.yaml`, discovers tools/skills from enabled providers, normalizes them, and caches searchable discovery/runtime metadata for retrieval and execution workflows. The caller never needs to know which protocol backs a tool — Axiolex resolves the transport, endpoint, and credentials server-side and returns a normalized result.

## Overview

The provider flow is:

```text
mcp_providers.yaml
  -> MCPDiscovery
  -> provider tools/list discovery
  -> normalized tool metadata
  -> Redis discovery/runtime cache
  -> BM25S retrieval and MCP tool routing
```

Use this page when you want to:

- **Add providers**: Register a new MCP server endpoint.
- **Manage credentials**: Reference API keys or bearer tokens through environment variables.
- **Discover tools**: Pull tool definitions from an enabled provider.
- **Disable providers**: Stop a provider and invalidate cached tools for it.

## Provider Configuration File

By default, AxioLex reads providers from:

```text
source_files/mcp_providers.yaml
```

A provider entry looks like this:

```yaml
providers:
  - id: alphavantage_finance
    name: Alpha Vantage MCP
    transport: streamable-http
    endpoint: https://mcp.alphavantage.co/mcp
    command: null
    args: []
    auth:
      type: api_key
      secret_env: ALPHAVANTAGE_API_KEY
      secret_value: null
    enabled: true
    features:
      supports_streaming: true
    limits:
      max_page_size: 15
      max_requests_per_minute: 60
      max_results: 100
      timeout_seconds: 10
```

## Configuration Fields

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Stable unique provider identifier. Used in API routes, cache keys, and normalized tool IDs. |
| `name` | Yes | Human-readable provider name shown in the UI. |
| `transport` | Yes | Provider transport. Supported: `streamable-http`, `stdio`, `a2a`. |
| `endpoint` | For HTTP transports | MCP server endpoint URL. |
| `command` | For stdio-style configs | Command name if a provider is represented by a local process. |
| `args` | No | Command arguments for process-based providers. |
| `auth.type` | No | Authentication mode: `none`, `api_key`, `bearer`, or `basic`. |
| `auth.secret_env` | For authenticated providers | Environment variable that contains the secret. |
| `auth.username` | For `basic` auth | Non-secret username/account identifier (e.g. Jira email). Stored in YAML as plaintext. |
| `auth.key_param` | No | Query-parameter name for `api_key` auth. Defaults to `api_key`. |
| `enabled` | No | Whether the provider participates in discovery. |
| `features.supports_streaming` | No | Indicates whether the provider supports streaming behavior. |
| `limits.max_page_size` | No | Provider-specific page size limit for discovery/adapters. |
| `limits.max_requests_per_minute` | No | Rate limit metadata for provider calls. |
| `limits.max_results` | No | Maximum result count metadata. |
| `limits.timeout_seconds` | No | Timeout metadata for provider operations. |

## Authentication

For providers that need credentials, store the secret in an environment variable and reference that variable with `auth.secret_env`.

```bash
export ALPHAVANTAGE_API_KEY="your-api-key"
```

```yaml
auth:
  type: api_key
  secret_env: ALPHAVANTAGE_API_KEY
```

For bearer-token providers:

```yaml
auth:
  type: bearer
  secret_env: CUSTOM_MCP_TOKEN
```

For basic auth providers (e.g. Jira) that need a username + token pair:

```yaml
auth:
  type: basic
  username: your-email@domain.com
  secret_env: JIRA_API_TOKEN
```

The `username` is a non-secret identifier stored in the YAML. The token is
stored encrypted in the secret store (or via the environment variable). For
stdio providers, both are passed to the subprocess as environment variables:
`{SECRET_ENV}` (the token) and `{SECRET_ENV}_USERNAME` (the email).

For unauthenticated providers:

```yaml
auth:
  type: none
  secret_env: null
```

AXIOLEX rejects inline credentials in `auth.secret_value`, provider URL query
parameters, and static authorization headers. The backend resolves the value
only from `auth.secret_env` at request time; the UI and provider YAML receive
only the environment-variable name. Credential-bearing URLs are redacted in
discovery logs.

## Add a Provider in YAML

Add a new provider under `providers`:

```yaml
providers:
  - id: local_markets
    name: Local Markets MCP
    transport: streamable-http
    endpoint: http://localhost:9001/mcp
    command: null
    args: []
    auth:
      type: none
      secret_env: null
      secret_value: null
    enabled: true
    features:
      supports_streaming: false
    limits:
      max_page_size: 50
      max_requests_per_minute: 60
      max_results: 100
      timeout_seconds: 10
```

After editing the YAML file, discover tools from the provider through the UI or REST API.

### A2A provider example

A2A agents expose skills via an agent card. Axiolex fetches the card at `{endpoint}/.well-known/agent-card.json` and maps each skill to a catalog tool.

```yaml
providers:
  - id: veris_finance_a2a
    name: Veris Finance Research (A2A)
    transport: a2a
    endpoint: http://localhost:8100/agents/veris-finance-research-agent/
    command: null
    args: []
    auth:
      type: none
      secret_env: null
    enabled: true
    namespaces:
      - veris.research
```

A2A execution is synchronous — Axiolex sends a `SendMessage` request and waits for the result within the configured timeout. The caller sees the same normalized response as an MCP tool.

## Manage Providers Through the Web UI

Start the Axiolex service and open the web interface. In the MCP and A2A Providers tab you can:

- **View providers**: Load all configured providers (MCP and A2A).
- **Add providers**: Submit a provider configuration through the form.
- **Edit providers**: Update connection details, auth settings, limits, and enabled state.
- **Discover tools**: Trigger provider discovery and cache discovered tools.
- **Disable providers**: Disable a provider and clear its cached tools when Redis is connected.

## Manage Providers Through the REST API

### List Providers

```bash
curl -X GET http://localhost:9200/mcp-providers
```

### Add a Provider

```bash
curl -X POST http://localhost:9200/mcp-providers \
  -H "Content-Type: application/json" \
  -d '{
    "id": "local_markets",
    "name": "Local Markets MCP",
    "transport": "streamable-http",
    "endpoint": "http://localhost:9001/mcp",
    "command": null,
    "args": [],
    "auth": {
      "type": "none",
      "secret_env": null,
      "secret_value": null
    },
    "enabled": true,
    "features": {
      "supports_streaming": false
    },
    "limits": {
      "max_page_size": 50,
      "max_requests_per_minute": 60,
      "max_results": 100,
      "timeout_seconds": 10
    }
  }'
```

### Update a Provider

```bash
curl -X PUT http://localhost:9200/mcp-providers/local_markets \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Local Markets MCP",
    "transport": "streamable-http",
    "endpoint": "http://localhost:9001/mcp",
    "command": null,
    "args": [],
    "auth": {
      "type": "none",
      "secret_env": null,
      "secret_value": null
    },
    "enabled": true,
    "features": {
      "supports_streaming": false
    },
    "limits": {
      "max_page_size": 50,
      "max_requests_per_minute": 60,
      "max_results": 100,
      "timeout_seconds": 10
    }
  }'
```

### Disable a Provider

```bash
curl -X DELETE http://localhost:9200/mcp-providers/local_markets
```

This sets `enabled` to `false`. If Redis is connected, AxioLex also invalidates cached tools for that provider and reloads the retriever index.

### Discover Provider Tools

```bash
curl -X GET http://localhost:9200/mcp-providers/local_markets/discover
```

A successful response includes the normalized tool list and count:

```json
{
  "success": true,
  "provider_id": "local_markets",
  "tools": [],
  "count": 0
}
```

## Discovery and Caching

When discovery succeeds, AxioLex separates tool data into two cache shapes:

- **Discovery data**: Searchable fields such as `id`, `title`, `description`, `tool_name`, `params`, `category`, and `provider`.
- **Runtime data**: Execution details such as `tool_name`, `params`, `transport`, `endpoint`, provider ID, and auth metadata.

This separation lets the MCP server retrieve and rank tools without mixing search text with runtime connection details.

## Alpha Vantage Provider

The `alphavantage_finance` provider has a provider-specific adapter. Use `ALPHAVANTAGE_API_KEY` for authentication:

```bash
export ALPHAVANTAGE_API_KEY="your-alpha-vantage-key"
```

Example configuration:

```yaml
- id: alphavantage_finance
  name: Alpha Vantage MCP
  transport: streamable-http
  endpoint: https://mcp.alphavantage.co/mcp
  command: null
  args: []
  auth:
    type: api_key
    secret_env: ALPHAVANTAGE_API_KEY
    secret_value: null
  enabled: true
  features:
    supports_streaming: true
  limits:
    max_page_size: 15
    max_requests_per_minute: 60
    max_results: 100
    timeout_seconds: 10
```

## Troubleshooting

- **Provider not listed**: Confirm the provider is under the top-level `providers` key in `source_files/mcp_providers.yaml`.
- **Discovery returns no tools**: Verify the endpoint URL, transport, credentials, and that the remote MCP server is reachable.
- **Authentication errors**: Confirm the environment variable named by `auth.secret_env` is set before starting AxioLex.
- **Disabled provider cannot discover**: Set `enabled: true` or update the provider through the API/UI.
- **Cached tools remain after disabling**: Check that Redis is connected so provider cache invalidation can run.
- **Unexpected tool routing results**: Re-run discovery, then rebuild or reload the relevant tool index so new cache contents are searchable.

## Related Pages

- [Document and Tool Ingestion Guide](./document-and-tool-ingestion-guide.html)
- [API Reference](./api-reference.html)
- [Architecture](./architecture.html)
