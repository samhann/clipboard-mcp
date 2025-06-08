#!/bin/bash

# Clipboard MCP Server Startup Script (Quiet version for Cursor)
# This script ensures the server runs with minimal output

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Change to project directory
cd "$PROJECT_DIR"

# Check if virtual environment exists, create if it doesn't
if [ ! -d "venv" ]; then
    python3 -m venv venv >/dev/null 2>&1
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies quietly
pip install --upgrade pip >/dev/null 2>&1
pip install -e . >/dev/null 2>&1

# Run the MCP server
python -m clipboard_mcp.server