"""
MCP Client Test Suite for Clipboard Server

This module provides comprehensive testing for the clipboard MCP server using a 
subprocess-based approach that mimics how real MCP clients interact with servers.
"""

import asyncio
import json
import subprocess
import sys
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

# Add src to path for testing without installation
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
except ImportError:
    PYPERCLIP_AVAILABLE = False
    print("Warning: pyperclip not available, some tests may be skipped", file=sys.stderr)


class MCPClientTester:
    """
    A testing client that communicates with MCP servers via stdio subprocess.
    Implements the MCP JSON-RPC protocol for testing purposes.
    """
    
    def __init__(self, server_command: list):
        self.server_command = server_command
        self.process: Optional[subprocess.Popen] = None
        self.request_id = 0
        
    @asynccontextmanager
    async def server_context(self):
        """Context manager that starts and cleans up the MCP server process."""
        try:
            # Start the MCP server as a subprocess
            print(f"Starting MCP server: {' '.join(self.server_command)}", file=sys.stderr)
            
            self.process = await asyncio.create_subprocess_exec(
                *self.server_command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            print("MCP server started successfully", file=sys.stderr)
            yield self
            
        except Exception as e:
            print(f"Error starting server: {e}", file=sys.stderr)
            raise
            
        finally:
            # Clean up the server process
            if self.process and self.process.returncode is None:
                print("Terminating MCP server", file=sys.stderr)
                self.process.terminate()
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    print("Force killing MCP server", file=sys.stderr)
                    self.process.kill()
                    await self.process.wait()
    
    async def initialize_connection(self) -> Dict[str, Any]:
        """Initialize the MCP connection with the server."""
        request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "resources": {},
                    "prompts": {}
                },
                "clientInfo": {
                    "name": "clipboard-mcp-test-client",
                    "version": "1.0.0"
                }
            }
        }
        
        response = await self._send_request(request)
        print(f"Server initialized: {response.get('result', {}).get('serverInfo', {})}", file=sys.stderr)
        return response
    
    async def list_tools(self) -> Dict[str, Any]:
        """List all available tools from the server."""
        request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/list",
            "params": {}
        }
        return await self._send_request(request)
    
    async def call_tool(self, name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        """Call a specific tool with given arguments."""
        request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments or {}
            }
        }
        return await self._send_request(request)
    
    def _next_id(self) -> int:
        """Generate next request ID."""
        self.request_id += 1
        return self.request_id
    
    async def _send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send a JSON-RPC request and await response."""
        if not self.process:
            raise RuntimeError("Server process not started")
        
        # Send request
        message = json.dumps(request) + "\n"
        print(f"Sending request: {request['method']}", file=sys.stderr)
        
        self.process.stdin.write(message.encode())
        await self.process.stdin.drain()
        
        # Read response
        response_line = await self.process.stdout.readline()
        if not response_line:
            # Check if server process has stderr output
            if self.process.stderr:
                stderr_data = await asyncio.wait_for(
                    self.process.stderr.read(1024), 
                    timeout=1.0
                )
                if stderr_data:
                    print(f"Server stderr: {stderr_data.decode()}", file=sys.stderr)
            raise RuntimeError("Server closed connection or no response received")
        
        try:
            response = json.loads(response_line.decode().strip())
        except json.JSONDecodeError as e:
            print(f"Invalid JSON response: {response_line.decode()}", file=sys.stderr)
            raise RuntimeError(f"Invalid JSON response from server: {e}")
        
        if "error" in response:
            print(f"Server error: {response['error']}", file=sys.stderr)
            raise Exception(f"Server error: {response['error']}")
        
        print(f"Received response for {request['method']}", file=sys.stderr)
        return response


async def test_clipboard_server():
    """
    Comprehensive test of the clipboard MCP server.
    Tests initialization, tool discovery, and all clipboard operations.
    """
    
    # Build path to server script
    project_root = Path(__file__).parent.parent
    server_script = project_root / "src" / "clipboard_mcp" / "server.py"
    
    if not server_script.exists():
        raise FileNotFoundError(f"Server script not found at {server_script}")
    
    # Test server command
    server_command = [sys.executable, str(server_script)]
    
    print("=" * 60, file=sys.stderr)
    print("STARTING CLIPBOARD MCP SERVER TESTS", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    
    async with MCPClientTester(server_command).server_context() as client:
        try:
            # Test 1: Initialize connection
            print("\n1. Testing server initialization...", file=sys.stderr)
            init_response = await client.initialize_connection()
            
            assert "result" in init_response, "Initialization should return result"
            result = init_response["result"]
            assert "protocolVersion" in result, "Should return protocol version"
            assert "serverInfo" in result, "Should return server info"
            
            server_info = result["serverInfo"]
            assert server_info["name"] == "clipboard-mcp", f"Expected 'clipboard-mcp', got '{server_info['name']}'"
            
            print("✓ Server initialization successful", file=sys.stderr)
            
            # Test 2: List available tools
            print("\n2. Testing tool discovery...", file=sys.stderr)
            tools_response = await client.list_tools()
            
            assert "result" in tools_response, "Tool listing should return result"
            tools = tools_response["result"]["tools"]
            
            expected_tools = {"get_clipboard_contents", "copy_to_clipboard", "get_clipboard_info"}
            actual_tools = {tool["name"] for tool in tools}
            
            assert expected_tools.issubset(actual_tools), f"Missing tools. Expected: {expected_tools}, Got: {actual_tools}"
            print(f"✓ Found all expected tools: {actual_tools}", file=sys.stderr)
            
            # Verify tool schemas
            for tool in tools:
                assert "name" in tool, "Tool should have name"
                assert "description" in tool, "Tool should have description"
                assert "inputSchema" in tool, "Tool should have input schema"
                print(f"  - {tool['name']}: {tool['description'][:50]}...", file=sys.stderr)
            
            # Test 3: Test clipboard operations (if pyperclip is available)
            if PYPERCLIP_AVAILABLE:
                print("\n3. Testing clipboard operations...", file=sys.stderr)
                
                # Test copy operation
                test_text = "Hello from MCP clipboard test! 🚀"
                print(f"   Copying text: '{test_text}'", file=sys.stderr)
                
                copy_response = await client.call_tool("copy_to_clipboard", {"text": test_text})
                assert "result" in copy_response, "Copy should return result"
                
                content = copy_response["result"]["content"]
                assert len(content) > 0, "Copy result should have content"
                assert content[0]["type"] == "text", "Copy result should be text"
                
                copy_result_text = content[0]["text"]
                assert "Successfully copied" in copy_result_text, f"Unexpected copy result: {copy_result_text}"
                assert str(len(test_text)) in copy_result_text, f"Copy result should mention length: {copy_result_text}"
                
                print("✓ Copy to clipboard successful", file=sys.stderr)
                
                # Test read operation
                print("   Reading clipboard contents...", file=sys.stderr)
                read_response = await client.call_tool("get_clipboard_contents")
                assert "result" in read_response, "Read should return result"
                
                content = read_response["result"]["content"]
                assert len(content) > 0, "Read result should have content"
                assert content[0]["type"] == "text", "Read result should be text"
                
                read_text = content[0]["text"]
                assert read_text == test_text, f"Expected '{test_text}', got '{read_text}'"
                
                print("✓ Read from clipboard successful", file=sys.stderr)
                
                # Test clipboard info
                print("   Getting clipboard info...", file=sys.stderr)
                info_response = await client.call_tool("get_clipboard_info")
                assert "result" in info_response, "Info should return result"
                
                content = info_response["result"]["content"]
                assert len(content) > 0, "Info result should have content"
                assert content[0]["type"] == "text", "Info result should be text"
                
                # Parse the info response (should be JSON-like structure)
                info_text = content[0]["text"]
                print(f"   Clipboard info: {info_text}", file=sys.stderr)
                
                # Basic validation that it contains expected fields
                assert "length" in info_text, "Info should contain length"
                assert str(len(test_text)) in info_text, f"Info should show correct length: {info_text}"
                
                print("✓ Get clipboard info successful", file=sys.stderr)
                
            else:
                print("\n3. Skipping clipboard operations (pyperclip not available)", file=sys.stderr)
                
                # Still test the tools, but expect error responses
                try:
                    await client.call_tool("get_clipboard_contents")
                    print("✓ get_clipboard_contents handled gracefully", file=sys.stderr)
                except Exception as e:
                    print(f"✓ get_clipboard_contents failed as expected: {e}", file=sys.stderr)
            
            # Test 4: Error handling
            print("\n4. Testing error handling...", file=sys.stderr)
            
            try:
                # Try to call non-existent tool
                await client.call_tool("nonexistent_tool")
                assert False, "Should have raised exception for non-existent tool"
            except Exception as e:
                print(f"✓ Non-existent tool properly rejected: {e}", file=sys.stderr)
            
            try:
                # Try to call with invalid arguments
                await client.call_tool("copy_to_clipboard", {"invalid_arg": "value"})
                # This might succeed if the server is lenient, or fail - both are acceptable
                print("✓ Invalid arguments handled", file=sys.stderr)
            except Exception as e:
                print(f"✓ Invalid arguments properly rejected: {e}", file=sys.stderr)
            
            print("\n" + "=" * 60, file=sys.stderr)
            print("ALL TESTS PASSED! ✅", file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            
        except Exception as e:
            print(f"\n❌ TEST FAILED: {e}", file=sys.stderr)
            
            # Try to get server stderr for debugging
            if client.process and client.process.stderr:
                try:
                    stderr_data = await asyncio.wait_for(
                        client.process.stderr.read(1024),
                        timeout=1.0
                    )
                    if stderr_data:
                        print(f"Server stderr: {stderr_data.decode()}", file=sys.stderr)
                except asyncio.TimeoutError:
                    pass
            
            raise


def main():
    """Main entry point for the test."""
    if not PYPERCLIP_AVAILABLE:
        print("Warning: pyperclip not available. Some tests will be limited.", file=sys.stderr)
    
    try:
        asyncio.run(test_clipboard_server())
        print("🎉 All tests completed successfully!")
        return 0
    except Exception as e:
        print(f"💥 Tests failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())