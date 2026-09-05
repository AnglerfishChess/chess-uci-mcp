import shutil
from typing import Any, Final

import esca
import pytest

from chess_uci_mcp.engine import UCIEngine, _game, _spell_line
from chess_uci_mcp.server import ChessUCIBridge

# We use list[Any] because the return type of pytest.param, `ParameterSet`,
# is not a public type.
ENGINES: list[Any] = []

#: Of those, the ones that report a forced mate as `mate N`. A neural engine reads its
#: value head in pawns and says `cp` all the way to mate, so `mateN` is not its to give.
MATE_SCORING_ENGINES: list[Any] = []

STOCKFISH_PATH: Final[str | None] = shutil.which("stockfish")
if STOCKFISH_PATH:
    ENGINES.append(pytest.param(STOCKFISH_PATH, id="stockfish"))
    MATE_SCORING_ENGINES.append(pytest.param(STOCKFISH_PATH, id="stockfish"))

LC0_PATH: Final[str | None] = shutil.which("lc0")
if LC0_PATH:
    ENGINES.append(pytest.param(LC0_PATH, id="lc0"))

# Skip all tests in this file if no engines are found
if not ENGINES:
    pytest.skip("No supported chess engines (stockfish, lc0) found in PATH", allow_module_level=True)

#: The standard array.
START_FEN: Final[str] = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

#: Black to move, a queen up: White's queen is missing from d1.
BLACK_A_QUEEN_UP: Final[str] = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR b KQkq - 0 1"

#: White to move, Ra8 mates on the back rank.
WHITE_MATES_IN_ONE: Final[str] = "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1"

#: Black to move, Ra1 mates on the back rank.
BLACK_MATES_IN_ONE: Final[str] = "r5k1/8/8/8/8/8/5PPP/6K1 b - - 0 1"

#: Giuoco Piano, White free to castle either way.
WHITE_MAY_CASTLE: Final[str] = "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 6 5"

#: Kings and rooks alone, Black free to castle either way.
BLACK_MAY_CASTLE: Final[str] = "r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1"


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
        analysis: dict[str, Any] = await engine.analyze_position(fen=START_FEN, time_ms=100)
        assert isinstance(analysis, dict)
        assert "best_move" in analysis
        assert "score" in analysis
        assert "pv" in analysis
        assert isinstance(analysis["pv"], list)

        # Test getting best move
        # First set position
        await engine.set_position(fen=START_FEN)
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
        engine_id = engine.get_engine_id()
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


@pytest.mark.asyncio
@pytest.mark.parametrize("engine_path", ENGINES)
async def test_score_is_from_whites_point_of_view(engine_path: str) -> None:
    """A position Black is winning scores negative, whichever side is to move."""
    engine: UCIEngine = UCIEngine(engine_path)
    try:
        await engine.start()
        analysis = await engine.analyze_position(fen=BLACK_A_QUEEN_UP, time_ms=500)
        score = analysis["score"]
        assert isinstance(score, float)
        # A whole queen down is worth far more than a pawn to any engine.
        assert score < -1.0
    finally:
        if engine._ready:
            await engine.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("engine_path", MATE_SCORING_ENGINES)
@pytest.mark.parametrize(
    ("fen", "expected"),
    [
        pytest.param(WHITE_MATES_IN_ONE, "mate1", id="white-mates"),
        pytest.param(BLACK_MATES_IN_ONE, "mate-1", id="black-mates"),
    ],
)
async def test_mate_score_formatting(engine_path: str, fen: str, expected: str) -> None:
    """A forced mate reads as "mateN", counted from White's point of view."""
    engine: UCIEngine = UCIEngine(engine_path)
    try:
        await engine.start()
        analysis = await engine.analyze_position(fen=fen, time_ms=500)
        assert analysis["score"] == expected
    finally:
        if engine._ready:
            await engine.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("engine_path", ENGINES)
async def test_moves_are_applied_to_the_position(engine_path: str) -> None:
    """A move list moves the game on: the answer is legal for the side left to move."""
    moves = ["e2e4", "e7e5", "g1f3"]

    engine: UCIEngine = UCIEngine(engine_path)
    try:
        await engine.start()
        await engine.set_position(fen=None, moves=moves)
        best_move = await engine.get_best_move(time_ms=200)

        game = _game(None, moves)
        assert game.position.side_to_move == "b"
        assert best_move in [game.move_to_uci(move) for move in game.legal_moves()]
    finally:
        if engine._ready:
            await engine.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("engine_path", ENGINES)
async def test_pv_replays_from_the_position_analysed(engine_path: str) -> None:
    """Every move of the principal variation can be played, in the order reported."""
    engine: UCIEngine = UCIEngine(engine_path)
    try:
        await engine.start()
        analysis = await engine.analyze_position(fen=WHITE_MAY_CASTLE, time_ms=500)

        game = esca.Game.from_fen(WHITE_MAY_CASTLE)
        for move in analysis["pv"]:
            game.play(move)
    finally:
        if engine._ready:
            await engine.stop()


@pytest.mark.parametrize(
    ("fen", "king_to_rook", "king_two_squares"),
    [
        pytest.param(WHITE_MAY_CASTLE, "e1h1", "e1g1", id="white-short"),
        pytest.param(BLACK_MAY_CASTLE, "e8h8", "e8g8", id="black-short"),
        pytest.param(BLACK_MAY_CASTLE, "e8a8", "e8c8", id="black-long"),
    ],
)
def test_castling_is_spelled_king_two_squares(fen: str, king_to_rook: str, king_two_squares: str) -> None:
    """Castling reads the way engines write it: the king moving two squares."""
    game = _game(fen)
    castling = next(move for move in game.legal_moves() if move.is_castling and move.uci == king_to_rook)

    assert game.move_to_uci(castling) == king_two_squares
    assert _spell_line(game, [castling]) == [king_two_squares]


@pytest.mark.asyncio
@pytest.mark.parametrize("engine_path", ENGINES)
@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        pytest.param("analyze", {"fen": "not a fen", "time_ms": 100}, id="analyze"),
        pytest.param("get_best_move", {"fen": "not a fen", "time_ms": 100}, id="get_best_move"),
        pytest.param("set_position", {"fen": "not a fen"}, id="set_position"),
    ],
)
async def test_invalid_fen_is_rejected(engine_path: str, tool: str, arguments: dict[str, Any]) -> None:
    """An unreadable FEN is refused by name."""
    bridge = ChessUCIBridge(engine_path)
    try:
        with pytest.raises(Exception, match="Invalid FEN string: not a fen"):
            await bridge.mcp.call_tool(tool, arguments)
    finally:
        await bridge.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("engine_path", ENGINES)
async def test_bridge_offers_its_six_tools(engine_path: str) -> None:
    """The bridge registers the whole command set and drives the engine through it."""
    bridge = ChessUCIBridge(engine_path, think_time=200)
    try:
        tools = await bridge.mcp.list_tools()
        assert {tool.name for tool in tools} == {
            "analyze",
            "get_best_move",
            "set_position",
            "engine_info",
            "get_engine_options",
            "set_engine_options",
        }

        assert await bridge.mcp.call_tool("set_position", {"moves": ["e2e4"]})
        assert await bridge.mcp.call_tool("engine_info", {})
    finally:
        await bridge.stop()
