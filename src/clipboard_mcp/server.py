#!/usr/bin/env python3
"""
Clipboard MCP Server - A minimal MCP server for clipboard operations.

This server implements the Model Context Protocol (MCP) using direct JSON-RPC 2.0
communication over stdio, making it compatible with Python 3.9+.
"""

import asyncio
import json
import sys
import logging
from typing import Any, Dict, List, Optional

import pyperclip

# Configure logging to stderr only (stdout is used for MCP protocol)
logging.basicConfig(
    level=logging.INFO, 
    stream=sys.stderr, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("clipboard-mcp")


class ClipboardMCPServer:
    """Minimal MCP server implementation for clipboard operations."""
    
    def __init__(self):
        self.request_id = 0
        
    async def handle_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle incoming JSON-RPC requests."""
        try:
            method = request.get("method")
            params = request.get("params", {})
            request_id = request.get("id")
            
            logger.info(f"Handling request: {method}")
            
            if method == "initialize":
                return self.handle_initialize(request_id, params)
            elif method == "tools/list":
                return self.handle_list_tools(request_id)
            elif method == "tools/call":
                return await self.handle_call_tool(request_id, params)
            elif method == "notifications/initialized":
                # This is a notification, no response needed
                return None
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }
                
        except Exception as e:
            logger.error(f"Error handling request: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
    
    def handle_initialize(self, request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "clipboard-mcp",
                    "version": "0.1.0"
                }
            }
        }
    
    def handle_list_tools(self, request_id: Any) -> Dict[str, Any]:
        """Handle tools/list request."""
        tools = [
            {
                "name": "get_clipboard_contents",
                "description": (
                    "Get the current contents of the system clipboard. "
                    "This tool retrieves whatever text is currently stored in the system clipboard. "
                    "Useful for accessing copied text, URLs, code snippets, or any other textual "
                    "content that has been copied to the clipboard."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "copy_to_clipboard",
                "description": (
                    "Copy the provided text to the system clipboard. "
                    "This tool allows you to programmatically copy text to the system clipboard, "
                    "making it available for pasting in other applications."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "The text content to copy to the clipboard"
                        }
                    },
                    "required": ["text"]
                }
            },
            {
                "name": "get_clipboard_info",
                "description": (
                    "Get information about the current clipboard contents. "
                    "This tool provides metadata about the clipboard contents without returning "
                    "the full text, which is useful for understanding what's in the clipboard "
                    "before deciding whether to retrieve it."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        ]
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": tools
            }
        }
    
    async def handle_call_tool(self, request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        logger.info(f"Calling tool: {tool_name} with args: {arguments}")
        
        try:
            if tool_name == "get_clipboard_contents":
                result = await self.get_clipboard_contents()
            elif tool_name == "copy_to_clipboard":
                text = arguments.get("text", "")
                result = await self.copy_to_clipboard(text)
            elif tool_name == "get_clipboard_info":
                result = await self.get_clipboard_info()
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32602,
                        "message": f"Unknown tool: {tool_name}"
                    }
                }
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": result
                }
            }
            
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": f"Tool execution error: {str(e)}"
                }
            }
    
    async def get_clipboard_contents(self) -> List[Dict[str, str]]:
        """Get the current contents of the system clipboard."""
        try:
            content = pyperclip.paste()
            if content is None or content == "":
                text = "Clipboard is empty"
            else:
                text = content
            
            return [{"type": "text", "text": text}]
            
        except Exception as e:
            logger.error(f"Error accessing clipboard: {e}")
            return [{"type": "text", "text": f"Error accessing clipboard: {str(e)}"}]
    
    async def copy_to_clipboard(self, text: str) -> List[Dict[str, str]]:
        """Copy the provided text to the system clipboard."""
        try:
            pyperclip.copy(text)
            char_count = len(text)
            return [{"type": "text", "text": f"Successfully copied {char_count} characters to clipboard"}]
            
        except Exception as e:
            logger.error(f"Error copying to clipboard: {e}")
            return [{"type": "text", "text": f"Error copying to clipboard: {str(e)}"}]
    
    async def get_clipboard_info(self) -> List[Dict[str, str]]:
        """Get information about the current clipboard contents."""
        try:
            content = pyperclip.paste()
            
            if content is None:
                content = ""
                
            length = len(content)
            is_empty = length == 0
            has_content = not is_empty
            preview = content[:50] + "..." if length > 50 else content
            
            info = {
                "length": length,
                "is_empty": is_empty,
                "has_content": has_content,
                "preview": preview if has_content else "No content"
            }
            
            return [{"type": "text", "text": json.dumps(info, indent=2)}]
            
        except Exception as e:
            logger.error(f"Error getting clipboard info: {e}")
            error_info = {
                "length": -1,
                "is_empty": True,
                "has_content": False,
                "preview": f"Error: {str(e)}"
            }
            return [{"type": "text", "text": json.dumps(error_info, indent=2)}]


async def main():
    """Main entry point for the clipboard MCP server."""
    logger.info("Starting clipboard MCP server")
    
    server = ClipboardMCPServer()
    
    while True:
        try:
            # Read line from stdin
            line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
            
            if not line:
                logger.info("EOF received, shutting down")
                break
                
            line = line.strip()
            if not line:
                continue
                
            logger.debug(f"Received: {line}")
            
            # Parse JSON-RPC request
            try:
                request = json.loads(line)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON received: {e}")
                continue
            
            # Handle request
            response = await server.handle_request(request)
            
            # Send response (only if it's not a notification)
            if response is not None:
                response_json = json.dumps(response)
                print(response_json, flush=True)
                logger.debug(f"Sent: {response_json}")
                
        except KeyboardInterrupt:
            logger.info("Received interrupt, shutting down")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            break
    
    logger.info("Server shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())