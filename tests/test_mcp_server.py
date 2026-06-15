import pytest

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
    assert "max_tools" in tools[0].inputSchema["properties"]
    assert "hybrid_search" in tools[0].inputSchema["properties"]
    assert "min_rrf_score" in tools[0].inputSchema["properties"]
    assert set(tools[0].outputSchema["properties"]) == {
        "query",
        "tools",
        "count",
        "search_mode",
    }
