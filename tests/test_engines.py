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


@pytest.mark.asyncio
@pytest.mark.parametrize("engine_path", ENGINES)
async def test_get_engine_id(engine_path: str) -> None:
    """Test retrieving engine identification info."""
    engine: UCIEngine = UCIEngine(engine_path)
    try:
        await engine.start()
        engine_id: dict[str, str] = engine.get_engine_id()
        assert isinstance(engine_id, dict)
        # Most UCI engines report at least a name
        assert "name" in engine_id
        assert isinstance(engine_id["name"], str)
        assert len(engine_id["name"]) > 0
    finally:
        if engine._ready:
            await engine.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("engine_path", ENGINES)
async def test_get_available_options(engine_path: str) -> None:
    """Test retrieving available UCI options with metadata."""
    engine: UCIEngine = UCIEngine(engine_path)
    try:
        await engine.start()
        options = engine.get_available_options()
        assert isinstance(options, dict)

        # Most engines have at least some options
        assert len(options) > 0

        # Check structure of an option (most engines have Hash)
        if "Hash" in options:
            hash_opt = options["Hash"]
            assert hash_opt["name"] == "Hash"
            assert hash_opt["type"] == "spin"
            assert hash_opt["min"] is not None
            assert hash_opt["max"] is not None
            assert isinstance(hash_opt["default"], int)
    finally:
        if engine._ready:
            await engine.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("engine_path", ENGINES)
async def test_set_options_runtime(engine_path: str) -> None:
    """Test setting UCI options at runtime."""
    engine: UCIEngine = UCIEngine(engine_path)
    try:
        await engine.start()
        options = engine.get_available_options()

        # Find a safe spin option to test with (Hash is common)
        if "Hash" in options:
            hash_opt = options["Hash"]
            min_val = hash_opt["min"] or 1
            # Set to minimum value to be safe
            applied, errors = await engine.set_options({"Hash": min_val})
            assert "Hash" in applied
            assert len(errors) == 0

            # Verify value is tracked
            current = engine.get_current_option_values()
            assert current.get("Hash") == min_val
    finally:
        if engine._ready:
            await engine.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("engine_path", ENGINES)
async def test_set_invalid_option_name(engine_path: str) -> None:
    """Test error handling for non-existent option names."""
    engine: UCIEngine = UCIEngine(engine_path)
    try:
        await engine.start()
        applied, errors = await engine.set_options({"NonExistentOption12345": 123})
        assert len(applied) == 0
        assert "NonExistentOption12345" in errors
        assert "not supported" in errors["NonExistentOption12345"]
    finally:
        if engine._ready:
            await engine.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("engine_path", ENGINES)
async def test_set_invalid_option_value(engine_path: str) -> None:
    """Test error handling for invalid option values."""
    engine: UCIEngine = UCIEngine(engine_path)
    try:
        await engine.start()
        options = engine.get_available_options()

        # Try to set Hash (spin type) with an invalid string value
        if "Hash" in options:
            applied, errors = await engine.set_options({"Hash": "not_a_number"})
            assert "Hash" not in applied
            assert "Hash" in errors
            assert "integer" in errors["Hash"].lower()
    finally:
        if engine._ready:
            await engine.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("engine_path", ENGINES)
async def test_set_option_out_of_range(engine_path: str) -> None:
    """Test error handling for out-of-range option values."""
    engine: UCIEngine = UCIEngine(engine_path)
    try:
        await engine.start()
        options = engine.get_available_options()

        # Try to set Hash to a value way above max
        if "Hash" in options:
            hash_opt = options["Hash"]
            if hash_opt["max"] is not None:
                way_above_max = hash_opt["max"] + 1000000
                applied, errors = await engine.set_options({"Hash": way_above_max})
                assert "Hash" not in applied
                assert "Hash" in errors
                assert "above maximum" in errors["Hash"]
    finally:
        if engine._ready:
            await engine.stop()