# chess-uci-mcp

An MCP bridge that provides an interface to UCI chess engines (such as Stockfish).

## Dependencies

You need to have Python 3.10 or newer, and also `uv`/`uvx` installed.

## Usage

To function, it requires an installed UCI-compatible chess engine, like Stockfish (has been tested with Stockfish 17).

In case of Stockfish, you can download it from https://stockfishchess.org/download/.

On macOS, you can use `brew install stockfish`.

You need to find out the path to your UCI-capable engine binary; for further example configuration, the path is e.g. `/usr/local/bin/stockfish` (which is default for Stockfish installed on macOS using Brew).

The further configuration should be done in your MCP setup;
for Claude Desktop, this is the file `claude_desktop_config.json` (find it in **Settings** menu, **Developer**, then **Edit Config**).

The full path on different OSes

* macOS: `~/Library/Application\ Support/Claude/claude_desktop_config.json`
* Windows: `%APPDATA%/Claude/claude_desktop_config.json`
* Linux: `~/.config/Claude/claude_desktop_config.json`

Add the following settings to your MCP configuration (depending on the way to run it you prefer):

### Uvx (recommended)

Uvx is able to directly run the Python application by its name, ensuring all the dependencies, in a automatically-created virtual environment.
This is the preferred way to run the `chess-uci-mcp` bridge. 

Set up your MCP server configuration (e.g. Claude Desktop configuration) file as following:

```json
"mcpServers": {
  "chess-uci-mcp": {
    "command": "uvx",
    "args": ["--from=git+https://github.com/AnglerfishChess/chess-uci-mcp", "chess-uci-mcp", "/usr/local/bin/stockfish"]
  }
}
```

### Uv

Use it if you have the repository cloned locally and run from it:

```json
"mcpServers": {
  "chess-uci-mcp": {
    "command": "uv",
    "args": ["run", "chess-uci-mcp", "/usr/local/bin/stockfish"]
  }
}
```

## Available MCP Commands

The bridge provides the following MCP commands:

1. `analyze` - Analyze a chess position specified by FEN string
2. `get_best_move` - Get the best move for a chess position
3. `set_position` - Set the current chess position
4. `engine_info` - Get information about the chess engine

## Development

```bash
# Clone the repository
git clone https://github.com/AnglerfishChess/chess-uci-mcp.git
# ... or
#    git clone git@github.com:AnglerfishChess/chess-uci-mcp.git

cd chess-uci-mcp

# Create a virtual environment
uv venv --python python3.10

# Activate the virtual environment
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate     # On Windows

# Install the package in development mode
#    uv pip install -e .
# or, with development dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Check code style
ruff check
```
