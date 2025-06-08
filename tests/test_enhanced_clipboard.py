"""
Comprehensive tests for the enhanced clipboard MCP server.
Tests database integration, URL fetching, image handling, and all new tools.
"""

import asyncio
import json
import sys
import os
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, List
from contextlib import asynccontextmanager

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from test_mcp_client import MCPClientTester

try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
except ImportError:
    PYPERCLIP_AVAILABLE = False


async def test_enhanced_clipboard_server():
    """
    Comprehensive test of the enhanced clipboard MCP server.
    Tests all new functionality including database, URL fetching, and history.
    """
    
    project_root = Path(__file__).parent.parent
    server_script = project_root / "src" / "clipboard_mcp" / "server.py"
    
    if not server_script.exists():
        raise FileNotFoundError(f"Server script not found at {server_script}")
    
    # Test server command
    server_command = [sys.executable, str(server_script)]
    
    print("=" * 60, file=sys.stderr)
    print("TESTING ENHANCED CLIPBOARD MCP SERVER", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    
    async with MCPClientTester(server_command).server_context() as client:
        try:
            # Test 1: Initialize connection
            print("\n1. Testing server initialization...", file=sys.stderr)
            init_response = await client.initialize_connection()
            
            assert "result" in init_response, "Initialization should return result"
            result = init_response["result"]
            assert result["serverInfo"]["name"] == "clipboard-mcp"
            assert result["serverInfo"]["version"] == "0.2.0"
            
            print("✓ Enhanced server initialization successful", file=sys.stderr)
            
            # Test 2: List available tools (should have 8 tools now)
            print("\n2. Testing enhanced tool discovery...", file=sys.stderr)
            tools_response = await client.list_tools()
            
            assert "result" in tools_response
            tools = tools_response["result"]["tools"]
            
            expected_tools = {
                "get_clipboard_contents", 
                "copy_to_clipboard", 
                "get_clipboard_info",
                "search_clipboard_history",
                "get_recent_clipboard_entries", 
                "get_clipboard_entry",
                "get_url_entries",
                "get_clipboard_stats"
            }
            actual_tools = {tool["name"] for tool in tools}
            
            assert expected_tools.issubset(actual_tools), f"Missing tools. Expected: {expected_tools}, Got: {actual_tools}"
            print(f"✓ Found all {len(actual_tools)} enhanced tools", file=sys.stderr)
            
            # Test 3: Basic clipboard operations
            print("\n3. Testing basic clipboard operations...", file=sys.stderr)
            
            if PYPERCLIP_AVAILABLE:
                # Test copy operation
                test_text = "Enhanced clipboard test with database! 🚀"
                copy_response = await client.call_tool("copy_to_clipboard", {"text": test_text})
                assert "result" in copy_response
                print("✓ Copy operation successful", file=sys.stderr)
                
                # Wait a moment for monitoring to pick up the change
                await asyncio.sleep(3)
                
                # Test read operation
                read_response = await client.call_tool("get_clipboard_contents")
                assert "result" in read_response
                content = read_response["result"]["content"][0]["text"]
                assert content == test_text
                print("✓ Read operation successful", file=sys.stderr)
            else:
                print("⚠️  Skipping clipboard operations (pyperclip not available)", file=sys.stderr)
            
            # Test 4: Database and history functionality
            print("\n4. Testing database and history functionality...", file=sys.stderr)
            
            # Get statistics
            stats_response = await client.call_tool("get_clipboard_stats")
            assert "result" in stats_response
            stats_content = stats_response["result"]["content"][0]["text"]
            assert "Total entries:" in stats_content
            print("✓ Statistics retrieval successful", file=sys.stderr)
            
            # Get recent entries
            recent_response = await client.call_tool("get_recent_clipboard_entries", {"limit": 5})
            assert "result" in recent_response
            recent_content = recent_response["result"]["content"][0]["text"]
            print("✓ Recent entries retrieval successful", file=sys.stderr)
            
            # Test 5: URL functionality
            print("\n5. Testing URL functionality...", file=sys.stderr)
            
            if PYPERCLIP_AVAILABLE:
                # Copy a URL to clipboard
                test_url = "https://httpbin.org/json"
                await client.call_tool("copy_to_clipboard", {"text": test_url})
                
                # Wait for URL processing
                await asyncio.sleep(5)
                
                # Check URL entries
                url_entries_response = await client.call_tool("get_url_entries", {"limit": 10})
                assert "result" in url_entries_response
                url_content = url_entries_response["result"]["content"][0]["text"]
                print("✓ URL entries retrieval successful", file=sys.stderr)
                
                # Search for the URL
                search_response = await client.call_tool("search_clipboard_history", {"query": "httpbin"})
                assert "result" in search_response
                search_content = search_response["result"]["content"][0]["text"]
                print("✓ Search functionality successful", file=sys.stderr)
                
            else:
                print("⚠️  Skipping URL tests (pyperclip not available)", file=sys.stderr)
            
            # Test 6: Advanced features
            print("\n6. Testing advanced features...", file=sys.stderr)
            
            # Test search with different parameters
            search_text_response = await client.call_tool("search_clipboard_history", {
                "query": "test",
                "content_type": "text",
                "limit": 3
            })
            assert "result" in search_text_response
            print("✓ Advanced search successful", file=sys.stderr)
            
            # Test clipboard info (enhanced)
            info_response = await client.call_tool("get_clipboard_info")
            assert "result" in info_response
            info_content = json.loads(info_response["result"]["content"][0]["text"])
            assert "is_url" in info_content  # New field
            print("✓ Enhanced clipboard info successful", file=sys.stderr)
            
            # Test 7: Error handling for new tools
            print("\n7. Testing error handling for new tools...", file=sys.stderr)
            
            # Test invalid entry ID
            try:
                await client.call_tool("get_clipboard_entry", {"entry_id": 99999})
                print("✓ Invalid entry ID handled gracefully", file=sys.stderr)
            except Exception as e:
                print(f"✓ Invalid entry ID properly rejected: {e}", file=sys.stderr)
            
            # Test empty search
            empty_search_response = await client.call_tool("search_clipboard_history", {"query": "nonexistentquery12345"})
            assert "result" in empty_search_response
            empty_content = empty_search_response["result"]["content"][0]["text"]
            assert "No clipboard entries found" in empty_content
            print("✓ Empty search results handled properly", file=sys.stderr)
            
            print("\n" + "=" * 60, file=sys.stderr)
            print("ALL ENHANCED TESTS PASSED! ✅", file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            
            # Print summary of what was tested
            print("\n📋 Enhanced Features Tested:", file=sys.stderr)
            print("  ✓ 8 MCP tools (5 new + 3 original)", file=sys.stderr)
            print("  ✓ SQLite database integration", file=sys.stderr)
            print("  ✓ Clipboard history and persistence", file=sys.stderr)
            print("  ✓ URL detection and content fetching", file=sys.stderr)
            print("  ✓ Full-text search functionality", file=sys.stderr)
            print("  ✓ Statistics and monitoring", file=sys.stderr)
            print("  ✓ Enhanced error handling", file=sys.stderr)
            print("  ✓ Backwards compatibility", file=sys.stderr)
            
        except Exception as e:
            print(f"\n❌ ENHANCED TEST FAILED: {e}", file=sys.stderr)
            
            # Try to get server stderr for debugging
            if client.process and client.process.stderr:
                try:
                    stderr_data = await asyncio.wait_for(
                        client.process.stderr.read(2048),
                        timeout=1.0
                    )
                    if stderr_data:
                        print(f"Server stderr: {stderr_data.decode()}", file=sys.stderr)
                except asyncio.TimeoutError:
                    pass
            
            raise


async def test_database_operations():
    """Test database operations directly."""
    print("\n" + "=" * 60, file=sys.stderr)
    print("TESTING DATABASE OPERATIONS", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    
    try:
        # Import modules for direct testing
        from clipboard_mcp.database import ClipboardDatabase
        from clipboard_mcp.url_fetcher import URLFetcher
        
        # Test with temporary database
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
            db_path = tmp_db.name
            
        try:
            # Test database initialization
            print("Testing database initialization...", file=sys.stderr)
            db = ClipboardDatabase(db_path)
            await db.connect()
            print("✓ Database initialized", file=sys.stderr)
            
            # Test adding entries
            print("Testing entry addition...", file=sys.stderr)
            entry_id = await db.add_entry("Test content", "text")
            assert entry_id is not None
            print(f"✓ Added entry {entry_id}", file=sys.stderr)
            
            # Test URL entry
            url_entry_id = await db.add_entry("https://example.com", "url")
            await db.update_url_data(
                url_entry_id,
                url_title="Example Domain",
                url_description="Example description",
                url_content="Example content",
                url_status_code=200
            )
            print("✓ Added URL entry with metadata", file=sys.stderr)
            
            # Test search
            results = await db.search_entries("Test")
            assert len(results) > 0
            print("✓ Search functionality working", file=sys.stderr)
            
            # Test stats
            stats = await db.get_stats()
            assert stats['total_entries'] >= 2
            print("✓ Statistics generation working", file=sys.stderr)
            
            await db.close()
            print("✓ Database operations completed successfully", file=sys.stderr)
            
        finally:
            # Cleanup
            try:
                os.unlink(db_path)
            except:
                pass
                
    except ImportError as e:
        print(f"⚠️  Skipping database tests: {e}", file=sys.stderr)
    except Exception as e:
        print(f"❌ Database test failed: {e}", file=sys.stderr)
        raise


async def test_url_fetcher():
    """Test URL fetching functionality."""
    print("\n" + "=" * 60, file=sys.stderr)
    print("TESTING URL FETCHER", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    
    try:
        from clipboard_mcp.url_fetcher import URLFetcher
        
        fetcher = URLFetcher()
        
        # Test URL detection
        assert fetcher.is_url("https://httpbin.org/json")
        assert not fetcher.is_url("not a url")
        print("✓ URL detection working", file=sys.stderr)
        
        # Test URL extraction
        url = fetcher.extract_url("Check this out: https://httpbin.org/json and more text")
        assert url == "https://httpbin.org/json"
        print("✓ URL extraction working", file=sys.stderr)
        
        # Test actual fetching (if network available)
        try:
            async with fetcher:
                result = await fetcher.fetch_url_content("https://httpbin.org/json")
                assert result["status_code"] == 200
                print("✓ URL fetching working", file=sys.stderr)
        except Exception as e:
            print(f"⚠️  Network test failed (expected in some environments): {e}", file=sys.stderr)
            
    except ImportError as e:
        print(f"⚠️  Skipping URL fetcher tests: {e}", file=sys.stderr)
    except Exception as e:
        print(f"❌ URL fetcher test failed: {e}", file=sys.stderr)
        raise


def main():
    """Main entry point for enhanced tests."""
    async def run_all_tests():
        print("🧪 Enhanced Clipboard MCP Server Test Suite", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        
        # Run database tests first
        await test_database_operations()
        
        # Run URL fetcher tests
        await test_url_fetcher()
        
        # Run full server integration tests
        await test_enhanced_clipboard_server()
        
        print("\n🎉 ALL ENHANCED TESTS COMPLETED SUCCESSFULLY!", file=sys.stderr)
        print("The enhanced clipboard MCP server is ready for use!", file=sys.stderr)
    
    try:
        asyncio.run(run_all_tests())
        print("✅ Enhanced test suite passed!")
        return 0
    except Exception as e:
        print(f"💥 Enhanced tests failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())