"""
MCP tool discovery module for discovering tools from multiple MCP providers.

This module provides functionality to:
- Discover tools from MCP servers
- Normalize tool definitions to unified format
- Cache discovery results
- Support multiple providers (Alphavantage, Etrade, Google, Tradier, etc.)
- Load provider configurations from YAML file
"""

import httpx
import yaml
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum

from .security import append_api_key, contains_inline_credential, redact_url, resolve_secret


class MCPProvider(Enum):
    """MCP provider identifiers."""
    ALPHAVANTAGE = "alphavantage"
    ETRADE = "etrade"
    GOOGLE = "google"
    TRADIER = "tradier"


@dataclass
class MCPProviderAuth:
    """Authentication configuration for MCP provider."""
    type: str = "none"  # bearer, api_key, none
    secret_env: Optional[str] = None
    secret_value: Optional[str] = None
    key_param: str = "api_key"  # query-param name for api_key auth (e.g. tavilyApiKey)

    def __post_init__(self):
        if self.secret_value:
            raise ValueError(
                "MCP credentials must be supplied through secret_env, not secret_value."
            )


@dataclass
class MCPLimits:
    """Rate limiting and performance limits for MCP provider."""
    max_page_size: int = 100
    max_requests_per_minute: int = 60
    max_results: int = 100
    timeout_seconds: int = 10
    max_tools_with_params: Optional[int] = None


@dataclass
class MCPProviderFeatures:
    """Feature flags for MCP provider."""
    supports_streaming: bool = False


@dataclass
class MCPProviderConfig:
    """Configuration for an MCP provider loaded from YAML."""
    id: str
    name: str
    transport: str = "http"  # http, streamable-http, stdio
    endpoint: Optional[str] = None
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    auth: MCPProviderAuth = field(default_factory=MCPProviderAuth)
    enabled: bool = True
    limits: MCPLimits = field(default_factory=MCPLimits)
    features: MCPProviderFeatures = field(default_factory=MCPProviderFeatures)
    headers: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.auth, dict):
            self.auth = MCPProviderAuth(**self.auth)
        if isinstance(self.limits, dict):
            self.limits = MCPLimits(**self.limits)
        if isinstance(self.features, dict):
            self.features = MCPProviderFeatures(**self.features)
        if contains_inline_credential(self.endpoint, self.headers):
            raise ValueError(
                "MCP credentials must be supplied through auth.secret_env, not provider URLs or headers."
            )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPProviderConfig":
        """Create config from dictionary."""
        return cls(**data)


class MCPDiscovery:
    """MCP tool discovery for multiple providers."""
    
    def __init__(self, providers: List[MCPProviderConfig] = None, config_file: str = "source_files/mcp_providers.yaml"):
        """Initialize MCP discovery with provider configurations."""
        self.providers = providers or []
        self.config_file = config_file
        self.client = httpx.Client(timeout=30.0)
        
        # Load from config file if no providers provided
        if not self.providers and config_file:
            self.load_from_yaml(config_file)
    
    def load_from_yaml(self, config_file: str):
        """Load provider configurations from YAML file."""
        try:
            if not os.path.exists(config_file):
                print(f"Config file {config_file} not found, using empty provider list")
                return

            with open(config_file, 'r') as f:
                data = yaml.safe_load(f)

            if data and 'providers' in data:
                self.providers = [MCPProviderConfig.from_dict(p) for p in data['providers']]
                print(f"Loaded {len(self.providers)} providers from {config_file}")
                for p in self.providers:
                    print(f"  - {p.id}: {p.name} (enabled={p.enabled})")
            else:
                print(f"No providers found in {config_file}")
        except Exception as e:
            print(f"Error loading providers from {config_file}: {e}")
            import traceback
            traceback.print_exc()
    
    def save_to_yaml(self, config_file: str = None):
        """Save provider configurations to YAML file."""
        target_file = config_file or self.config_file
        try:
            data = {
                'providers': [
                    {
                        'id': p.id,
                        'name': p.name,
                        'transport': p.transport,
                        'endpoint': p.endpoint,
                        'command': p.command,
                        'args': p.args,
                        'auth': {
                            'type': p.auth.type,
                            'secret_env': p.auth.secret_env,
                            'key_param': p.auth.key_param,
                        },
                        'enabled': p.enabled,
                        'features': {
                            'supports_streaming': p.features.supports_streaming
                        },
                        'limits': {
                            'max_page_size': p.limits.max_page_size,
                            'max_requests_per_minute': p.limits.max_requests_per_minute,
                            'max_results': p.limits.max_results,
                            'timeout_seconds': p.limits.timeout_seconds
                        }
                    }
                    for p in self.providers
                ]
            }
            
            with open(target_file, 'w') as f:
                yaml.dump(data, f, default_flow_style=False)
            
            print(f"Saved {len(self.providers)} providers to {target_file}")
        except Exception as e:
            print(f"Error saving providers to {target_file}: {e}")
    
    def add_provider(self, config: MCPProviderConfig):
        """Add a provider configuration."""
        self.providers.append(config)
    
    def remove_provider(self, provider_id: str):
        """Remove a provider by ID."""
        self.providers = [p for p in self.providers if p.id != provider_id]
    
    def get_provider(self, provider_id: str) -> Optional[MCPProviderConfig]:
        """Get a provider by ID."""
        for p in self.providers:
            if p.id == provider_id:
                return p
        return None
    
    async def discover_all(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Discover tools from all enabled providers.

        Returns:
            Dictionary mapping provider IDs to their discovered tools
        """
        results = {}
        for provider in self.providers:
            if provider.enabled:
                results[provider.id] = await self.discover_from_config(provider)
        return results
    
    async def discover_from_config(self, config: MCPProviderConfig) -> List[Dict[str, Any]]:
        """
        Discover tools from a specific provider configuration.

        Args:
            config: MCP provider configuration

        Returns:
            List of discovered tools in unified format
        """
        try:
            # Use provider-specific adapter if available
            if config.id == "alphavantage_finance":
                from .alphavantage_adapter import AlphaVantageAdapter
                adapter = AlphaVantageAdapter(config)
                return await adapter.discover_tools()

            # Default transport-based discovery
            if config.transport == "http":
                return self._discover_http(config)
            elif config.transport == "streamable-http":
                return await self._discover_streamable_http(config)
            else:
                print(f"Transport {config.transport} not yet implemented")
                return []
        except Exception as e:
            print(f"Error discovering tools from {config.id}: {redact_url(str(e))}")
            return []
    
    def _discover_http(self, config: MCPProviderConfig) -> List[Dict[str, Any]]:
        """Discover tools using HTTP POST with JSON-RPC."""
        tools = []
        
        try:
            headers = self._auth_headers(config)
            
            # List tools
            payload = {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": 1
            }
            
            response = self.client.post(
                config.endpoint,
                json=payload,
                headers=headers,
                timeout=config.limits.timeout_seconds
            )
            
            if response.status_code != 200:
                print(f"HTTP error {response.status_code}: {response.text}")
                return []
            
            result = response.json()
            
            # Handle different response formats
            if "result" in result and "tools" in result["result"]:
                mcp_tools = result["result"]["tools"]
            elif "tools" in result:
                mcp_tools = result["tools"]
            else:
                print(f"Unexpected response format: {result}")
                return []
            
            # Normalize tools to unified format
            for mcp_tool in mcp_tools:
                normalized = self._normalize_tool(mcp_tool, config.id)
                if normalized:
                    tools.append(normalized)
            
            return tools
            
        except Exception as e:
            print(f"HTTP discovery error: {redact_url(str(e))}")
            return []
    
    async def _discover_streamable_http(self, config: MCPProviderConfig) -> List[Dict[str, Any]]:
        """Discover tools using streamable-http transport."""
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client, create_mcp_http_client

        tools = []

        try:
            # Resolve the backend-only environment secret once.
            secret = resolve_secret(config.auth.secret_env, config.id)

            # For api_key auth, append the key as a URL query parameter
            # (required by providers like Alpha Vantage that expect ?apikey=...).
            # The param name defaults to "api_key" but can be overridden via
            # auth.key_param (e.g. Tavily uses "tavilyApiKey").
            # For bearer auth, send the token in the Authorization header via a
            # custom httpx client, keeping it out of the URL and server logs.
            url = config.endpoint
            http_client = None
            if config.auth.type == "api_key" and secret:
                url = append_api_key(url, secret, config.auth.key_param)
            elif config.auth.type == "bearer" and secret:
                http_client = create_mcp_http_client(
                    headers={"Authorization": f"Bearer {secret}"}
                )

            print(f"Connecting to streamable-http endpoint: {redact_url(url)}")

            async with streamable_http_client(url, http_client=http_client) as streams:
                read, write = streams[:2]
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools_list = await session.list_tools()

                    # Normalize tools to unified format
                    for mcp_tool in tools_list.tools:
                        normalized = self._normalize_tool_from_mcp(mcp_tool, config.id)
                        if normalized:
                            tools.append(normalized)

            print(f"Discovered {len(tools)} tools via streamable-http")

        except Exception as e:
            print(f"Streamable-http discovery error: {redact_url(str(e))}")

        return tools

    def _normalize_tool_from_mcp(self, mcp_tool, provider_id: str) -> Optional[Dict[str, Any]]:
        """
        Normalize MCP tool object to unified discovery format.

        Args:
            mcp_tool: MCP tool object from ClientSession
            provider_id: Provider ID string

        Returns:
            Normalized tool in discovery format
        """
        try:
            # Extract basic info from MCP tool object
            tool_name = mcp_tool.name
            description = mcp_tool.description if hasattr(mcp_tool, 'description') else ""

            # Extract params from inputSchema
            params = {}
            if hasattr(mcp_tool, 'inputSchema') and mcp_tool.inputSchema:
                input_schema = mcp_tool.inputSchema
                if hasattr(input_schema, "model_dump"):
                    input_schema = input_schema.model_dump()
                if isinstance(input_schema, dict):
                    params = input_schema.get("properties", {})

            # Determine category based on tool name
            category = self._infer_category(tool_name, provider_id)

            return {
                "id": f"{provider_id}:{tool_name}",
                "title": tool_name,
                "description": description,
                "tool_name": tool_name,
                "params": params,
                "category": category,
                "provider": provider_id,
                "mcp_tool": mcp_tool  # Store original for reference
            }

        except Exception as e:
            print(f"Error normalizing tool: {e}")
            return None
    
    def _normalize_tool(self, mcp_tool: Dict[str, Any], provider_id: str) -> Optional[Dict[str, Any]]:
        """
        Normalize MCP tool to unified discovery format.
        
        Args:
            mcp_tool: Raw MCP tool definition
            provider_id: Provider ID string
            
        Returns:
            Normalized tool in discovery format
        """
        try:
            # Extract basic info
            tool_name = mcp_tool.get("name", "")
            description = mcp_tool.get("description", "")
            input_schema = mcp_tool.get("inputSchema", {})
            
            # Keep each parameter's complete JSON Schema definition.
            params = input_schema.get("properties", {})
            
            # Determine category based on tool name
            category = self._infer_category(tool_name, provider_id)
            
            return {
                "id": f"{provider_id}:{tool_name}",
                "title": tool_name,
                "description": description,
                "tool_name": tool_name,
                "params": params,
                "category": category,
                "provider": provider_id,
                "mcp_tool": mcp_tool  # Store original for reference
            }
            
        except Exception as e:
            print(f"Error normalizing tool: {e}")
            return None
    
    def _infer_category(self, tool_name: str, provider_id: str) -> str:
        """Infer tool category from name and provider."""
        name_lower = tool_name.lower()
        provider_lower = provider_id.lower()
        
        # Provider-specific categories
        if "alphavantage" in provider_lower:
            if "stock" in name_lower or "quote" in name_lower or "time_series" in name_lower:
                return "finance"
            elif "forex" in name_lower or "currency" in name_lower:
                return "finance"
            elif "crypto" in name_lower or "digital" in name_lower:
                return "finance"
            elif "news" in name_lower or "sentiment" in name_lower:
                return "news"
        
        # General categories
        if "stock" in name_lower or "price" in name_lower or "market" in name_lower:
            return "finance"
        elif "order" in name_lower or "trade" in name_lower or "buy" in name_lower or "sell" in name_lower:
            return "trading"
        elif "account" in name_lower or "portfolio" in name_lower or "balance" in name_lower:
            return "account"
        elif "news" in name_lower or "alert" in name_lower:
            return "news"
        
        return "general"
    
    def get_tool_schema(self, provider_id: str, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed schema for a specific tool.

        Args:
            provider_id: Provider ID string
            tool_name: Tool name

        Returns:
            Tool schema or None if not found
        """
        provider_config = self.get_provider(provider_id)
        if not provider_config:
            return None

        try:
            # Use TOOL_GET if available (Alpha Vantage pattern)
            payload = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "TOOL_GET",
                    "arguments": {"tool_name": tool_name}
                },
                "id": 1
            }

            headers = self._auth_headers(provider_config)

            response = self.client.post(
                provider_config.endpoint,
                json=payload,
                headers=headers,
                timeout=provider_config.limits.timeout_seconds
            )

            if response.status_code == 200:
                result = response.json()
                if "result" in result:
                    return result["result"]

            return None

        except Exception as e:
            print(f"Error getting tool schema: {redact_url(str(e))}")
            return None
    
    def close(self):
        """Close HTTP client."""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


    def _auth_headers(self, config: MCPProviderConfig) -> Dict[str, str]:
        """Build outbound auth headers using a backend-only environment secret."""
        headers = {"Content-Type": "application/json", **config.headers}
        secret = resolve_secret(config.auth.secret_env, config.id)
        if not secret:
            return headers
        if config.auth.type == "bearer":
            headers["Authorization"] = f"Bearer {secret}"
        elif config.auth.type == "api_key":
            headers["X-API-Key"] = secret
        return headers


def create_alphavantage_discovery(
    api_key_env: str = "ALPHAVANTAGE_API_KEY",
) -> MCPDiscovery:
    """Create Alpha Vantage discovery that resolves its key in the backend."""
    config = MCPProviderConfig(
        id="alphavantage_finance",
        name="Alpha Vantage MCP",
        transport="http",
        endpoint="https://mcp.alphavantage.co/mcp",
        auth=MCPProviderAuth(type="api_key", secret_env=api_key_env),
        enabled=True
    )

    discovery = MCPDiscovery([config])
    return discovery
