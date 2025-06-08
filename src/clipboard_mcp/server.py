#!/usr/bin/env python3
"""
Clipboard MCP Server - Enhanced with history persistence and URL fetching.

This server implements the Model Context Protocol (MCP) using direct JSON-RPC 2.0
communication over stdio, with SQLite persistence and intelligent content processing.
"""

import asyncio
import json
import sys
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path
import signal

import pyperclip

# Handle imports for both module and direct execution
try:
    from .database import ClipboardDatabase
    from .monitor import ClipboardMonitor
    from .url_fetcher import URLFetcher
except ImportError:
    # Direct execution - add parent to path
    sys.path.insert(0, str(Path(__file__).parent))
    from database import ClipboardDatabase
    from monitor import ClipboardMonitor
    from url_fetcher import URLFetcher

# Configure logging to stderr only (stdout is used for MCP protocol)
logging.basicConfig(
    level=logging.INFO, 
    stream=sys.stderr, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("clipboard-mcp")


class ClipboardMCPServer:
    """Enhanced MCP server implementation for clipboard operations with persistence."""
    
    def __init__(self):
        self.request_id = 0
        self.db: Optional[ClipboardDatabase] = None
        self.monitor: Optional[ClipboardMonitor] = None
        self.running = False
        
    async def initialize(self):
        """Initialize database and monitoring."""
        try:
            # Initialize database
            self.db = ClipboardDatabase()
            await self.db.connect()
            
            # Initialize and start clipboard monitor
            self.monitor = ClipboardMonitor(self.db, poll_interval=2.0)
            await self.monitor.start()
            
            # Setup cleanup on shutdown
            self._setup_signal_handlers()
            
            self.running = True
            logger.info("Clipboard MCP server initialized with monitoring")
            
        except Exception as e:
            logger.error(f"Failed to initialize server: {e}")
            raise
            
    async def shutdown(self):
        """Clean shutdown of server components."""
        if not self.running:
            return
            
        self.running = False
        logger.info("Shutting down clipboard MCP server")
        
        if self.monitor:
            await self.monitor.stop()
            
        if self.db:
            await self.db.close()
            
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating shutdown")
            asyncio.create_task(self.shutdown())
            
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
    async def handle_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle incoming JSON-RPC requests."""
        try:
            method = request.get("method")
            params = request.get("params", {})
            request_id = request.get("id")
            
            logger.debug(f"Handling request: {method}")
            
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
                    "version": "0.2.0"
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
                    "Returns the live clipboard content that is currently available for pasting."
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
                    "This will replace the current clipboard contents and make the text available for pasting."
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
                    "Get information about the current clipboard contents including length, type, and preview. "
                    "Useful for understanding what's in the clipboard before retrieving it."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "search_clipboard_history",
                "description": (
                    "Search through clipboard history using text queries. "
                    "Finds past clipboard entries that match the search terms. "
                    "Useful for finding previously copied text, URLs, or code snippets."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query to find in clipboard history"
                        },
                        "content_type": {
                            "type": "string",
                            "enum": ["text", "url", "image"],
                            "description": "Filter by content type (optional)"
                        },
                        "limit": {
                            "type": "integer",
                            "default": 20,
                            "minimum": 1,
                            "maximum": 100,
                            "description": "Maximum number of results to return"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "get_recent_clipboard_entries",
                "description": (
                    "Get the most recent clipboard entries. "
                    "Shows a history of recently copied items including text, URLs, and images. "
                    "Useful for accessing something that was copied earlier."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 50,
                            "description": "Number of recent entries to return"
                        },
                        "content_type": {
                            "type": "string",
                            "enum": ["text", "url", "image"],
                            "description": "Filter by content type (optional)"
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "get_clipboard_entry",
                "description": (
                    "Get a specific clipboard entry by ID. "
                    "Retrieves the full content of a previously copied item including any fetched URL content."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "entry_id": {
                            "type": "integer",
                            "description": "The ID of the clipboard entry to retrieve"
                        }
                    },
                    "required": ["entry_id"]
                }
            },
            {
                "name": "get_url_entries",
                "description": (
                    "Get clipboard entries that were URLs with their fetched content. "
                    "Shows websites that were copied to clipboard along with their titles, descriptions, and extracted text. "
                    "Useful for finding previously visited web pages and their content."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "default": 20,
                            "minimum": 1,
                            "maximum": 100,
                            "description": "Maximum number of URL entries to return"
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "get_clipboard_stats",
                "description": (
                    "Get statistics about clipboard usage and database contents. "
                    "Shows total entries, entries by type, recent activity, and storage information."
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
        
        logger.debug(f"Calling tool: {tool_name} with args: {arguments}")
        
        try:
            # Original clipboard tools
            if tool_name == "get_clipboard_contents":
                result = await self.get_clipboard_contents()
            elif tool_name == "copy_to_clipboard":
                text = arguments.get("text", "")
                result = await self.copy_to_clipboard(text)
            elif tool_name == "get_clipboard_info":
                result = await self.get_clipboard_info()
            # New history tools
            elif tool_name == "search_clipboard_history":
                query = arguments.get("query", "")
                content_type = arguments.get("content_type")
                limit = arguments.get("limit", 20)
                result = await self.search_clipboard_history(query, content_type, limit)
            elif tool_name == "get_recent_clipboard_entries":
                limit = arguments.get("limit", 10)
                content_type = arguments.get("content_type")
                result = await self.get_recent_clipboard_entries(limit, content_type)
            elif tool_name == "get_clipboard_entry":
                entry_id = arguments.get("entry_id")
                result = await self.get_clipboard_entry(entry_id)
            elif tool_name == "get_url_entries":
                limit = arguments.get("limit", 20)
                result = await self.get_url_entries(limit)
            elif tool_name == "get_clipboard_stats":
                result = await self.get_clipboard_stats()
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
    
    # Original clipboard tools
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
            
            # Force a clipboard check to add to history
            if self.monitor:
                await self.monitor.force_check()
                
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
            preview = content[:100] + "..." if length > 100 else content
            
            # Check if it's a URL
            url_fetcher = URLFetcher()
            is_url = url_fetcher.is_url(content) if content else False
            
            info = {
                "length": length,
                "is_empty": is_empty,
                "has_content": has_content,
                "is_url": is_url,
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
    
    # New history tools
    async def search_clipboard_history(self, query: str, content_type: Optional[str], limit: int) -> List[Dict[str, str]]:
        """Search clipboard history."""
        if not self.db:
            return [{"type": "text", "text": "Database not available"}]
            
        try:
            entries = await self.db.search_entries(
                query=query,
                content_type=content_type,
                limit=limit
            )
            
            if not entries:
                return [{"type": "text", "text": f"No clipboard entries found matching '{query}'"}]
                
            result_text = f"Found {len(entries)} clipboard entries matching '{query}':\n\n"
            
            for entry in entries:
                created_at = entry['created_at']
                content_type = entry['content_type']
                preview = entry['content_preview'] or "[No preview]"
                
                result_text += f"ID: {entry['id']} | {created_at} | {content_type.upper()}\n"
                result_text += f"Preview: {preview}\n"
                
                if entry.get('url_title'):
                    result_text += f"Title: {entry['url_title']}\n"
                if entry.get('url_description'):
                    result_text += f"Description: {entry['url_description'][:100]}...\n"
                    
                result_text += "\n"
                
            return [{"type": "text", "text": result_text}]
            
        except Exception as e:
            logger.error(f"Error searching clipboard history: {e}")
            return [{"type": "text", "text": f"Error searching clipboard history: {str(e)}"}]
    
    async def get_recent_clipboard_entries(self, limit: int, content_type: Optional[str]) -> List[Dict[str, str]]:
        """Get recent clipboard entries."""
        if not self.db:
            return [{"type": "text", "text": "Database not available"}]
            
        try:
            entries = await self.db.search_entries(
                content_type=content_type,
                limit=limit
            )
            
            if not entries:
                return [{"type": "text", "text": "No clipboard entries found"}]
                
            result_text = f"Recent clipboard entries ({len(entries)}):\n\n"
            
            for entry in entries:
                created_at = entry['created_at']
                content_type = entry['content_type']
                preview = entry['content_preview'] or "[No preview]"
                
                result_text += f"ID: {entry['id']} | {created_at} | {content_type.upper()}\n"
                result_text += f"Preview: {preview}\n"
                
                if entry.get('url_title'):
                    result_text += f"Title: {entry['url_title']}\n"
                    
                result_text += "\n"
                
            return [{"type": "text", "text": result_text}]
            
        except Exception as e:
            logger.error(f"Error getting recent entries: {e}")
            return [{"type": "text", "text": f"Error getting recent entries: {str(e)}"}]
    
    async def get_clipboard_entry(self, entry_id: int) -> List[Dict[str, str]]:
        """Get a specific clipboard entry by ID."""
        if not self.db:
            return [{"type": "text", "text": "Database not available"}]
            
        if entry_id is None:
            return [{"type": "text", "text": "Entry ID is required"}]
            
        try:
            entry = await self.db.get_entry_by_id(entry_id)
            
            if not entry:
                return [{"type": "text", "text": f"Entry {entry_id} not found"}]
                
            result_text = f"Clipboard Entry {entry['id']}\n"
            result_text += f"Created: {entry['created_at']}\n"
            result_text += f"Type: {entry['content_type']}\n"
            result_text += f"Accessed: {entry['access_count']} times\n\n"
            
            if entry['content_type'] == 'image':
                result_text += f"Image: {entry.get('image_size', 'Unknown size')} {entry.get('image_format', 'Unknown format')}\n"
                result_text += f"Content: {entry['content']}\n"
            else:
                result_text += f"Content:\n{entry['content']}\n"
                
            if entry.get('url_title'):
                result_text += f"\nURL Title: {entry['url_title']}\n"
            if entry.get('url_description'):
                result_text += f"Description: {entry['url_description']}\n"
            if entry.get('url_content'):
                result_text += f"\nFetched Content:\n{entry['url_content'][:1000]}...\n"
                
            return [{"type": "text", "text": result_text}]
            
        except Exception as e:
            logger.error(f"Error getting entry {entry_id}: {e}")
            return [{"type": "text", "text": f"Error getting entry {entry_id}: {str(e)}"}]
    
    async def get_url_entries(self, limit: int) -> List[Dict[str, str]]:
        """Get URL entries with fetched content."""
        if not self.db:
            return [{"type": "text", "text": "Database not available"}]
            
        try:
            entries = await self.db.get_url_entries(limit)
            
            if not entries:
                return [{"type": "text", "text": "No URL entries found"}]
                
            result_text = f"URL entries with fetched content ({len(entries)}):\n\n"
            
            for entry in entries:
                result_text += f"ID: {entry['id']} | {entry['created_at']}\n"
                result_text += f"URL: {entry['content']}\n"
                
                if entry.get('url_title'):
                    result_text += f"Title: {entry['url_title']}\n"
                if entry.get('url_description'):
                    result_text += f"Description: {entry['url_description']}\n"
                if entry.get('url_fetch_error'):
                    result_text += f"Fetch Error: {entry['url_fetch_error']}\n"
                    
                result_text += "\n"
                
            return [{"type": "text", "text": result_text}]
            
        except Exception as e:
            logger.error(f"Error getting URL entries: {e}")
            return [{"type": "text", "text": f"Error getting URL entries: {str(e)}"}]
    
    async def get_clipboard_stats(self) -> List[Dict[str, str]]:
        """Get clipboard database statistics."""
        if not self.db:
            return [{"type": "text", "text": "Database not available"}]
            
        try:
            stats = await self.db.get_stats()
            
            result_text = "Clipboard Statistics:\n\n"
            result_text += f"Total entries: {stats['total_entries']}\n"
            result_text += f"URL entries: {stats['url_entries']}\n"
            result_text += f"Entries in last 24h: {stats['entries_last_24h']}\n\n"
            
            result_text += "Entries by type:\n"
            for content_type, count in stats['entries_by_type'].items():
                result_text += f"  {content_type}: {count}\n"
                
            # Monitor status
            if self.monitor:
                monitor_status = self.monitor.get_status()
                result_text += f"\nMonitor status: {'Running' if monitor_status['running'] else 'Stopped'}\n"
                result_text += f"Poll interval: {monitor_status['poll_interval']}s\n"
                result_text += f"PIL available: {monitor_status['pil_available']}\n"
                
            return [{"type": "text", "text": result_text}]
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return [{"type": "text", "text": f"Error getting stats: {str(e)}"}]


async def main():
    """Main entry point for the clipboard MCP server."""
    server = ClipboardMCPServer()
    
    try:
        logger.info("Starting clipboard MCP server")
        
        # Start initialization in background but don't wait
        init_task = asyncio.create_task(server.initialize())
        
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
                
                # For initialize request, we can respond immediately
                if request.get("method") == "initialize":
                    response = server.handle_initialize(request.get("id"), request.get("params", {}))
                else:
                    # Wait for initialization to complete for other requests
                    if not init_task.done():
                        await init_task
                    
                    # Handle request normally
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
                
    finally:
        # Cancel initialization if still running
        if not init_task.done():
            init_task.cancel()
            
        await server.shutdown()
        logger.info("Server shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())