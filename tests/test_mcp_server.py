import pytest

from axiolex.mcp import server as mcp_server
from axiolex.mcp.server import create_mcp_server


class EmptyRetriever:
    def retrieve_documents(self, query, **kwargs):
        return {"success": True, "documents": []}


@pytest.mark.asyncio
async def test_mcp_server_exposes_discover_and_list_namespaces():
    server = create_mcp_server(retriever=EmptyRetriever())

    tools = await server.list_tools()

    assert [tool.name for tool in tools] == ["discover_tools", "list_namespaces"]
    # discover_tools schema
    dt = next(t for t in tools if t.name == "discover_tools")
    assert dt.inputSchema["properties"]["query"]["type"] == "string"
    assert "top_k" in dt.inputSchema["properties"]
    assert "hybrid_search" in dt.inputSchema["properties"]
    assert "temperature" in dt.inputSchema["properties"]
    assert "min_hybrid_score" in dt.inputSchema["properties"]
    assert "bm25_weight" in dt.inputSchema["properties"]
    assert "colbert_weight" in dt.inputSchema["properties"]
    assert "candidate_limit" in dt.inputSchema["properties"]
    assert "min_rrf_score" in dt.inputSchema["properties"]
    assert "namespaces" in dt.inputSchema["properties"]
    assert set(dt.outputSchema["properties"]) == {
        "query",
        "tools",
        "count",
        "search_mode",
    }
    tool_output = dt.outputSchema["$defs"]["DiscoveredTool"]["properties"]
    assert "rank" in tool_output
    assert "relevance_score" in tool_output
    assert "hybrid_score" in tool_output
    assert "bm25_softmax_score" in tool_output
    assert "colbert_softmax_score" in tool_output
    # list_namespaces schema
    ln = next(t for t in tools if t.name == "list_namespaces")
    assert set(ln.outputSchema["properties"]) == {"namespaces", "count"}
    ns_output = ln.outputSchema["$defs"]["NamespaceInfo"]["properties"]
    assert set(ns_output) == {"id", "name", "description"}


def test_mcp_server_main_exits_cleanly_on_keyboard_interrupt(monkeypatch):
    class InterruptingServer:
        def run(self, transport):
            assert transport == "stdio"
            raise KeyboardInterrupt()

    monkeypatch.setattr("sys.argv", ["axiolex-mcp-server"])
    monkeypatch.setattr(
        mcp_server,
        "create_mcp_server",
        lambda **kwargs: InterruptingServer(),
    )

    assert mcp_server.main() is None
