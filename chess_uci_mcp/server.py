"""
MCP server module for chess engine integration.

This module implements the MCP server that provides access to UCI chess engines.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

import chess
from mcp import Server, Handler  # Changed from MCPServer, MCPHandler

from chess_uci_mcp.config import Config
from chess_uci_mcp.engine import UCIEngine

logger = logging.getLogger(__name__)


class ChessEngineServer:
    """MCP Server for UCI chess engines."""

    def __init__(self, config: Config):
        """
        Initialize the chess engine MCP server.

        Args:
            config: Server configuration
        """
        self.config = config
        self.engine: Optional[UCIEngine] = None
        self.server: Optional[Server] = None  # Changed from MCPServer
        self.stop_event = asyncio.Event()

    async def start(self) -> None:
        """
        Start the server and chess engine.

        Raises:
            RuntimeError: If server fails to start
        """
        try:
            # Initialize the chess engine
            self.engine = UCIEngine(self.config.engine.path, self.config.engine.options)
            await self.engine.start()

            # Create MCP server and add handlers
            handler = ChessEngineHandler(self.engine, self.config)
            self.server = Server(  # Changed from MCPServer
                host=self.config.server.host,
                port=self.config.server.port,
            )
            self.server.add_handler("chess", handler)

            # Start the server
            await self.server.start()
            actual_port = self.server.port

            logger.info(f"Chess UCI MCP server started on {self.config.server.host}:{actual_port}")
            logger.info(
                f"Connected to engine: {self.config.engine.name} at {self.config.engine.path}"
            )

            # Wait until stop is requested
            await self.stop_event.wait()

        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            await self.stop()
            raise RuntimeError(f"Failed to start server: {e}")

    async def stop(self) -> None:
        """Stop the server and chess engine."""
        logger.info("Stopping Chess UCI MCP server")

        # Stop the engine
        if self.engine:
            await self.engine.stop()
            self.engine = None

        # Stop the server
        if self.server:
            await self.server.stop()
            self.server = None

        # Set the stop event
        self.stop_event.set()


class ChessEngineHandler(Handler):  # Changed from MCPHandler
    """MCP handler for chess engine commands."""

    def __init__(self, engine: UCIEngine, config: Config):
        """
        Initialize the chess engine handler.

        Args:
            engine: UCI engine instance
            config: Server configuration
        """
        super().__init__()
        self.engine = engine
        self.config = config

    async def handle_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle an MCP request.

        Args:
            method: Method name
            params: Method parameters

        Returns:
            Dictionary with response data

        Raises:
            Exception: If the method is not supported or an error occurs
        """
        logger.debug(f"Received request: {method} with params: {params}")

        try:
            if method == "analyze":
                return await self._handle_analyze(params)
            elif method == "get_best_move":
                return await self._handle_get_best_move(params)
            elif method == "set_position":
                return await self._handle_set_position(params)
            elif method == "engine_info":
                return await self._handle_engine_info(params)
            else:
                raise ValueError(f"Unsupported method: {method}")
        except Exception as e:
            logger.error(f"Error handling request {method}: {e}")
            raise

    async def _handle_analyze(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle analysis request.

        Args:
            params: Request parameters, must include 'fen'

        Returns:
            Analysis results
        """
        # Get FEN string
        fen = params.get("fen")
        if not fen:
            raise ValueError("Missing required parameter 'fen'")

        # Validate FEN
        try:
            chess.Board(fen)
        except ValueError:
            raise ValueError(f"Invalid FEN string: {fen}")

        # Get think time
        think_time = params.get("time_ms", self.config.default_think_time)

        # Analyze position
        result = await self.engine.analyze_position(fen, think_time)

        return {"result": result}

    async def _handle_get_best_move(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle best move request.

        Args:
            params: Request parameters

        Returns:
            Best move information
        """
        # If FEN is provided, set the position first
        fen = params.get("fen")
        if fen:
            try:
                chess.Board(fen)
                await self.engine.set_position(fen)
            except ValueError:
                raise ValueError(f"Invalid FEN string: {fen}")

        # Get think time
        think_time = params.get("time_ms", self.config.default_think_time)

        # Get best move
        best_move = await self.engine.get_best_move(think_time)

        return {"move": best_move}

    async def _handle_set_position(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle set position request.

        Args:
            params: Request parameters

        Returns:
            Success status
        """
        # Get FEN and moves
        fen = params.get("fen")
        moves = params.get("moves")

        # Validate FEN if provided
        if fen:
            try:
                chess.Board(fen)
            except ValueError:
                raise ValueError(f"Invalid FEN string: {fen}")

        # Validate moves if provided
        if moves and not isinstance(moves, list):
            raise ValueError("Moves must be a list")

        # Set position
        await self.engine.set_position(fen, moves)

        return {"success": True}

    async def _handle_engine_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle engine info request.

        Args:
            params: Request parameters (unused)

        Returns:
            Engine information
        """
        return {
            "name": self.config.engine.name,
            "path": self.config.engine.path,
            "options": self.config.engine.options,
        }
