"""MCP server exposing Axiolex tool discovery."""

import argparse
import os
from typing import Annotated, Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, Field

from ..core.cache import RedisConfig
from ..core.retriever import BM25SRetriever, get_tool_discovery_retriever
from ..services.tool_discovery_service import ToolDiscoveryService


DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 9701
DEFAULT_PATH = "/mcp"
DEFAULT_REDIS_HOST = "localhost"
DEFAULT_REDIS_PORT = 6380
DEFAULT_REDIS_DB = 0


class DiscoveredTool(BaseModel):
    """Execution-ready downstream tool definition."""

    name: str
    description: str
    params: Dict[str, Any]
    inputSchema: Dict[str, Any]
    endpoint: Any = None
    transport: Optional[str] = None
    provider: Optional[str] = None
    bm25_score: Optional[float] = None
    softmax_score: Optional[float] = None
    bm25_rank: Optional[int] = None
    bm25_softmax_score: Optional[float] = None
    colbert_score: Optional[float] = None
    colbert_rank: Optional[int] = None
    colbert_softmax_score: Optional[float] = None
    hybrid_score: Optional[float] = None


class DiscoverToolsResult(BaseModel):
    """Structured result returned by the discover_tools MCP tool."""

    query: str
    tools: List[DiscoveredTool]
    count: int
    search_mode: str


def create_mcp_server(
    retriever: Optional[BM25SRetriever] = None,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    path: str = DEFAULT_PATH,
    redis_config: Optional[RedisConfig] = None,
) -> FastMCP:
    """Create the Axiolex discovery MCP server."""
    if retriever is None:
        retriever = get_tool_discovery_retriever(redis_config)
    service = ToolDiscoveryService(retriever=retriever)
    server = FastMCP(
        "axiolex",
        instructions=(
            "Use discover_tools to select execution-ready tools for a user request. "
            "Execute returned tools through the calling application's local executor."
        ),
        host=host,
        port=port,
        streamable_http_path=path,
        json_response=True,
        stateless_http=True,
        transport_security=TransportSecuritySettings(
            allowed_hosts=[
                "localhost:*",
                "127.0.0.1:*",
                "[::1]:*",
                "axiolex:*",
            ],
            allowed_origins=[
                "http://localhost:*",
                "http://127.0.0.1:*",
                "http://[::1]:*",
                "http://axiolex:*",
            ],
        ),
    )

    @server.tool(
        name="discover_tools",
        title="Discover Axiolex Tools",
        description=(
            "Find tools relevant to a natural-language request and return their exact "
            "names, parameter schemas, endpoints, and transports."
        ),
        structured_output=True,
    )
    def discover_tools(
        query: Annotated[
            str,
            Field(description="Natural-language request to route to tools."),
        ],
        max_tools: Annotated[
            Optional[int],
            Field(
                ge=1,
                le=100,
                description="Maximum execution-ready tools to return.",
            ),
        ] = None,
        hybrid_search: Annotated[
            bool,
            Field(description="Use BM25 + ColBERT softmax score fusion."),
        ] = False,
        temperature: Annotated[
            Optional[float],
            Field(
                ge=0.1,
                le=10.0,
                description=(
                    "Softmax temperature for hybrid score fusion. Omit to use "
                    "the server retrieval default."
                ),
            ),
        ] = None,
        min_hybrid_score: Annotated[
            Optional[float],
            Field(
                ge=0.0,
                description="Optional threshold on fused hybrid_score.",
            ),
        ] = None,
        bm25_weight: Annotated[
            Optional[float],
            Field(
                ge=0.0,
                description=(
                    "BM25 blend weight. Omit to use AXIOLEX_HYBRID_BM25_WEIGHT "
                    "server default, usually 0.4."
                ),
            ),
        ] = None,
        colbert_weight: Annotated[
            Optional[float],
            Field(
                ge=0.0,
                description=(
                    "ColBERT blend weight. Omit to use "
                    "AXIOLEX_HYBRID_COLBERT_WEIGHT server default, usually 0.6."
                ),
            ),
        ] = None,
        candidate_limit: Annotated[
            Optional[int],
            Field(
                ge=1,
                le=1000,
                description=(
                    "Per-model candidate count before fusion. Omit to use "
                    "AXIOLEX_HYBRID_CANDIDATE_LIMIT server default, usually 100."
                ),
            ),
        ] = None,
        min_rrf_score: Annotated[
            Optional[float],
            Field(
                ge=0.0,
                description="Deprecated alias for min_hybrid_score.",
            ),
        ] = None,
    ) -> DiscoverToolsResult:
        return DiscoverToolsResult.model_validate(
            service.discover_tools(
                query=query,
                max_tools=max_tools,
                hybrid_search=hybrid_search,
                temperature=temperature,
                min_hybrid_score=min_hybrid_score,
                bm25_weight=bm25_weight,
                colbert_weight=colbert_weight,
                candidate_limit=candidate_limit,
                min_rrf_score=min_rrf_score,
            )
        )

    return server


def main() -> None:
    """Run Axiolex as a Streamable HTTP MCP server."""
    parser = argparse.ArgumentParser(description="Axiolex MCP discovery server")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host to bind to")
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help="Port to bind to"
    )
    parser.add_argument("--path", default=DEFAULT_PATH, help="MCP HTTP path")
    parser.add_argument(
        "--redis-host",
        default=os.getenv("AXIOLEX_REDIS_HOST", DEFAULT_REDIS_HOST),
    )
    parser.add_argument(
        "--redis-port",
        type=int,
        default=int(os.getenv("AXIOLEX_REDIS_PORT", str(DEFAULT_REDIS_PORT))),
    )
    parser.add_argument(
        "--redis-db",
        type=int,
        default=int(os.getenv("AXIOLEX_REDIS_DB", str(DEFAULT_REDIS_DB))),
    )
    parser.add_argument("--redis-password-env")
    args = parser.parse_args()

    password = os.getenv(args.redis_password_env) if args.redis_password_env else None
    redis_config = RedisConfig(
        host=args.redis_host,
        port=args.redis_port,
        db=args.redis_db,
        password=password,
    )
    try:
        create_mcp_server(
            host=args.host,
            port=args.port,
            path=args.path,
            redis_config=redis_config,
        ).run(transport="streamable-http")
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
