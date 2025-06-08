# MCP Server Development and Debugging Guide

This guide covers everything learned while building and debugging the clipboard MCP server, including common issues, solutions, and best practices.

## Table of Contents

- [Common Issues](#common-issues)
- [Python Version Compatibility](#python-version-compatibility)
- [MCP Protocol Implementation](#mcp-protocol-implementation)
- [Testing and Debugging](#testing-and-debugging)
- [Cursor Integration](#cursor-integration)
- [Protocol Communication](#protocol-communication)
- [Best Practices](#best-practices)

## Common Issues

### 1. Python Version Compatibility ⚠️

**Problem**: FastMCP and official MCP libraries require Python 3.10+
**Symptoms**: 
```
ERROR: Could not find a version that satisfies the requirement fastmcp>=0.1.0
ERROR: Could not find a version that satisfies the requirement mcp>=1.0.0
```

**Solutions**:
- **Option A**: Upgrade to Python 3.10+ and use official libraries
- **Option B**: Implement MCP protocol directly (what we did)
- **Option C**: Use alternative MCP implementations

**Our Implementation**: Direct JSON-RPC 2.0 implementation compatible with Python 3.9+

### 2. Cursor Shows Red Dot / "0 tools enabled"

**Common Causes**:
1. **Startup script outputs to stdout** (interferes with MCP protocol)
2. **Python version incompatibility**
3. **Missing dependencies**
4. **Incorrect JSON-RPC response format**
5. **Server crashes during initialization**

**Debugging Steps**:
```bash
# Test server manually
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{"tools":{}}}}' | ./scripts/run-server-quiet.sh

# Should return:
{"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "clipboard-mcp", "version": "0.1.0"}}}
```

### 3. Clipboard Access Issues

**Problem**: pyperclip fails in headless environments
**Solutions**:
- Graceful error handling in clipboard operations
- Check for GUI environment availability
- Provide meaningful error messages

```python
try:
    content = pyperclip.paste()
    return [{"type": "text", "text": content}]
except Exception as e:
    return [{"type": "text", "text": f"Error accessing clipboard: {str(e)}"}]
```

## Python Version Compatibility

### Checking Your Python Version
```bash
python3 --version
# If you have 3.10+, you can use official libraries
# If you have 3.9 or below, use direct implementation
```

### Library Requirements by Python Version

| Python Version | FastMCP | Official MCP | Direct Implementation |
|---------------|---------|--------------|---------------------|
| 3.8           | ❌      | ❌           | ✅                  |
| 3.9           | ❌      | ❌           | ✅                  |
| 3.10+         | ✅      | ✅           | ✅                  |

### Migration Path

**From FastMCP to Direct Implementation**:
```python
# Before (FastMCP)
from fastmcp import FastMCP
mcp = FastMCP("server-name")

@mcp.tool
def my_tool() -> str:
    return "result"

# After (Direct)
class MCPServer:
    def handle_list_tools(self, request_id):
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": [...]}
        }
```

## MCP Protocol Implementation

### Essential JSON-RPC Methods

1. **initialize** - Server capability negotiation
2. **tools/list** - List available tools
3. **tools/call** - Execute a tool
4. **notifications/initialized** - Initialization complete (notification only)

### Request/Response Examples

**Initialize Request**:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {"tools": {}},
    "clientInfo": {"name": "cursor", "version": "1.0"}
  }
}
```

**Initialize Response**:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {"tools": {}},
    "serverInfo": {"name": "clipboard-mcp", "version": "0.1.0"}
  }
}
```

**Tools List Response**:
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "tools": [
      {
        "name": "get_clipboard_contents",
        "description": "Get clipboard contents",
        "inputSchema": {
          "type": "object",
          "properties": {},
          "required": []
        }
      }
    ]
  }
}
```

**Tool Call Response**:
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {"type": "text", "text": "Tool execution result"}
    ]
  }
}
```

### Error Handling

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32601,
    "message": "Method not found: unknown_method"
  }
}
```

**Common Error Codes**:
- `-32700`: Parse error
- `-32600`: Invalid request  
- `-32601`: Method not found
- `-32602`: Invalid params
- `-32603`: Internal error

## Testing and Debugging

### 1. Manual Protocol Testing

```bash
# Test initialization
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{"tools":{}}}}' | ./scripts/run-server-quiet.sh

# Test tool listing
(echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{"tools":{}}}}'; echo '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}') | ./scripts/run-server-quiet.sh
```

### 2. Automated Testing Framework

Our test client (`tests/test_mcp_client.py`) provides:
- Subprocess-based server testing
- Full MCP protocol simulation
- Clipboard operation verification
- Error handling validation

```bash
# Run comprehensive tests
./scripts/test-server.sh

# Run individual test
python tests/test_mcp_client.py
```

### 3. Debugging Common Issues

**Server Not Starting**:
```bash
# Check if script is executable
ls -la scripts/run-server-quiet.sh

# Test Python execution
python3 -c "import sys; print(sys.version)"

# Check dependencies
pip list | grep pyperclip
```

**Protocol Errors**:
```bash
# Enable debug logging in server
# Add to server.py:
logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
```

**Clipboard Issues**:
```bash
# Test clipboard access
python3 -c "import pyperclip; pyperclip.copy('test'); print(pyperclip.paste())"
```

## Cursor Integration

### Configuration File Location

- **Global**: `~/.cursor/mcp.json`
- **Project**: `.cursor/mcp.json`

### Configuration Format

```json
{
  "mcpServers": {
    "clipboard-mcp": {
      "command": "/absolute/path/to/scripts/run-server-quiet.sh",
      "args": []
    }
  }
}
```

### Alternative Configurations

**Using Python directly**:
```json
{
  "mcpServers": {
    "clipboard-mcp": {
      "command": "/absolute/path/to/venv/bin/python",
      "args": ["-m", "clipboard_mcp.server"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/src"
      }
    }
  }
}
```

**Using uv**:
```json
{
  "mcpServers": {
    "clipboard-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path", "python", "-m", "clipboard_mcp.server"]
    }
  }
}
```

### Troubleshooting Cursor Integration

1. **Check Cursor Settings**: Go to Settings > MCP Servers
2. **Look for Status Indicators**:
   - 🟢 Green: Working correctly
   - 🟠 Orange: Configuration issues
   - 🔴 Red: Server failed to start
3. **Click Refresh**: Circular arrow icon to reload configuration
4. **Check Tool Count**: Should show "3 tools enabled" for clipboard-mcp
5. **Restart Cursor**: Close and reopen completely after config changes

## Protocol Communication

### Stdio Transport

MCP servers communicate via stdin/stdout using JSON-RPC 2.0:
- **stdin**: Receives JSON-RPC requests (one per line)
- **stdout**: Sends JSON-RPC responses (one per line)
- **stderr**: Used for logging only

### Critical Rules

1. **Never print to stdout** except for JSON-RPC responses
2. **All logging goes to stderr**
3. **One JSON object per line**
4. **Flush output immediately** after sending responses
5. **Handle EOF gracefully** (client disconnect)

### Message Flow

```
Client → Server: {"jsonrpc":"2.0","id":1,"method":"initialize",...}
Server → Client: {"jsonrpc":"2.0","id":1,"result":{...}}

Client → Server: {"jsonrpc":"2.0","id":2,"method":"tools/list",...}
Server → Client: {"jsonrpc":"2.0","id":2,"result":{"tools":[...]}}

Client → Server: {"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"tool_name"}}
Server → Client: {"jsonrpc":"2.0","id":3,"result":{"content":[...]}}
```

## Best Practices

### 1. Development

- **Use absolute paths** in Cursor configuration
- **Test manually** before integrating with Cursor
- **Implement graceful error handling**
- **Provide detailed tool descriptions**
- **Use proper JSON schema for tool inputs**

### 2. Error Handling

```python
try:
    result = perform_operation()
    return [{"type": "text", "text": result}]
except Exception as e:
    logger.error(f"Operation failed: {e}")
    return [{"type": "text", "text": f"Error: {str(e)}"}]
```

### 3. Logging

```python
import logging
import sys

# Configure logging to stderr only
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("your-mcp-server")
```

### 4. Tool Design

- **Clear descriptions**: Explain what the tool does and when to use it
- **Proper schemas**: Define input parameters with types and descriptions
- **Consistent return format**: Always return list of content objects
- **Handle edge cases**: Empty inputs, missing data, etc.

### 5. Testing

- **Unit tests**: Test individual tool functions
- **Integration tests**: Test full MCP protocol communication
- **Error scenarios**: Test with invalid inputs and edge cases
- **Cross-platform**: Test on different operating systems

### 6. Deployment

- **Startup scripts**: Handle environment setup automatically
- **Dependency management**: Use virtual environments
- **Silent installation**: Avoid output during server startup
- **Version compatibility**: Document Python version requirements

## Debugging Checklist

When MCP server isn't working:

- [ ] Check Python version compatibility
- [ ] Verify all dependencies are installed
- [ ] Test server manually with JSON-RPC
- [ ] Check startup script permissions
- [ ] Verify absolute paths in configuration
- [ ] Look for stdout contamination
- [ ] Check stderr for error messages
- [ ] Test clipboard access separately
- [ ] Restart Cursor after configuration changes
- [ ] Check MCP settings for status indicators

## Advanced Topics

### Custom Transport

For advanced use cases, you can implement HTTP or WebSocket transports instead of stdio.

### Security Considerations

- Validate all inputs
- Sanitize file paths
- Limit resource access
- Handle sensitive data appropriately

### Performance Optimization

- Cache expensive operations
- Use async/await for I/O operations
- Implement request timeouts
- Monitor memory usage

### Monitoring and Observability

- Structured logging
- Metrics collection
- Health checks
- Error tracking

---

This guide represents lessons learned from building a production-ready MCP server from scratch, dealing with real-world compatibility issues, and successfully integrating with Cursor IDE.