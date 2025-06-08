#!/bin/bash

# Clipboard MCP Server Startup Script
# This script ensures the server runs with the correct Python environment and dependencies

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Change to project directory
cd "$PROJECT_DIR"

# Check if virtual environment exists, create if it doesn't
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..." >&2
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..." >&2
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip >&2

# Install the package in editable mode with dependencies
echo "Installing clipboard-mcp package..." >&2
pip install -e . >&2

# Run the MCP server (no output to stdout, only stderr for errors)
echo "Starting clipboard MCP server..." >&2
python -m clipboard_mcp.server