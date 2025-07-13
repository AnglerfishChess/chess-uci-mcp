#!/usr/bin/env python3
"""
Entry point for the Chess UCI MCP server.

This module provides the main CLI interface for starting and configuring the server.
"""

import asyncio
import logging
import sys

import click

from chess_uci_mcp.server import ChessUCIBridge

logger = logging.getLogger("chess_uci_mcp")


async def run_bridge(engine_path: str, uci_options: dict[str, str], think_time: int) -> None:
    """Asynchronously run and manage the ChessUCIBridge."""
    bridge = ChessUCIBridge(engine_path, think_time=think_time, options=uci_options)
    try:
        await bridge.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down")
    finally:
        logger.info("Shutting down bridge")
        await bridge.stop()


@click.command()
@click.argument("engine_path", type=click.Path(exists=True))
@click.option(
    "--uci-option",
    "-o",
    multiple=True,
    type=(str, str),
    metavar="NAME VALUE",
    help="Set a UCI option (e.g., -o Threads 4)",
)
@click.option("--think-time", default=1000, type=int, help="Default thinking time in ms")
@click.option("--debug/--no-debug", default=False, help="Enable debug logging")
def main(
    engine_path: str,
    uci_option: list[tuple[str, str]],
    think_time: int = 1000,
    debug: bool = False,
) -> None:
    """
    Start the Chess UCI MCP server with a specified engine.

    ENGINE_PATH is the path to the UCI-compatible chess engine executable.
    """
    # Configure logging
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,  # Ensure logs go to stderr, not stdout
    )
    # Configure root logger
    logging.getLogger().setLevel(log_level)

    # Convert uci_option list of tuples to a dictionary
    uci_options = dict(uci_option)

    # Output startup information to logs instead of stdout
    logger.info("Starting Chess UCI MCP bridge")
    logger.info("Engine path: %s", engine_path)
    logger.info("Think time: %d ms", think_time)
    for name, value in uci_options.items():
        logger.info("UCI Option: %s = %s", name, value)

    # Run the bridge
    try:
        asyncio.run(run_bridge(engine_path, uci_options, think_time))
    except Exception:
        logger.exception("Error running bridge")
        sys.exit(1)


if __name__ == "__main__":
    main()
