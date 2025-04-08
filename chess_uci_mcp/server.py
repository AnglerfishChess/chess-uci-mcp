"""
MCP server module for chess engine integration.

This module implements the MCP server that provides access to UCI chess engines.
"""

import logging
from typing import Any, Optional

import chess
from mcp.server import FastMCP

from chess_uci_mcp.engine import UCIEngine

logger = logging.getLogger(__name__)


class ChessUCIBridge:
    """Bridge between MCP and UCI chess engines."""

    def __init__(self, engine_path: str, **options):
        """
        Initialize the chess UCI bridge.

        Args:
            engine_path: Path to the UCI engine executable
            options: Engine options (threads, hash, etc.)
        """
        self.engine_path = engine_path
        self.engine_options = {
            "Threads": options.get("threads", 4),
            "Hash": options.get("hash", 128),
        }

        # Add any additional options
        for key, value in options.items():
            if key not in ["threads", "hash"] and not key.startswith("_"):
                self.engine_options[key] = value

        self.default_think_time = options.get("think_time", 1000)
        self.engine: Optional[UCIEngine] = None
        self.mcp = FastMCP("chess-uci")

        # Register tools
        self._register_tools()

    def _register_tools(self):
        """Register MCP tools for chess engine functions."""

        @self.mcp.tool("analyze", description="Analyze a chess position specified by FEN string.")
        async def analyze(fen: str, time_ms: Optional[int] = None) -> dict[str, Any]:
            """
            Analyze a chess position.

            Args:
                fen: FEN string representation of the position
                time_ms: Time to think in milliseconds (default uses bridge setting)

            Returns:
                Analysis results
            """
            if not self.engine:
                await self._ensure_engine_started()

            # Use default time if not specified
            think_time = time_ms if time_ms is not None else self.default_think_time

            # Validate FEN
            try:
                chess.Board(fen)
            except ValueError:
                raise ValueError(f"Invalid FEN string: {fen}")

            result = await self.engine.analyze_position(fen, think_time)
            return result

        @self.mcp.tool("get_best_move", description="Get the best move for a chess position.")
        async def get_best_move(fen: Optional[str] = None, time_ms: Optional[int] = None) -> str:
            """
            Get best move for current or specified position.

            Args:
                fen: FEN string (optional, if omitted uses current position)
                time_ms: Time to think in milliseconds (default uses bridge setting)

            Returns:
                Best move in UCI format (e.g., "e2e4")
            """
            if not self.engine:
                await self._ensure_engine_started()

            # Set position if FEN is provided
            if fen:
                try:
                    chess.Board(fen)
                    await self.engine.set_position(fen)
                except ValueError:
                    raise ValueError(f"Invalid FEN string: {fen}")

            # Use default time if not specified
            think_time = time_ms if time_ms is not None else self.default_think_time

            best_move = await self.engine.get_best_move(think_time)
            return best_move

        @self.mcp.tool("set_position", description="Set the current chess position.")
        async def set_position(
            fen: Optional[str] = None, moves: Optional[list[str]] = None
        ) -> dict[str, bool]:
            """
            Set a position on the engine's internal board.

            Args:
                fen: FEN string (if None, uses starting position)
                moves: List of moves in UCI format

            Returns:
                Success status
            """
            if not self.engine:
                await self._ensure_engine_started()

            # Validate FEN if provided
            if fen:
                try:
                    chess.Board(fen)
                except ValueError:
                    raise ValueError(f"Invalid FEN string: {fen}")

            # Validate moves
            if moves and not isinstance(moves, list):
                raise ValueError("Moves must be a list of strings")

            await self.engine.set_position(fen, moves)
            return {"success": True}

        @self.mcp.tool("engine_info", description="Get information about the chess engine.")
        async def engine_info() -> dict[str, Any]:
            """
            Get engine information.

            Returns:
                Engine information
            """
            if not self.engine:
                await self._ensure_engine_started()

            return {
                "path": self.engine_path,
                "options": self.engine_options,
            }

    async def _ensure_engine_started(self):
        """Ensure the engine is started."""
        if not self.engine:
            # Create a copy of options without think_time (it's not a UCI option)
            engine_options = {k: v for k, v in self.engine_options.items() if k != "think_time"}
            self.engine = UCIEngine(self.engine_path, engine_options)
            await self.engine.start()

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
