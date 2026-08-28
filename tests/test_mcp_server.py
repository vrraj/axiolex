import pytest

from axiolex.mcp import server as mcp_server
from axiolex.mcp.server import create_mcp_server


class EmptyRetriever:
    def retrieve_documents(self, query, **kwargs):
        return {"success": True, "documents": []}


@pytest.mark.asyncio
async def test_mcp_server_exposes_only_discover_tools():
    server = create_mcp_server(retriever=EmptyRetriever())

    tools = await server.list_tools()

    assert [tool.name for tool in tools] == ["discover_tools"]
    assert tools[0].inputSchema["properties"]["query"]["type"] == "string"
    assert "top_k" in tools[0].inputSchema["properties"]
    assert "hybrid_search" in tools[0].inputSchema["properties"]
    assert "temperature" in tools[0].inputSchema["properties"]
    assert "min_hybrid_score" in tools[0].inputSchema["properties"]
    assert "bm25_weight" in tools[0].inputSchema["properties"]
    assert "colbert_weight" in tools[0].inputSchema["properties"]
    assert "candidate_limit" in tools[0].inputSchema["properties"]
    assert "min_rrf_score" in tools[0].inputSchema["properties"]
    assert "namespaces" in tools[0].inputSchema["properties"]
    assert set(tools[0].outputSchema["properties"]) == {
        "query",
        "tools",
        "count",
        "search_mode",
    }
    tool_output = tools[0].outputSchema["$defs"]["DiscoveredTool"]["properties"]
    assert "rank" in tool_output
    assert "relevance_score" in tool_output
    assert "hybrid_score" in tool_output
    assert "bm25_softmax_score" in tool_output
    assert "colbert_softmax_score" in tool_output


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
