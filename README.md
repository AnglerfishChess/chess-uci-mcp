# chess-uci-mcp

An MCP bridge that provides an interface to UCI chess engines (such as Stockfish or Leela Chess Zero).

<!-- mcp-name: io.github.AnglerfishChess/chess-uci-mcp -->

The UCI side runs on [esca](https://github.com/AnglerfishChess/esca): it speaks the protocol to the engine and
answers every chess question the bridge has along the way.


## Dependencies

You need to have Python 3.12 or newer, and also `uv`/`uvx` installed.

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
    "args": ["chess-uci-mcp@latest", "/usr/local/bin/stockfish"]
  }
}
```

To pass options to the engine, add them to the `args` array. For example, to set the `Threads` and `Hash` options for Stockfish:

```json
"mcpServers": {
  "chess-uci-mcp": {
    "command": "uvx",
    "args": [
      "chess-uci-mcp@latest", 
      "/usr/local/bin/stockfish",
      "-o", "Threads", "4",
      "-o", "Hash", "128"
    ]
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

Similarly, to pass options when running with `uv`:

```json
"mcpServers": {
  "chess-uci-mcp": {
    "command": "uv",
    "args": [
      "run", 
      "chess-uci-mcp", 
      "/usr/local/bin/stockfish",
      "-o", "Threads", "4",
      "-o", "Hash", "128"
    ]
  }
}
```

## Command-line Options

The application accepts the following command-line options:

*   `ENGINE_PATH`: (Required) The path to the UCI-compatible chess engine executable.
*   `--uci-option` or `-o`: Set a UCI option. This option can be used multiple times. It takes two arguments: the option name and its value (e.g., `-o Threads 4`).
*   `--think-time`: The default thinking time for the engine in milliseconds. Defaults to `1000`.
*   `--debug`: Enable debug logging.

## Available MCP Commands

The bridge provides the following MCP commands:

1. `analyze` - Analyze a chess position specified by FEN string
2. `get_best_move` - Get the best move for a chess position
3. `set_position` - Set the current chess position
4. `engine_info` - Get information about the chess engine
5. `get_engine_options` - Get all available UCI engine options with their metadata and current values
6. `set_engine_options` - Set one or more UCI engine options at runtime

## Development

```bash
# Clone the repository
git clone https://github.com/AnglerfishChess/chess-uci-mcp.git
# ... or
#    git clone git@github.com:AnglerfishChess/chess-uci-mcp.git

cd chess-uci-mcp

# Create a virtual environment
uv venv --python python3.13

# Activate the virtual environment
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate     # On Windows

# Install the package in development mode
#    uv pip install -e .
# or, with development dependencies
uv pip install -e ".[dev]"

# Resync the packages:
uv sync --extra=dev

# Run tests
pytest

# Check code style
ruff check
```

### Release process

The checklist lives in the `releasing` skill under `.claude/skills/`, so a release runs the same way every
time: preconditions, version bump, tag, GitHub release. Publishing a GitHub release is the trigger — from there
`.github/workflows/publish.yml` builds the package and uploads it to PyPI through a
[trusted publisher](https://docs.pypi.org/trusted-publishers/), then republishes the MCP registry entry. Both
authenticate over OIDC, so no token is stored in this repository or on any developer's machine.

Nothing is automatic: a release only happens when a human publishes the GitHub release.

`pyproject.toml` holds the version, and every other copy is derived from it:

```bash
uv sync --extra=dev    # updates uv.lock, keeping the dev tools installed
uv run python .claude/skills/releasing/scripts/sync_version.py
```

That writes `chess_uci_mcp/__init__.py` and both version fields in `server.json`. Passing `--check` instead
reports drift without touching anything, which is what CI runs.

### The MCP registry

[registry.modelcontextprotocol.io](https://registry.modelcontextprotocol.io) is the authoritative index of public
MCP servers, consumed by Smithery, PulseMCP, Docker Hub and others. It has no search box; it is an API:

```bash
curl -s "https://registry.modelcontextprotocol.io/v0/servers?search=chess-uci-mcp&limit=3"
```

The listing is described by `server.json`, under the name `io.github.AnglerfishChess/chess-uci-mcp`. GitHub
authentication grants the `io.github.<user>/*` namespace; an organisation namespace additionally requires Owner
rights on that organisation, and the name is case-sensitive.

Ownership of the PyPI package is proven by the `mcp-name:` marker near the top of this README, which becomes the
package description on PyPI. The registry reads it from the *published* artifact, so adding it to git is not
enough — it only counts once a release carrying it reaches PyPI. Note also that the registry caps `description`
at 100 characters where PyPI does not, which is why `server.json` carries its own one-line description rather
than reusing the project's.

## Related projects

* [esca](https://github.com/AnglerfishChess/esca) — the MIT Rust/Python chess library that speaks UCI for this
  server.
* [chessplaza](https://github.com/AnglerfishChess/chessplaza) — AI chess hustlers with personalities, playing
  through this server.

## Related sites

[Certified by MCP Review](https://mcpreview.com/mcp-servers/anglerfishchess/chess-uci-mcp)

