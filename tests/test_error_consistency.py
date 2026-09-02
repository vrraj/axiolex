"""Tests for consistent error messages across SDK, REST, and MCP surfaces."""

import json
import pytest
from unittest.mock import patch, MagicMock

from axiolex.sdk import Axiolex, AxiolexError, _raise_for_status


# ---------------------------------------------------------------------------
# SDK error handling
# ---------------------------------------------------------------------------

class TestSdkErrorHandling:
    """Verify the SDK surfaces clean error messages from the server."""

    def _make_response(self, status_code: int, detail: str):
        resp = MagicMock()
        resp.is_success = status_code < 400
        resp.status_code = status_code
        resp.json.return_value = {"detail": detail}
        resp.text = json.dumps({"detail": detail})
        return resp

    def test_raise_for_status_success_does_nothing(self):
        resp = self._make_response(200, "")
        _raise_for_status(resp)  # should not raise

    def test_raise_for_status_400_extracts_detail(self):
        resp = self._make_response(400, "Unknown namespace(s): bad_ns")
        with pytest.raises(AxiolexError) as exc_info:
            _raise_for_status(resp)
        assert exc_info.value.message == "Unknown namespace(s): bad_ns"
        assert exc_info.value.status_code == 400
        assert str(exc_info.value) == "Unknown namespace(s): bad_ns"

    def test_raise_for_status_500_extracts_detail(self):
        resp = self._make_response(500, "Internal server error")
        with pytest.raises(AxiolexError) as exc_info:
            _raise_for_status(resp)
        assert exc_info.value.message == "Internal server error"
        assert exc_info.value.status_code == 500

    def test_raise_for_status_non_json_body(self):
        resp = MagicMock()
        resp.is_success = False
        resp.status_code = 502
        resp.json.side_effect = json.JSONDecodeError("msg", "doc", 0)
        resp.text = "Bad Gateway"
        with pytest.raises(AxiolexError) as exc_info:
            _raise_for_status(resp)
        assert exc_info.value.status_code == 502
        assert "Bad Gateway" in exc_info.value.message

    def test_discover_raises_axiolex_error_on_400(self):
        """SDK discover() should raise AxiolexError, not httpx.HTTPStatusError."""
        client = Axiolex("http://fake-host:9999")
        mock_response = self._make_response(400, "Unknown namespace(s): bad_ns")
        mock_http = MagicMock()
        mock_http.post.return_value = mock_response
        client._client = mock_http

        with pytest.raises(AxiolexError) as exc_info:
            client.discover("test query", namespaces=["bad_ns"])
        assert exc_info.value.message == "Unknown namespace(s): bad_ns"
        assert exc_info.value.status_code == 400

    def test_execute_raises_axiolex_error_on_400(self):
        """SDK execute() should raise AxiolexError on bad tool_id."""
        client = Axiolex("http://fake-host:9999")
        mock_response = self._make_response(400, "TOOL_NOT_FOUND: no such tool")
        mock_http = MagicMock()
        mock_http.post.return_value = mock_response
        client._client = mock_http

        with pytest.raises(AxiolexError) as exc_info:
            client.execute("bad:tool", {})
        assert "TOOL_NOT_FOUND" in exc_info.value.message
        assert exc_info.value.status_code == 400

    def test_list_namespaces_raises_axiolex_error_on_500(self):
        """SDK list_namespaces() should raise AxiolexError on server error."""
        client = Axiolex("http://fake-host:9999")
        mock_response = self._make_response(500, "Redis connection failed")
        mock_http = MagicMock()
        mock_http.get.return_value = mock_response
        client._client = mock_http

        with pytest.raises(AxiolexError) as exc_info:
            client.list_namespaces()
        assert exc_info.value.message == "Redis connection failed"
        assert exc_info.value.status_code == 500

    def test_axiolex_error_is_exception(self):
        """AxiolexError must be catchable as a regular Exception."""
        error = AxiolexError("test", 400)
        assert isinstance(error, Exception)
        assert error.message == "test"
        assert error.status_code == 400


# ---------------------------------------------------------------------------
# Service-layer error messages (the source of truth for all surfaces)
# ---------------------------------------------------------------------------

class TestServiceErrorMessages:
    """Verify the service layer produces the exact messages all surfaces relay."""

    def test_unknown_namespace_message(self):
        """The ValueError message must name the invalid namespace."""
        from axiolex.services.tool_discovery_service import ToolDiscoveryService

        # Use a fake retriever — the namespace check happens before retrieval.
        class FakeRetriever:
            def reload_cache_if_changed(self):
                pass

        service = ToolDiscoveryService(retriever=FakeRetriever())

        with patch("axiolex.services.tool_discovery_service.load_namespaces") as mock_load:
            mock_load.return_value = {"finance", "legal"}
            with pytest.raises(ValueError) as exc_info:
                service.discover_tools(
                    "test query",
                    namespaces=["bad_ns"],
                )
            assert "bad_ns" in str(exc_info.value)
            assert "Unknown namespace" in str(exc_info.value)

    def test_top_k_validation_message(self):
        """The ValueError message for invalid top_k."""
        from axiolex.services.tool_discovery_service import ToolDiscoveryService

        class FakeRetriever:
            def reload_cache_if_changed(self):
                pass

        service = ToolDiscoveryService(retriever=FakeRetriever())
        with pytest.raises(ValueError) as exc_info:
            service.discover_tools("test", top_k=0)
        assert "top_k" in str(exc_info.value)


# ---------------------------------------------------------------------------
# MCP server error handling
# ---------------------------------------------------------------------------

class TestMcpErrorHandling:
    """Verify the MCP server surfaces ValueError cleanly."""

    def test_mcp_discover_unknown_namespace_raises_value_error(self):
        """The MCP tool should propagate ValueError with the original message."""
        from axiolex.mcp.server import create_mcp_server, DiscoverToolsResult

        class FakeRetriever:
            def reload_cache_if_changed(self):
                pass

        server = create_mcp_server(retriever=FakeRetriever())

        # Find the discover tool function in the server's tool registry.
        # FastMCP stores tools in _tool_manager._tools as Tool objects.
        tools = server._tool_manager._tools
        discover_tool = tools.get("axiolex_discover_tools")
        assert discover_tool is not None, "axiolex_discover_tools not found in MCP server"

        # The tool's .fn attribute is the actual callable.
        fn = discover_tool.fn

        with patch("axiolex.services.tool_discovery_service.load_namespaces") as mock_load:
            mock_load.return_value = {"finance", "legal"}
            with pytest.raises(ValueError) as exc_info:
                fn(query="test", namespaces=["bad_ns"])
            assert "bad_ns" in str(exc_info.value)
            assert "Unknown namespace" in str(exc_info.value)

    def test_mcp_discover_unexpected_error_raises_runtime_error(self):
        """Non-ValueError exceptions should be wrapped as RuntimeError."""
        from axiolex.mcp.server import create_mcp_server

        class FakeRetriever:
            def reload_cache_if_changed(self):
                pass

        server = create_mcp_server(retriever=FakeRetriever())
        tools = server._tool_manager._tools
        fn = tools["axiolex_discover_tools"].fn

        with patch(
            "axiolex.services.tool_discovery_service.ToolDiscoveryService.discover_tools",
            side_effect=ConnectionError("Redis is down"),
        ):
            with pytest.raises(RuntimeError) as exc_info:
                fn(query="test")
            assert "Discovery failed" in str(exc_info.value)
            assert "Redis is down" in str(exc_info.value)
