"""
Chess engine wrapper module.

This module provides functionality to interact with UCI-compatible chess engines.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


class UCIEngine:
    """A wrapper for UCI chess engines."""

    def __init__(self, engine_path: str, options: Optional[Dict[str, Any]] = None):
        """
        Initialize UCI engine wrapper.

        Args:
            engine_path: Path to the UCI engine executable
            options: Dictionary of engine options to set
        """
        self.engine_path = Path(engine_path)
        self.options = options or {}
        self.process: Optional[asyncio.subprocess.Process] = None
        self._ready = False

    async def start(self) -> None:
        """
        Start the engine process.

        Raises:
            FileNotFoundError: If the engine executable is not found
            RuntimeError: If the engine fails to start
        """
        if not self.engine_path.exists():
            raise FileNotFoundError(f"Engine not found at {self.engine_path}")

        logger.info(f"Starting engine: {self.engine_path}")
        try:
            self.process = await asyncio.create_subprocess_exec(
                str(self.engine_path),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Initialize UCI mode
            await self._send_command("uci")
            await self._wait_for_uciok()

            # Set options
            for name, value in self.options.items():
                await self._send_command(f"setoption name {name} value {value}")

            # Indicate that the engine is ready
            await self._send_command("isready")
            await self._wait_for_readyok()

            self._ready = True
            logger.info(f"Engine {self.engine_path} started and ready")
        except Exception as e:
            logger.error(f"Failed to start engine: {e}")
            if self.process:
                self.process.terminate()
                self.process = None
            raise RuntimeError(f"Failed to start engine: {e}")

    async def stop(self) -> None:
        """Stop the engine process."""
        if self.process:
            logger.info(f"Stopping engine: {self.engine_path}")
            try:
                await self._send_command("quit")
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    logger.warning(f"Engine {self.engine_path} did not exit, terminating")
                    self.process.terminate()
                    await self.process.wait()
            except Exception as e:
                logger.error(f"Error during engine shutdown: {e}")
                if self.process:
                    self.process.terminate()
            finally:
                self.process = None
                self._ready = False

    async def analyze_position(self, fen: str, time_ms: int = 1000) -> Dict[str, Any]:
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
        if not self.process or not self._ready:
            raise RuntimeError("Engine not started")

        # Set position
        await self._send_command(f"position fen {fen}")

        # Start analysis
        await self._send_command(f"go movetime {time_ms}")

        # Collect and parse output
        analysis_result = await self._collect_analysis(time_ms)
        return analysis_result

    async def set_position(
        self, fen: Optional[str] = None, moves: Optional[List[str]] = None
    ) -> None:
        """
        Set a position on the engine's internal board.

        Args:
            fen: FEN string (if None, uses starting position)
            moves: List of moves in UCI format

        Raises:
            RuntimeError: If the engine is not started
        """
        if not self.process or not self._ready:
            raise RuntimeError("Engine not started")

        cmd = "position"
        if fen:
            cmd += f" fen {fen}"
        else:
            cmd += " startpos"

        if moves and len(moves) > 0:
            cmd += " moves " + " ".join(moves)

        await self._send_command(cmd)

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
        if not self.process or not self._ready:
            raise RuntimeError("Engine not started")

        await self._send_command(f"go movetime {time_ms}")

        best_move = await self._wait_for_bestmove()
        return best_move

    async def _send_command(self, command: str) -> None:
        """
        Send a command to the engine.

        Args:
            command: UCI command string
        """
        if not self.process or not self.process.stdin:
            raise RuntimeError("Engine process not available")

        logger.debug(f"Sending command: {command}")
        cmd_bytes = (command + "\n").encode("utf-8")
        self.process.stdin.write(cmd_bytes)
        await self.process.stdin.drain()

    async def _read_line(self) -> str:
        """
        Read a line from the engine output.

        Returns:
            Line of text from the engine
        """
        if not self.process or not self.process.stdout:
            raise RuntimeError("Engine process not available")

        line = await self.process.stdout.readline()
        result = line.decode("utf-8").strip()
        logger.debug(f"Engine output: {result}")
        return result

    async def _wait_for_uciok(self) -> None:
        """Wait for the engine to send 'uciok'."""
        while True:
            line = await self._read_line()
            if line == "uciok":
                return

    async def _wait_for_readyok(self) -> None:
        """Wait for the engine to send 'readyok'."""
        while True:
            line = await self._read_line()
            if line == "readyok":
                return

    async def _wait_for_bestmove(self) -> str:
        """
        Wait for the engine to send the best move.

        Returns:
            Best move in UCI format
        """
        while True:
            line = await self._read_line()
            if line.startswith("bestmove "):
                parts = line.split()
                if len(parts) >= 2:
                    return parts[1]

    async def _collect_analysis(self, timeout_ms: int) -> Dict[str, Any]:
        """
        Collect analysis information from engine output.

        Args:
            timeout_ms: Timeout in milliseconds

        Returns:
            Dictionary with analysis data
        """
        result = {
            "depth": 0,
            "score": None,
            "pv": [],
            "best_move": None,
        }

        # Set a timeout slightly longer than the requested thinking time
        timeout = timeout_ms / 1000 + 0.5

        end_time = asyncio.get_event_loop().time() + timeout

        while True:
            # Check if we've exceeded the timeout
            remaining = end_time - asyncio.get_event_loop().time()
            if remaining <= 0:
                break

            try:
                line = await asyncio.wait_for(self._read_line(), timeout=remaining)

                # Parse the line
                if line.startswith("bestmove "):
                    parts = line.split()
                    if len(parts) >= 2:
                        result["best_move"] = parts[1]
                    break

                elif line.startswith("info "):
                    self._parse_info_line(line, result)

            except asyncio.TimeoutError:
                break

        return result

    def _parse_info_line(self, line: str, result: Dict[str, Any]) -> None:
        """
        Parse an info line from the engine.

        Args:
            line: Info line from the engine
            result: Result dictionary to update
        """
        parts = line.split()
        i = 1  # Skip "info"

        while i < len(parts):
            if parts[i] == "depth" and i + 1 < len(parts):
                try:
                    depth = int(parts[i + 1])
                    if depth > result["depth"]:
                        result["depth"] = depth
                    i += 2
                except ValueError:
                    i += 2

            elif parts[i] == "score" and i + 2 < len(parts):
                score_type = parts[i + 1]
                try:
                    if score_type == "cp":
                        result["score"] = int(parts[i + 2]) / 100.0
                    elif score_type == "mate":
                        mate_in = int(parts[i + 2])
                        result["score"] = "mate" + str(mate_in)
                    i += 3
                except ValueError:
                    i += 3

            elif parts[i] == "pv" and i + 1 < len(parts):
                # Collect the PV (principal variation)
                pv = []
                i += 1
                while i < len(parts) and parts[i] not in ["depth", "score", "time"]:
                    pv.append(parts[i])
                    i += 1
                if len(pv) > 0:
                    result["pv"] = pv

            else:
                i += 1
