"""
Chess engine wrapper module.

This module provides functionality to interact with UCI-compatible chess engines.
"""

import logging
from typing import Any, Optional

import chess.engine

from chess_uci_mcp.types import ConfigValue, OptionMetadata

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
        self._current_option_values: dict[str, ConfigValue] = {}

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
                supported_options = self.engine.options
                configurable_options = {}
                for name, value in self.options.items():
                    if name in supported_options:
                        configurable_options[name] = value
                        logger.info("Setting engine option: %s = %s", name, value)
                    else:
                        logger.warning("Engine does not support option '%s'. Ignoring.", name)

                if configurable_options:
                    await self.engine.configure(configurable_options)
                    self._current_option_values.update(configurable_options)

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

    def get_engine_id(self) -> dict[str, str]:
        """
        Get the engine identification info.

        Returns:
            Dictionary with engine ID info (typically 'name', 'author')

        Raises:
            RuntimeError: If the engine is not started
        """
        if not self.engine or not self._ready:
            raise RuntimeError("Engine not started")
        return dict(self.engine.id)

    def get_available_options(self) -> dict[str, OptionMetadata]:
        """
        Get all available UCI options with their metadata.

        Returns:
            Dictionary mapping option names to their metadata

        Raises:
            RuntimeError: If the engine is not started
        """
        if not self.engine or not self._ready:
            raise RuntimeError("Engine not started")

        options: dict[str, OptionMetadata] = {}
        for name, option in self.engine.options.items():
            options[name] = {
                "name": option.name,
                "type": option.type,
                "default": option.default,
                "min": option.min,
                "max": option.max,
                "var": list(option.var) if option.var else None,
            }
        return options

    def get_current_option_values(self) -> dict[str, ConfigValue]:
        """
        Get current values for all configured options.

        Note: Returns values that were explicitly set. Options not set
        use their defaults (available in option metadata).

        Returns:
            Dictionary mapping option names to their current values
        """
        return dict(self._current_option_values)

    async def set_options(
        self, options: dict[str, ConfigValue]
    ) -> tuple[dict[str, ConfigValue], dict[str, str]]:
        """
        Set one or more UCI options at runtime.

        Args:
            options: Dictionary of option names to values

        Returns:
            Tuple of (successfully_applied, errors)

        Raises:
            RuntimeError: If the engine is not started
        """
        if not self.engine or not self._ready:
            raise RuntimeError("Engine not started")

        applied: dict[str, ConfigValue] = {}
        errors: dict[str, str] = {}
        supported_options = self.engine.options

        for name, value in options.items():
            if name not in supported_options:
                errors[name] = f"Option '{name}' is not supported by this engine"
                continue

            # Validate the value based on option type
            option_meta = supported_options[name]
            validation_error = self._validate_option_value(option_meta, value)
            if validation_error:
                errors[name] = validation_error
                continue

            applied[name] = value

        if applied:
            await self.engine.configure(applied)
            self._current_option_values.update(applied)
            for name, value in applied.items():
                logger.info("Set engine option: %s = %s", name, value)

        return applied, errors

    def _validate_option_value(self, option: Any, value: ConfigValue) -> Optional[str]:
        """
        Validate an option value against its constraints.

        Args:
            option: Option object from python-chess
            value: Value to validate

        Returns:
            Error message if invalid, None if valid
        """
        if option.type == "check":
            if not isinstance(value, bool):
                return f"Expected boolean value for check option, got {type(value).__name__}"
        elif option.type == "spin":
            if not isinstance(value, int):
                return f"Expected integer value for spin option, got {type(value).__name__}"
            if option.min is not None and value < option.min:
                return f"Value {value} is below minimum {option.min}"
            if option.max is not None and value > option.max:
                return f"Value {value} is above maximum {option.max}"
        elif option.type == "combo":
            if option.var and value not in option.var:
                return f"Value '{value}' not in allowed values: {option.var}"
        elif option.type == "string":
            if not isinstance(value, (str, type(None))):
                return f"Expected string value for string option, got {type(value).__name__}"
        # 'button' type triggers an action, doesn't take a persistent value

        return None
