"""
Pytest-compatible integration tests for clipboard MCP server.
These tests can be run with: pytest tests/test_clipboard_integration.py -v
"""

import pytest
import asyncio
import sys
import os
from pathlib import Path

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from test_mcp_client import MCPClientTester

# Skip tests if dependencies are not available
pytest_asyncio = pytest.importorskip("pytest_asyncio")

try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
except ImportError:
    PYPERCLIP_AVAILABLE = False


class TestClipboardMCPServer:
    """Test suite for clipboard MCP server using pytest framework."""
    
    @pytest.fixture
    async def mcp_client(self):
        """Fixture that provides an initialized MCP client connected to our server."""
        project_root = Path(__file__).parent.parent
        server_script = project_root / "src" / "clipboard_mcp" / "server.py"
        
        if not server_script.exists():
            pytest.skip(f"Server script not found at {server_script}")
        
        server_command = [sys.executable, str(server_script)]
        
        async with MCPClientTester(server_command).server_context() as client:
            # Initialize the connection
            await client.initialize_connection()
            yield client
    
    @pytest.mark.asyncio
    async def test_server_initialization(self, mcp_client):
        """Test that the server initializes correctly and returns proper metadata."""
        # The client is already initialized by the fixture
        tools_response = await mcp_client.list_tools()
        
        assert "result" in tools_response
        tools = tools_response["result"]["tools"]
        
        # Verify we have the expected tools
        tool_names = {tool["name"] for tool in tools}
        expected_tools = {"get_clipboard_contents", "copy_to_clipboard", "get_clipboard_info"}
        
        assert expected_tools.issubset(tool_names), f"Missing tools. Expected: {expected_tools}, Got: {tool_names}"
        
        # Verify each tool has required properties
        for tool in tools:
            assert "name" in tool, "Tool must have a name"
            assert "description" in tool, "Tool must have a description"
            assert "inputSchema" in tool, "Tool must have an input schema"
            assert len(tool["description"]) > 10, "Tool description should be meaningful"
    
    @pytest.mark.asyncio
    async def test_tool_schemas(self, mcp_client):
        """Test that tool schemas are properly defined."""
        tools_response = await mcp_client.list_tools()
        tools = tools_response["result"]["tools"]
        
        tool_by_name = {tool["name"]: tool for tool in tools}
        
        # Test copy_to_clipboard schema
        copy_tool = tool_by_name["copy_to_clipboard"]
        copy_schema = copy_tool["inputSchema"]
        assert "properties" in copy_schema
        assert "text" in copy_schema["properties"], "copy_to_clipboard should have 'text' parameter"
        assert copy_schema["properties"]["text"]["type"] == "string"
        
        # Test get_clipboard_contents schema (should have no required parameters)
        get_tool = tool_by_name["get_clipboard_contents"]
        get_schema = get_tool["inputSchema"]
        # This tool should have no required parameters
        required = get_schema.get("required", [])
        assert len(required) == 0, "get_clipboard_contents should have no required parameters"
        
        # Test get_clipboard_info schema
        info_tool = tool_by_name["get_clipboard_info"]
        info_schema = info_tool["inputSchema"]
        required = info_schema.get("required", [])
        assert len(required) == 0, "get_clipboard_info should have no required parameters"
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(not PYPERCLIP_AVAILABLE, reason="pyperclip not available")
    async def test_clipboard_copy_and_read(self, mcp_client):
        """Test copying text to clipboard and reading it back."""
        test_text = "Hello from pytest! 🧪"
        
        # Copy text to clipboard
        copy_response = await mcp_client.call_tool("copy_to_clipboard", {"text": test_text})
        
        assert "result" in copy_response
        content = copy_response["result"]["content"]
        assert len(content) > 0
        assert content[0]["type"] == "text"
        
        copy_result = content[0]["text"]
        assert "Successfully copied" in copy_result
        assert str(len(test_text)) in copy_result
        
        # Read text from clipboard
        read_response = await mcp_client.call_tool("get_clipboard_contents")
        
        assert "result" in read_response
        content = read_response["result"]["content"]
        assert len(content) > 0
        assert content[0]["type"] == "text"
        
        read_text = content[0]["text"]
        assert read_text == test_text, f"Expected '{test_text}', got '{read_text}'"
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(not PYPERCLIP_AVAILABLE, reason="pyperclip not available")
    async def test_clipboard_info(self, mcp_client):
        """Test getting clipboard metadata."""
        test_text = "Test clipboard info 📊"
        
        # First, put some known text in clipboard
        await mcp_client.call_tool("copy_to_clipboard", {"text": test_text})
        
        # Get clipboard info
        info_response = await mcp_client.call_tool("get_clipboard_info")
        
        assert "result" in info_response
        content = info_response["result"]["content"]
        assert len(content) > 0
        assert content[0]["type"] == "text"
        
        info_text = content[0]["text"]
        
        # The info should contain length information
        assert "length" in info_text
        assert str(len(test_text)) in info_text
        assert "preview" in info_text or "has_content" in info_text
    
    @pytest.mark.asyncio
    async def test_error_handling_invalid_tool(self, mcp_client):
        """Test that invalid tool calls are handled properly."""
        with pytest.raises(Exception) as exc_info:
            await mcp_client.call_tool("nonexistent_tool", {})
        
        # Should get some kind of error about unknown tool
        error_msg = str(exc_info.value).lower()
        assert "error" in error_msg or "unknown" in error_msg or "not found" in error_msg
    
    @pytest.mark.asyncio
    async def test_copy_empty_string(self, mcp_client):
        """Test copying an empty string to clipboard."""
        copy_response = await mcp_client.call_tool("copy_to_clipboard", {"text": ""})
        
        assert "result" in copy_response
        content = copy_response["result"]["content"]
        assert len(content) > 0
        assert content[0]["type"] == "text"
        
        result_text = content[0]["text"]
        assert "0 characters" in result_text or "Successfully copied" in result_text
    
    @pytest.mark.asyncio
    async def test_copy_unicode_text(self, mcp_client):
        """Test copying unicode text with emojis and special characters."""
        unicode_text = "Hello 世界! 🌍 Testing unicode: αβγ 🚀✨"
        
        copy_response = await mcp_client.call_tool("copy_to_clipboard", {"text": unicode_text})
        
        assert "result" in copy_response
        content = copy_response["result"]["content"]
        assert len(content) > 0
        assert content[0]["type"] == "text"
        
        result_text = content[0]["text"]
        assert "Successfully copied" in result_text
        
        # If pyperclip is available, verify we can read it back
        if PYPERCLIP_AVAILABLE:
            read_response = await mcp_client.call_tool("get_clipboard_contents")
            read_content = read_response["result"]["content"]
            read_text = read_content[0]["text"]
            assert read_text == unicode_text
    
    @pytest.mark.asyncio
    async def test_large_text_handling(self, mcp_client):
        """Test handling of large text content."""
        # Create a reasonably large text (10KB)
        large_text = "A" * 10000
        
        copy_response = await mcp_client.call_tool("copy_to_clipboard", {"text": large_text})
        
        assert "result" in copy_response
        content = copy_response["result"]["content"]
        assert len(content) > 0
        assert content[0]["type"] == "text"
        
        result_text = content[0]["text"]
        assert "Successfully copied" in result_text
        assert "10000" in result_text
    
    @pytest.mark.asyncio
    async def test_clipboard_graceful_error_handling(self, mcp_client):
        """Test that clipboard operations handle errors gracefully."""
        # This test should pass regardless of pyperclip availability
        # The server should return error messages rather than crashing
        
        try:
            read_response = await mcp_client.call_tool("get_clipboard_contents")
            # If this succeeds, great!
            assert "result" in read_response
        except Exception as e:
            # If it fails, the error should be graceful
            error_msg = str(e).lower()
            assert any(word in error_msg for word in ["error", "clipboard", "access"]), \
                f"Error should be clipboard-related: {e}"
        
        try:
            copy_response = await mcp_client.call_tool("copy_to_clipboard", {"text": "test"})
            # If this succeeds, great!
            assert "result" in copy_response
        except Exception as e:
            # If it fails, the error should be graceful
            error_msg = str(e).lower()
            assert any(word in error_msg for word in ["error", "clipboard", "access"]), \
                f"Error should be clipboard-related: {e}"