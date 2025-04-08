#!/usr/bin/env python3
"""
Entry point for the Chess UCI MCP server.

This module provides the main CLI interface for starting and configuring the server.
"""

import logging

import click


@click.command()
@click.argument("engine_path", type=click.Path(exists=True))
@click.option("--host", "-h", default="localhost", help="Host to bind the server to")
@click.option("--port", "-p", default=8765, type=int, help="Port to bind the server to")
@click.option("--threads", "-t", default=4, type=int, help="Number of engine threads to use")
@click.option("--hash", default=128, type=int, help="Hash table size in MB")
@click.option("--think-time", default=1000, type=int, help="Default thinking time in ms")
@click.option("--debug/--no-debug", default=False, help="Enable debug logging")
def main(
    engine_path: str,
    host: str = "localhost",
    port: int = 8765,
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
    )
    logger = logging.getLogger("chess_uci_mcp")
    logger.setLevel(log_level)

    # Output startup information
    click.echo("Starting Chess UCI MCP server")
    click.echo(f"Engine path: {engine_path}")
    click.echo(f"Host: {host}")
    click.echo(f"Port: {port}")
    click.echo(f"Threads: {threads}")
    click.echo(f"Hash: {hash} MB")
    click.echo(f"Think time: {think_time} ms")

    # Stub, real implementation will be here later
    click.echo("Stub: server is running")

    return


if __name__ == "__main__":
    main()
