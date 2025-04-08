# chess-uci-mcp

An MCP server that provides an interface to UCI chess engines (such as Stockfish).

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/chess-uci-mcp.git
cd chess-uci-mcp

# Create a virtual environment
uv venv --python python3.10

# Activate the virtual environment
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate     # On Windows

# Install the package in development mode
uv pip install -e .
```

## Usage

After installation, you can run the server with:

```bash
uv run chess-uci-mcp /path/to/stockfish
```

## MCP Integration

Add the following server to your MCP configuration:

```json
"mcpServers": {
  "chess-uci-mcp": {
    "command": "uv",
    "args": ["run", "chess-uci-mcp", "/path/to/stockfish_binary"]
  }
}
```

## Development

```bash
# Install development dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Check code style
ruff check
```
