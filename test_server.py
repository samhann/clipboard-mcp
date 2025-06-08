#!/usr/bin/env python3
"""
Simple test script to verify MCP server structure without full installation.
This tests the imports and basic functionality.
"""

import sys
import os

# Add src to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    # Test imports
    print("Testing imports...", file=sys.stderr)
    
    # Test pyperclip (might not be installed)
    try:
        import pyperclip
        print("✓ pyperclip available", file=sys.stderr)
    except ImportError:
        print("✗ pyperclip not available (expected - run pip install pyperclip)", file=sys.stderr)
    
    # Test fastmcp (might not be installed)
    try:
        from fastmcp import FastMCP
        print("✓ fastmcp available", file=sys.stderr)
    except ImportError:
        print("✗ fastmcp not available (expected - run pip install fastmcp)", file=sys.stderr)
    
    # Test our server module structure
    try:
        from clipboard_mcp import __version__
        print(f"✓ clipboard_mcp package loaded, version: {__version__}", file=sys.stderr)
    except ImportError as e:
        print(f"✗ clipboard_mcp package import failed: {e}", file=sys.stderr)
    
    print("Test completed. Install dependencies to run the full server.", file=sys.stderr)
    
except Exception as e:
    print(f"Error during testing: {e}", file=sys.stderr)
    sys.exit(1)