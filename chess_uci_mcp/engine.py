"""
Chess engine wrapper module.

This module provides functionality to interact with UCI-compatible chess engines.
"""

import logging
from typing import Any, Optional

import chess.engine

logger = logging.getLogger(__name__)


class UCIEngine:
    """A wrapper for UCI chess engines using python-chess."""

    def __init__(self, engine_path: str, options: Optional[dict[str, Any]] = None):
        """
        Initialize UCI engine wrapper.

        Args:
            engine_path: Path to the UCI engine executable
            options: Dictionary of engine options to set
        """
        self.engine_path = engine_path
        self.options = options or {}
        self.transport = None
        self.engine = None
        self._ready = False

    async def start(self) -> None:
        """
        Start the engine process.

        Raises:
            RuntimeError: If the engine fails to start
        """
        logger.info("Starting engine: %s", self.engine_path)
        try:
            # Start the engine process
            self.transport, self.engine = await chess.engine.popen_uci(self.engine_path)

            # Configure engine options
            if self.options:
                await self.engine.configure(self.options)

            self._ready = True
            logger.info("Engine %s started and ready", self.engine_path)
        except Exception as e:
            logger.error("Failed to start engine: %s", e)
            if self.transport and self.engine:
                await self.engine.quit()
                self.transport = None
                self.engine = None
            raise RuntimeError(f"Failed to start engine: {e}")

    async def stop(self) -> None:
        """Stop the engine process."""
        if self.engine:
            logger.info("Stopping engine: %s", self.engine_path)
            try:
                await self.engine.quit()
            except Exception as e:
                logger.error("Error during engine shutdown: %s", e)
            finally:
                self.transport = None
                self.engine = None
                self._ready = False

    async def analyze_position(self, fen: str, time_ms: int = 1000) -> dict[str, Any]:
        """
        Analyze a chess position and return the best move and evaluation.

        Args:
            fen: FEN string representation of the position
            time_ms: Time to think in milliseconds

        Returns:
            Dictionary containing analysis results

        Raises:
            RuntimeError: If the engine is not started
        """
        if not self.engine or not self._ready:
            raise RuntimeError("Engine not started")

        # Create a board from the FEN string
        board = chess.Board(fen)

        # Set time limit for analysis
        limit = chess.engine.Limit(time=time_ms / 1000)

        # Run analysis
        info = await self.engine.analyse(board, limit)

        # Format the result
        result = {
            "depth": info.get("depth", 0),
            "score": self._format_score(info.get("score")),
            "pv": [move.uci() for move in info.get("pv", [])],
            "best_move": info.get("pv", [None])[0].uci() if info.get("pv") else None,
        }

        return result

    async def set_position(
        self, fen: Optional[str] = None, moves: Optional[list[str]] = None
    ) -> None:
        """
        Set a position on the engine's internal board.

        Args:
            fen: FEN string (if None, uses starting position)
            moves: List of moves in UCI format

        Raises:
            RuntimeError: If the engine is not started
        """
        if not self.engine or not self._ready:
            raise RuntimeError("Engine not started")

        # This method doesn't do anything directly with python-chess
        # as the engine state is managed internally by the chess.engine module.
        # Position will be set when get_best_move or analyze_position is called.

        # Store the position information for later use
        self._current_fen = fen
        self._current_moves = moves or []
        logger.debug("Position set: FEN=%s, Moves=%s", fen or "startpos", moves)

    async def get_best_move(self, time_ms: int = 1000) -> str:
        """
        Calculate the best move from the current position.

        Args:
            time_ms: Time to think in milliseconds

        Returns:
            Best move in UCI format (e.g., "e2e4")

        Raises:
            RuntimeError: If the engine is not started
        """
        if not self.engine or not self._ready:
            raise RuntimeError("Engine not started")

        # Create a board
        board = (
            chess.Board(self._current_fen)
            if hasattr(self, "_current_fen") and self._current_fen
            else chess.Board()
        )

        # Apply moves if any
        if hasattr(self, "_current_moves") and self._current_moves:
            for move_uci in self._current_moves:
                board.push_uci(move_uci)

        # Set time limit
        limit = chess.engine.Limit(time=time_ms / 1000)

        # Get best move
        result = await self.engine.play(board, limit)

        # Return the move in UCI format
        return result.move.uci() if result.move else ""

    def _format_score(self, score: Optional[chess.engine.PovScore]) -> Optional[Any]:
        """
        Format the score from the engine analysis.

        Args:
            score: PovScore object from python-chess

        Returns:
            Formatted score value
        """
        if score is None:
            return None

        # Get score from white's perspective
        white_score = score.white()

        # Check if it's a mate score
        if white_score.is_mate():
            mate_in = white_score.mate()
            return f"mate{mate_in}" if mate_in is not None else None

        # Return centipawn score as a float
        if white_score.score() is not None:
            return white_score.score() / 100.0

        return None
