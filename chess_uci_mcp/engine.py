"""
Chess engine wrapper module.

This module provides functionality to interact with UCI-compatible chess engines.
"""

import logging
from typing import Any

import esca
from esca import uci

from chess_uci_mcp.types import ConfigValue, EngineId, OptionMetadata

logger = logging.getLogger(__name__)

#: Added to a search's own budget, so that waiting for the answer outlasts the search asked for.
_ANSWER_MARGIN = 10.0


def _game(fen: str | None = None, moves: list[str] | None = None) -> esca.Game:
    """
    Build a game at `fen` (the starting position if None) with `moves` played.

    Args:
        fen: FEN string of the position to start from
        moves: Moves in UCI format to play from it

    Returns:
        Game spelling castling the way engines do, e.g. "e1g1"

    Raises:
        ValueError: If the FEN or any of the moves cannot be read
    """
    game = esca.Game.from_fen(fen) if fen else esca.Game()
    game.castling_output = esca.KING_TWO_SQUARES
    for move in moves or []:
        game.play(move)
    return game


def _spell_line(game: esca.Game, moves: list[esca.Move]) -> list[str]:
    """
    Spell a line in UCI, each move read in the position it is played in.

    Args:
        game: Game whose current position the line starts from
        moves: Moves of the line, in order

    Returns:
        Moves in UCI format, cut short at one that cannot be played
    """
    walk = esca.Game.from_position(game.position, variant=game.variant)
    walk.castling_output = esca.KING_TWO_SQUARES
    line: list[str] = []
    for move in moves:
        line.append(walk.move_to_uci(move))
        try:
            walk.play(move)
        except ValueError:
            break
    return line


def _coerce(option: uci.Option, value: Any) -> ConfigValue:
    """
    Read `value` as a value of the option's own type.

    Args:
        option: Option the value is meant for
        value: Value as given, possibly as text

    Returns:
        Value of the type the option declared
    """
    if option.type == "check":
        return value if isinstance(value, bool) else str(value).strip().lower() not in ("false", "0", "")
    if option.type == "spin":
        return value if isinstance(value, int) and not isinstance(value, bool) else int(str(value))
    if option.type == "button":
        return None
    return str(value)


class UCIEngine:
    """A wrapper for UCI chess engines."""

    def __init__(self, engine_path: str, options: dict[str, Any] | None = None):
        """
        Initialize UCI engine wrapper.

        Args:
            engine_path: Path to the UCI engine executable
            options: Dictionary of engine options to set
        """
        self.engine_path = engine_path
        self.options = options or {}
        self.engine: uci.AsyncEngine | None = None
        self._ready = False
        self._current_option_values: dict[str, ConfigValue] = {}
        self._current_fen: str | None = None
        self._current_moves: list[str] = []

    async def start(self) -> None:
        """
        Start the engine process.

        Raises:
            RuntimeError: If the engine fails to start
        """
        logger.info("Starting engine: %s", self.engine_path)
        engine = uci.AsyncEngine(self.engine_path)
        try:
            await engine.handshake()
            await engine.new_game()

            for name, value in self.options.items():
                option = self._declared(name, engine)
                if option is None:
                    logger.warning("Engine does not support option '%s'. Ignoring.", name)
                    continue
                logger.info("Setting engine option: %s = %s", name, value)
                coerced = _coerce(option, value)
                await engine.set_option(option.name, coerced)
                self._current_option_values[name] = coerced
            if self._current_option_values:
                await engine.is_ready()

            self.engine = engine
            self._ready = True
            logger.info("Engine %s started and ready", self.engine_path)
        except Exception as e:
            logger.error("Failed to start engine: %s", e)
            engine.kill()
            self.engine = None
            raise RuntimeError(f"Failed to start engine: {e}") from e

    async def stop(self) -> None:
        """Stop the engine process."""
        if self.engine:
            logger.info("Stopping engine: %s", self.engine_path)
            try:
                await self.engine.quit()
            except Exception as e:
                logger.error("Error during engine shutdown: %s", e)
            finally:
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

        game = _game(fen)
        seconds = time_ms / 1000
        lines = await self.engine.analyse(
            game,
            uci.Limits(movetime=seconds),
            timeout=seconds + _ANSWER_MARGIN,
        )
        if not lines:
            return {"depth": 0, "score": None, "pv": [], "best_move": None}

        best = lines[0]
        pv = _spell_line(game, best.pv)
        return {
            "depth": best.depth if best.depth is not None else 0,
            "score": self._format_score(best, game.position.side_to_move),
            "pv": pv,
            "best_move": pv[0] if pv else None,
        }

    async def set_position(self, fen: str | None = None, moves: list[str] | None = None) -> None:
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

        game = _game(self._current_fen, self._current_moves)
        seconds = time_ms / 1000
        answer = await self.engine.play(
            game,
            uci.Limits(movetime=seconds),
            timeout=seconds + _ANSWER_MARGIN,
        )
        return game.move_to_uci(answer.best) if answer.best else ""

    def _format_score(self, info: uci.Info, side_to_move: str) -> float | str | None:
        """
        Format the score of a search report from White's point of view.

        Args:
            info: Report carrying the score
            side_to_move: Side the score is reported for, "w" or "b"

        Returns:
            Pawns as a float, "mateN" for a forced mate, or None if unscored
        """
        sign = 1 if side_to_move == "w" else -1

        if info.mate is not None:
            return f"mate{sign * info.mate}"

        if info.cp is not None:
            return sign * info.cp / 100.0

        return None

    def get_engine_id(self) -> EngineId:
        """
        Get the engine identification info.

        Returns:
            Dictionary with engine ID info (typically 'name', 'author')

        Raises:
            RuntimeError: If the engine is not started
        """
        if not self.engine or not self._ready:
            raise RuntimeError("Engine not started")

        engine_id: EngineId = {}
        if self.engine.name is not None:
            engine_id["name"] = self.engine.name
        if self.engine.author is not None:
            engine_id["author"] = self.engine.author
        return engine_id

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
                "var": list(option.vars) if option.vars else None,
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

    async def set_options(self, options: dict[str, ConfigValue]) -> tuple[dict[str, ConfigValue], dict[str, str]]:
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

        for name, value in options.items():
            option = self._declared(name)
            if option is None:
                errors[name] = f"Option '{name}' is not supported by this engine"
                continue

            # Validate the value based on option type
            validation_error = self._validate_option_value(option, value)
            if validation_error:
                errors[name] = validation_error
                continue

            try:
                await self.engine.set_option(option.name, value)
            except ValueError as e:
                errors[name] = str(e)
                continue

            applied[name] = value
            logger.info("Set engine option: %s = %s", name, value)

        if applied:
            self._current_option_values.update(applied)
            await self.engine.is_ready()

        return applied, errors

    def _declared(self, name: str, engine: uci.AsyncEngine | None = None) -> uci.Option | None:
        """
        Find an option the engine offers, matched without regard to case.

        Args:
            name: Option name as the caller spelled it
            engine: Engine to ask, the started one by default

        Returns:
            The option, or None if the engine offers no such one
        """
        engine = engine if engine is not None else self.engine
        if engine is None:
            return None
        for option in engine.options.values():
            if option.name.lower() == name.lower():
                return option
        return None

    def _validate_option_value(self, option: uci.Option, value: ConfigValue) -> str | None:
        """
        Validate an option value against its constraints.

        Args:
            option: Option the value is meant for
            value: Value to validate

        Returns:
            Error message if invalid, None if valid
        """
        if option.type == "check":
            if not isinstance(value, bool):
                return f"Expected boolean value for check option, got {type(value).__name__}"
        elif option.type == "spin":
            if not isinstance(value, int) or isinstance(value, bool):
                return f"Expected integer value for spin option, got {type(value).__name__}"
            if option.min is not None and value < option.min:
                return f"Value {value} is below minimum {option.min}"
            if option.max is not None and value > option.max:
                return f"Value {value} is above maximum {option.max}"
        elif option.type == "combo":
            if option.vars and value not in option.vars:
                return f"Value '{value}' not in allowed values: {option.vars}"
        elif option.type == "string" and not isinstance(value, str | None):
            return f"Expected string value for string option, got {type(value).__name__}"
        # 'button' type triggers an action, doesn't take a persistent value

        return None
