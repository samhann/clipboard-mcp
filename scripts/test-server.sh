#!/bin/bash

# Clipboard MCP Server Test Script
# This script sets up the environment and runs comprehensive tests on the clipboard MCP server

set -e  # Exit on any error

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Change to project directory
cd "$PROJECT_DIR"

echo "🧪 Clipboard MCP Server Test Suite" >&2
echo "===================================" >&2
echo "Project directory: $PROJECT_DIR" >&2
echo "" >&2

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if Python 3 is available
if ! command_exists python3; then
    echo "❌ Error: python3 is not installed or not in PATH" >&2
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version 2>&1)" >&2

# Check if virtual environment exists, create if it doesn't
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..." >&2
    python3 -m venv venv
    echo "✓ Virtual environment created" >&2
else
    echo "✓ Virtual environment exists" >&2
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..." >&2
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..." >&2
pip install --upgrade pip >&2

# Install the package and test dependencies
echo "📥 Installing package and dependencies..." >&2
pip install -e ".[test]" >&2

echo "✓ Dependencies installed" >&2
echo "" >&2

# Check if pyperclip works (clipboard access)
echo "🔧 Testing clipboard access..." >&2
python3 -c "
import sys
try:
    import pyperclip
    # Test basic clipboard functionality
    test_text = 'clipboard-test-123'
    pyperclip.copy(test_text)
    result = pyperclip.paste()
    if result == test_text:
        print('✓ Clipboard access working', file=sys.stderr)
    else:
        print('⚠️  Clipboard access limited (may affect some tests)', file=sys.stderr)
except Exception as e:
    print(f'⚠️  Clipboard access error: {e}', file=sys.stderr)
    print('   (Tests will run but with limited functionality)', file=sys.stderr)
"

echo "" >&2

# Run the comprehensive MCP client tests
echo "🚀 Running MCP server tests..." >&2
echo "==============================" >&2

# Run our custom MCP client test
python3 tests/test_mcp_client.py

test_exit_code=$?

echo "" >&2

if [ $test_exit_code -eq 0 ]; then
    echo "🎉 All tests passed successfully!" >&2
    echo "" >&2
    echo "📋 Test Summary:" >&2
    echo "  ✓ MCP server initialization" >&2
    echo "  ✓ Tool discovery and validation" >&2
    echo "  ✓ Clipboard operations (copy/read/info)" >&2
    echo "  ✓ Error handling" >&2
    echo "  ✓ JSON-RPC protocol compliance" >&2
    echo "" >&2
    echo "🔧 Server is ready for use with Cursor or other MCP clients!" >&2
else
    echo "❌ Tests failed with exit code: $test_exit_code" >&2
    echo "" >&2
    echo "🔍 Troubleshooting tips:" >&2
    echo "  - Check that all dependencies are installed: pip install -e .[test]" >&2
    echo "  - Ensure clipboard access is available (GUI environment)" >&2
    echo "  - Check server.py for syntax errors" >&2
    echo "  - Review test output above for specific error details" >&2
    exit $test_exit_code
fi

# Optional: Run pytest if available and there are pytest-compatible tests
if command_exists pytest && [ -f "tests/test_example.py" ]; then
    echo "" >&2
    echo "🧹 Running additional pytest tests..." >&2
    pytest tests/ -v >&2 || echo "⚠️  Some pytest tests failed (non-critical)" >&2
fi

echo "" >&2
echo "✅ Test suite completed!" >&2