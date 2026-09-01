"""axiolex_execute_tool — generic tool dispatcher.

The dispatcher resolves a tool by ``tool_id`` from the current catalog,
validates arguments against the *current* schema, and dispatches via a
transport adapter. JSON-RPC 2.0 is the wire format for every MCP
message; the only two official transports that carry it are stdio (local
subprocess providers) and Streamable HTTP (remote providers).

Phase 1 does not implement user-level authorization or policy enforcement.
The execution interface is intended for trusted environments.
"""

from .errors import ExecutionError
from .adapters import TransportAdapter, StreamableHttpAdapter, StdioAdapter, get_adapter
from .service import ToolExecutionService, execute_tool

__all__ = [
    "ExecutionError",
    "TransportAdapter",
    "StreamableHttpAdapter",
    "StdioAdapter",
    "get_adapter",
    "ToolExecutionService",
    "execute_tool",
]
