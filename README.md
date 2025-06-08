# clipboard-mcp

A Model Context Protocol (MCP) implementation for clipboard operations using FastMCP.

This MCP server provides tools to interact with the system clipboard, allowing AI assistants to read clipboard contents, copy text to the clipboard, and get clipboard metadata.

## Features

- **get_clipboard_contents**: Retrieve current clipboard text content
- **copy_to_clipboard**: Copy text to the system clipboard  
- **get_clipboard_info**: Get metadata about clipboard contents (length, preview, etc.)

## Installation

```bash
pip install -e .
```

## Quick Start

### Running the MCP Server

The easiest way to run the server is using the provided startup script:

```bash
./scripts/run-server.sh
```

Or run directly with Python:

```bash
# Make sure you're in a virtual environment with dependencies installed
python -m clipboard_mcp.server
```

Or using the installed console script:

```bash
clipboard-mcp
```

## Development Setup

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```
4. Install the package in editable mode:
   ```bash
   pip install -e .
   ```

## Testing

### Quick Test

Run the comprehensive test suite to verify everything works:

```bash
./scripts/test-server.sh
```

This script will:
- Set up the virtual environment
- Install dependencies  
- Run integration tests with a real MCP client
- Test clipboard operations (copy, read, info)
- Verify JSON-RPC protocol compliance

### Manual Testing

Test individual components:

```bash
# Run the MCP client integration test directly
python tests/test_mcp_client.py

# Run pytest-compatible tests
pip install -e .[test]
pytest tests/test_clipboard_integration.py -v

# Run all pytest tests
pytest
```

### Test Coverage

The test suite includes:
- **MCP Protocol Tests**: Server initialization, tool discovery, JSON-RPC compliance
- **Clipboard Operations**: Copy/read/info operations with real clipboard
- **Error Handling**: Invalid tools, malformed requests, graceful failures  
- **Edge Cases**: Empty strings, unicode text, large content
- **Cross-platform**: Works with or without clipboard access

## Cursor IDE Configuration

To use this MCP server with Cursor IDE, add the following configuration to your MCP settings file:

### Option 1: Using the startup script (Recommended)

Create or edit `.cursor/mcp.json` in your project directory or `~/.cursor/mcp.json` for global access:

```json
{
  "mcpServers": {
    "clipboard-mcp": {
      "command": "/absolute/path/to/clipboard-mcp/scripts/run-server.sh",
      "args": []
    }
  }
}
```

### Option 2: Using Python directly with virtual environment

```json
{
  "mcpServers": {
    "clipboard-mcp": {
      "command": "/absolute/path/to/clipboard-mcp/venv/bin/python",
      "args": ["-m", "clipboard_mcp.server"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/clipboard-mcp/src"
      }
    }
  }
}
```

### Option 3: Using uv (if you have uv installed)

```json
{
  "mcpServers": {
    "clipboard-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/clipboard-mcp", "python", "-m", "clipboard_mcp.server"]
    }
  }
}
```

### Setup Steps for Cursor:

1. **Install the MCP server**: Navigate to the clipboard-mcp directory and run `pip install -e .`
2. **Choose a configuration method**: Pick one of the options above and replace `/absolute/path/to/clipboard-mcp` with the actual path to your clipboard-mcp directory
3. **Create the MCP config file**: Add the configuration to `.cursor/mcp.json` (project-specific) or `~/.cursor/mcp.json` (global)
4. **Restart Cursor**: Close and reopen Cursor IDE
5. **Verify setup**: Go to Cursor Settings > MCP Servers and check that clipboard-mcp shows with a green status indicator

### Usage in Cursor:

Once configured, the clipboard tools will be automatically available to Cursor's Composer Agent. You can:

- Ask Cursor to "check what's in my clipboard"
- Request "copy this text to clipboard: [your text]"
- Ask for clipboard information like "how many characters are in my clipboard?"

The AI will automatically use the appropriate MCP tools to fulfill these requests.

## Code Quality

Run the following commands to ensure code quality:

```bash
# Format code
black src tests

# Sort imports
isort src tests

# Lint code
flake8 src tests

# Type checking
mypy src
```

## Troubleshooting

### Common Issues:

1. **Permission denied for run-server.sh**: Make sure the script is executable with `chmod +x scripts/run-server.sh`
2. **Python module not found**: Ensure you've run `pip install -e .` in the project directory
3. **Clipboard access errors**: Some systems require additional permissions for clipboard access
4. **MCP server not showing in Cursor**: Check that the path in your configuration is absolute and correct

## Dependencies

- **Python 3.8+**
- **fastmcp**: The FastMCP library for creating MCP servers
- **pyperclip**: Cross-platform clipboard access library

## License

MIT License