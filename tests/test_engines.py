import pytest
import shutil
import chess
from chess_uci_mcp.engine import UCIEngine
from typing import Any, Optional, Final

# We use list[Any] because the return type of pytest.param, `ParameterSet`,
# is not a public type.
ENGINES: list[Any] = []

STOCKFISH_PATH: Final[Optional[str]] = shutil.which("stockfish")
if STOCKFISH_PATH:
    ENGINES.append(pytest.param(STOCKFISH_PATH, id="stockfish"))

LC0_PATH: Final[Optional[str]] = shutil.which("lc0")
if LC0_PATH:
    ENGINES.append(pytest.param(LC0_PATH, id="lc0"))

# Skip all tests in this file if no engines are found
if not ENGINES:
    pytest.skip("No supported chess engines (stockfish, lc0) found in PATH", allow_module_level=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("engine_path", ENGINES)
async def test_uci_engine_wrapper_sanity(engine_path: str) -> None:
    """
    Tests the basic functionality of the UCIEngine wrapper.
    - Starts the engine.
    - Analyzes the starting position.
    - Gets the best move from the starting position.
    - Stops the engine.
    """
    engine: UCIEngine = UCIEngine(engine_path)
    try:
        await engine.start()
        assert engine._ready is True

        # Test analysis
        start_fen: str = chess.STARTING_FEN
        analysis: dict[str, Any] = await engine.analyze_position(fen=start_fen, time_ms=100)
        assert isinstance(analysis, dict)
        assert "best_move" in analysis
        assert "score" in analysis
        assert "pv" in analysis
        assert isinstance(analysis["pv"], list)

        # Test getting best move
        # First set position
        await engine.set_position(fen=start_fen)
        best_move: str = await engine.get_best_move(time_ms=100)
        assert isinstance(best_move, str)
        # A valid UCI move is at least 4 chars long (e.g., 'e2e4')
        assert len(best_move) >= 4

    finally:
        if engine._ready:
            await engine.stop()
        assert engine._ready is False