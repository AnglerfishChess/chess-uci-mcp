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

@click.command()
@click.argument("engine_path", type=click.Path(exists=True))
@click.option("--threads", "-t", default=4, type=int, help="Number of engine threads to use")
@click.option("--hash", default=128, type=int, help="Hash table size in MB")
@click.option("--think-time", default=1000, type=int, help="Default thinking time in ms")
@click.option("--debug/--no-debug", default=False, help="Enable debug logging")
def main(
    engine_path: str,
    threads: int = 4,
    hash: int = 128,
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
    logger = logging.getLogger("chess_uci_mcp")
    logger.setLevel(log_level)

    # Output startup information to logs instead of stdout
    logger.info("Starting Chess UCI MCP bridge")
    logger.info("Engine path: %s", engine_path)
    logger.info("Threads: %d", threads)
    logger.info("Hash: %d MB", hash)
    logger.info("Think time: %d ms", think_time)

    # Create and start bridge
    bridge = ChessUCIBridge(
        engine_path,
        threads=threads,
        hash=hash,
        think_time=think_time
    )

    # Run the bridge
    try:
        asyncio.run(bridge.start())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down")
        asyncio.run(bridge.stop())
    except Exception as e:
        logger.error("Error running bridge: %s", e)
        asyncio.run(bridge.stop())
        sys.exit(1)

if __name__ == "__main__":
    main()