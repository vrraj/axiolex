"""MCP server exposing Axiolex tool discovery."""

import argparse
import os
import sys
from typing import Annotated, Any, Dict, List, Optional, Union

# When spawned as a stdio subprocess (e.g. by Claude Desktop), the CWD may be
# "/" or another unrelated directory. Resolve the project root from the package
# location and chdir there so relative paths (.env, source_files/, logs/) work.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.getcwd() != _PROJECT_ROOT and os.path.exists(os.path.join(_PROJECT_ROOT, ".env")):
    os.chdir(_PROJECT_ROOT)

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, Field

from ..core.cache import RedisConfig
from ..core.retriever import BM25SRetriever, get_tool_discovery_retriever
from ..services.tool_discovery_service import ToolDiscoveryService
from ..services.namespace_service import list_consumable_namespaces
from .execution import ToolExecutionService

load_dotenv()


DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 9701
DEFAULT_PATH = "/mcp"
DEFAULT_REDIS_HOST = "localhost"
DEFAULT_REDIS_PORT = 6380
DEFAULT_REDIS_DB = 0


class DiscoveredTool(BaseModel):
    """Execution-ready downstream tool definition."""

    tool_id: str
    name: str
    description: str
    params: Dict[str, Any]
    inputSchema: Dict[str, Any]
    endpoint: Optional[Union[str, Dict[str, Any]]] = None
    transport: Optional[str] = None
    provider: Optional[str] = None
    bm25_score: Optional[float] = None
    softmax_score: Optional[float] = None
    rank: Optional[int] = None
    relevance_score: Optional[float] = None
    bm25_rank: Optional[int] = None
    bm25_softmax_score: Optional[float] = None
    colbert_score: Optional[float] = None
    colbert_rank: Optional[int] = None
    colbert_softmax_score: Optional[float] = None
    hybrid_score: Optional[float] = None


class DiscoverToolsResult(BaseModel):
    """Structured result returned by the axiolex_discover_tools MCP tool."""

    query: str
    tools: List[DiscoveredTool]
    count: int
    search_mode: str


class NamespaceInfo(BaseModel):
    """A single namespace in the enterprise capability map."""

    id: str
    name: str
    description: str


class ListNamespacesResult(BaseModel):
    """Structured result returned by the list_namespaces MCP tool."""

    namespaces: List[NamespaceInfo]
    count: int


class ExecuteToolError(BaseModel):
    """Error payload in an axiolex_execute_tool response (spec Section 4/8)."""

    code: str
    message: str
    retryable: bool


class ExecuteToolResult(BaseModel):
    """Structured result returned by the axiolex_execute_tool MCP tool.

    Matches the spec Section 4 response contract: ``status`` is success or
    error, ``result`` is present only on success, ``error`` only on failure.
    ``tool_id`` and a fresh ``execution_id`` are always echoed back for
    correlation across multi-call agent loops.
    """

    status: str
    tool_id: str
    execution_id: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[ExecuteToolError] = None


# ---------------------------------------------------------------------------
# MCP tool contract and behavioral guidance
#
# Each tool has two parts:
#   - *_CONTRACT: describes what the tool does. This is part of the MCP
#     contract and should NOT be changed — AI clients depend on this to
#     understand how to call the tool.
#   - *_BEHAVIOR: tells the AI client how to present results to the user.
#     This can be freely tweaked to change how Claude/Cursor/Codex surfaces
#     discovered tools and execution results.
#
# The final description sent to the client is the concatenation:
#   description = CONTRACT + " " + BEHAVIOR
#
# To change wording, edit the BEHAVIOR variables below, then restart the
# server (make stop && make start). See README "MCP Tool Descriptions"
# section for details.
# ---------------------------------------------------------------------------

_SERVER_CONTRACT = (
    "Use list_namespaces to see the tool domains Axiolex covers "
    "(e.g. finance.market_data, retail.orders). "
    "Use axiolex_discover_tools to find execution-ready tools for a user "
    "request. "
    "Execute a returned tool by calling axiolex_execute_tool with its tool_id "
    "and the arguments the model produced against the tool's input schema."
)

_SERVER_BEHAVIOR = (
    "Call list_namespaces early in the session to learn what tool domains "
    "Axiolex covers and keep the result in memory. "
    "When calling axiolex_discover_tools, consider passing one or more "
    "namespace IDs to filter results — this helps return more relevant tools "
    "when the user's request clearly maps to a domain. "
    "Filtering is optional; omit namespaces to search the entire catalog. "
    "At the end of your response, list the tool names you discovered and "
    "the tool names you executed."
)

_NAMESPACES_CONTRACT = (
    "List all enabled namespaces (e.g. finance.market_data, retail.orders) "
    "with their names and descriptions. "
    "Namespaces group related tools by domain."
)

_NAMESPACES_BEHAVIOR = (
    "Call this early in the session to learn what tool domains Axiolex covers. "
    "Keep the result in memory. "
    "The namespace IDs are useful as optional filters for "
    "axiolex_discover_tools to return more relevant tools for a user's request."
)

_DISCOVER_CONTRACT = (
    "Find tools relevant to a natural-language request and return their "
    "tool_id, exact name, parameter schema, endpoint, and transport. "
    "Pass the returned tool_id to axiolex_execute_tool to run the tool."
)

_DISCOVER_BEHAVIOR = (
    "List the tool names you found at the end of your response."
)

_EXECUTE_CONTRACT = (
    "Execute a tool previously returned by axiolex_discover_tools. "
    "Pass the tool_id returned by discovery and the arguments the "
    "model produced against that tool's input schema. The dispatcher "
    "resolves the tool fresh from the catalog by tool_id, validates "
    "arguments against the current schema, and dispatches over the "
    "tool's transport. Returns a normalized result envelope with "
    "status, result (on success) or error (on failure), and an "
    "execution_id for tracing."
)

_EXECUTE_BEHAVIOR = (
    "List the tool name you executed at the end of your response."
)


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
        instructions=f"{_SERVER_CONTRACT} {_SERVER_BEHAVIOR}",
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
        name="axiolex_discover_tools",
        title="Discover Axiolex Tools",
        description=f"{_DISCOVER_CONTRACT} {_DISCOVER_BEHAVIOR}",
        structured_output=True,
    )
    def axiolex_discover_tools(
        query: Annotated[
            str,
            Field(description="Natural-language request to route to tools."),
        ],
        top_k: Annotated[
            Optional[int],
            Field(
                ge=1,
                le=100,
                description="Maximum tools Axiolex returns. The calling application decides how many enter LLM context.",
            ),
        ] = None,
        hybrid_search: Annotated[
            Optional[bool],
            Field(
                description=(
                    "None = deployment default (hybrid if AXIOLEX_HYBRID_ENABLED, "
                    "else lexical). True = force hybrid. False = force lexical."
                ),
            ),
        ] = None,
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
        namespaces: Annotated[
            Optional[List[str]],
            Field(
                description=(
                    "Optional list of one or more namespace IDs "
                    "(e.g. ['finance.market_data', 'research.web']) to filter "
                    "discovery to those tool domains. Helps return more relevant "
                    "tools when the request maps to a known domain. "
                    "Omit to search all namespaces."
                ),
            ),
        ] = None,
    ) -> DiscoverToolsResult:
        try:
            return DiscoverToolsResult.model_validate(
                service.discover_tools(
                    query=query,
                    top_k=top_k,
                    hybrid_search=hybrid_search,
                    temperature=temperature,
                    min_hybrid_score=min_hybrid_score,
                    bm25_weight=bm25_weight,
                    colbert_weight=colbert_weight,
                    candidate_limit=candidate_limit,
                    min_rrf_score=min_rrf_score,
                    namespaces=namespaces,
                )
            )
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        except Exception as exc:
            raise RuntimeError(f"Discovery failed: {exc}") from exc

    @server.tool(
        name="list_namespaces",
        title="List Axiolex Namespaces",
        description=f"{_NAMESPACES_CONTRACT} {_NAMESPACES_BEHAVIOR}",
        structured_output=True,
    )
    def list_namespaces() -> ListNamespacesResult:
        entries = list_consumable_namespaces()
        return ListNamespacesResult(
            namespaces=[NamespaceInfo(**ns) for ns in entries],
            count=len(entries),
        )

    @server.tool(
        name="axiolex_execute_tool",
        title="Execute an Axiolex Tool",
        description=f"{_EXECUTE_CONTRACT} {_EXECUTE_BEHAVIOR}",
        structured_output=True,
    )
    async def axiolex_execute_tool(
        tool_id: Annotated[
            str,
            Field(
                description=(
                    "Stable tool identifier returned by axiolex_discover_tools "
                    "(not the raw tool name)."
                ),
            ),
        ],
        arguments: Annotated[
            Dict[str, Any],
            Field(
                description=(
                    "Arguments matching the tool's input schema. Validated "
                    "against the current schema at execution time."
                ),
            ),
        ],
        idempotency_key: Annotated[
            Optional[str],
            Field(
                description=(
                    "Optional caller-supplied key for de-duplicating repeat "
                    "calls to tools with side effects."
                ),
            ),
        ] = None,
        timeout_ms: Annotated[
            Optional[int],
            Field(
                ge=1,
                description=(
                    "Optional execution timeout in milliseconds. Clamped to "
                    "the dispatcher ceiling (AXIOLEX_EXECUTE_TIMEOUT_MS)."
                ),
            ),
        ] = None,
    ) -> ExecuteToolResult:
        service = ToolExecutionService()
        response = await service.execute_tool(
            tool_id=tool_id,
            arguments=arguments,
            idempotency_key=idempotency_key,
            timeout_ms=timeout_ms,
        )
        return ExecuteToolResult.model_validate(response)

    return server


def main() -> None:
    """Run Axiolex as an MCP discovery server."""
    parser = argparse.ArgumentParser(description="Axiolex MCP discovery server")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host to bind to")
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help="Port to bind to"
    )
    parser.add_argument("--path", default=DEFAULT_PATH, help="MCP HTTP path")
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "streamable-http", "sse"],
        help="MCP transport (stdio for Claude Desktop, streamable-http for remote clients)",
    )
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
        ).run(transport=args.transport)
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
