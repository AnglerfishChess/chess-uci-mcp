"""
MCP server module for chess engine integration.

This module implements the MCP server that provides access to UCI chess engines.
"""

import logging
from typing import Any

import esca
from mcp.server import FastMCP

from chess_uci_mcp.engine import UCIEngine
from chess_uci_mcp.types import (
    EngineInfo,
    GetEngineOptionsResult,
    OptionInfo,
    SetEngineOptionsResult,
)

logger = logging.getLogger(__name__)


class ChessUCIBridge:
    """Bridge between MCP and UCI chess engines."""

    def __init__(self, engine_path: str, **options):
        """
        Initialize the chess UCI bridge.

        Args:
            engine_path: Path to the UCI engine executable
            options: Engine options (e.g., think_time, Threads, Hash)
        """
        self.engine_path = engine_path
        self.default_think_time = options.pop("think_time", 1000)
        self.engine_options = options

        self.engine: UCIEngine | None = None
        self.mcp = FastMCP("chess-uci")

        # Register tools
        self._register_tools()

    def _register_tools(self):
        """Register MCP tools for chess engine functions."""

        @self.mcp.tool("analyze", description="Analyze a chess position specified by FEN string.")
        async def analyze(fen: str, time_ms: int | None = None) -> dict[str, Any]:
            """
            Analyze a chess position.

            Args:
                fen: FEN string representation of the position
                time_ms: Time to think in milliseconds (default uses bridge setting)

            Returns:
                Analysis results
            """
            engine = await self._ensure_engine_started()

            # Use default time if not specified
            think_time = time_ms if time_ms is not None else self.default_think_time

            # Validate FEN
            try:
                esca.Position.from_fen(fen)
            except ValueError:
                raise ValueError(f"Invalid FEN string: {fen}") from None

            result = await engine.analyze_position(fen, think_time)
            return result

        @self.mcp.tool("get_best_move", description="Get the best move for a chess position.")
        async def get_best_move(fen: str | None = None, time_ms: int | None = None) -> str:
            """
            Get best move for current or specified position.

            Args:
                fen: FEN string (optional, if omitted uses current position)
                time_ms: Time to think in milliseconds (default uses bridge setting)

            Returns:
                Best move in UCI format (e.g., "e2e4")
            """
            engine = await self._ensure_engine_started()

            # Set position if FEN is provided
            if fen:
                try:
                    esca.Position.from_fen(fen)
                except ValueError:
                    raise ValueError(f"Invalid FEN string: {fen}") from None
                await engine.set_position(fen)

            # Use default time if not specified
            think_time = time_ms if time_ms is not None else self.default_think_time

            best_move = await engine.get_best_move(think_time)
            return best_move

        @self.mcp.tool("set_position", description="Set the current chess position.")
        async def set_position(fen: str | None = None, moves: list[str] | None = None) -> dict[str, bool]:
            """
            Set a position on the engine's internal board.

            Args:
                fen: FEN string (if None, uses starting position)
                moves: List of moves in UCI format

            Returns:
                Success status
            """
            engine = await self._ensure_engine_started()

            # Validate FEN if provided
            if fen:
                try:
                    esca.Position.from_fen(fen)
                except ValueError:
                    raise ValueError(f"Invalid FEN string: {fen}") from None

            # Validate moves
            if moves and not isinstance(moves, list):
                raise ValueError("Moves must be a list of strings")

            await engine.set_position(fen, moves)
            return {"success": True}

        @self.mcp.tool("engine_info", description="Get information about the chess engine.")
        async def engine_info() -> EngineInfo:
            """
            Get engine information including engine ID and configured options.

            Returns:
                Engine information with path, id, and configured options
            """
            engine = await self._ensure_engine_started()

            return {
                "path": self.engine_path,
                "id": engine.get_engine_id(),
                "configured_options": self.engine_options,
            }

        @self.mcp.tool(
            "get_engine_options",
            description="Get all available UCI engine options with their metadata and current values.",
        )
        async def get_engine_options() -> GetEngineOptionsResult:
            """
            List all available UCI options with their metadata and current values.

            Returns:
                Dictionary of all options with metadata (type, default, min, max, var)
                and current values
            """
            engine = await self._ensure_engine_started()

            available_options = engine.get_available_options()
            current_values = engine.get_current_option_values()

            options: dict[str, OptionInfo] = {}
            for name, metadata in available_options.items():
                # Current value is either explicitly set or falls back to default
                current_value = current_values.get(name, metadata["default"])
                options[name] = {
                    "metadata": metadata,
                    "current_value": current_value,
                }

            return {"options": options}

        @self.mcp.tool(
            "set_engine_options",
            description="Set one or more UCI engine options at runtime.",
        )
        async def set_engine_options(options: dict[str, Any]) -> SetEngineOptionsResult:
            """
            Set UCI engine options dynamically.

            Args:
                options: Dictionary mapping option names to values.
                         Example: {"Hash": 256, "Threads": 4}

            Returns:
                Result with success status, applied options, and any errors
            """
            engine = await self._ensure_engine_started()

            if not options:
                return {
                    "success": True,
                    "applied_options": {},
                    "errors": {},
                }

            applied, errors = await engine.set_options(options)

            return {
                "success": len(errors) == 0,
                "applied_options": applied,
                "errors": errors,
            }

    async def _ensure_engine_started(self) -> UCIEngine:
        """Ensure the engine is started, and answer with it."""
        if not self.engine:
            # Create a copy of options without think_time (it's not a UCI option)
            engine_options = {k: v for k, v in self.engine_options.items() if k != "think_time"}
            engine = UCIEngine(self.engine_path, engine_options)
            await engine.start()
            self.engine = engine
        return self.engine

    async def start(self):
        """Start the MCP bridge."""
        logger.info("Starting Chess UCI MCP bridge with engine: %s", self.engine_path)

        # Start the engine
        await self._ensure_engine_started()

        # Run in stdio mode
        await self.mcp.run_stdio_async()

    async def stop(self):
        """Stop the MCP bridge."""
        logger.info("Stopping Chess UCI MCP bridge")

        # Stop the engine
        if self.engine:
            await self.engine.stop()
            self.engine = None
