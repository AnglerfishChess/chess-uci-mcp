"""
Configuration module for chess-uci-mcp.

This module handles loading and validating configuration for the Chess UCI MCP server.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Exception raised for configuration errors."""

    pass


class ChessEngineConfig:
    """Configuration for a chess engine."""

    def __init__(self, config_dict: Dict[str, Any]):
        """
        Initialize chess engine configuration.

        Args:
            config_dict: Dictionary containing engine configuration

        Raises:
            ConfigError: If required configuration is missing
        """
        # Required fields
        if "path" not in config_dict:
            raise ConfigError("Engine configuration must include 'path'")

        self.path = config_dict["path"]

        # Check if the path is expandable
        self.path = os.path.expanduser(self.path)

        # Optional fields with defaults
        self.name = config_dict.get("name", os.path.basename(self.path))
        self.options = config_dict.get("options", {})

        # Validate that the path exists
        if not os.path.isfile(self.path):
            raise ConfigError(f"Engine path does not exist: {self.path}")

        # Validate that the path is executable
        if not os.access(self.path, os.X_OK):
            raise ConfigError(f"Engine is not executable: {self.path}")


class ServerConfig:
    """Configuration for the MCP server."""

    def __init__(self, config_dict: Dict[str, Any]):
        """
        Initialize server configuration.

        Args:
            config_dict: Dictionary containing server configuration
        """
        self.host = config_dict.get("host", "localhost")
        self.port = config_dict.get("port", 0)  # 0 means random port
        self.timeout = config_dict.get("timeout", 30)  # seconds
        self.log_level = config_dict.get("log_level", "INFO")


class Config:
    """Main configuration for chess-uci-mcp."""

    def __init__(self, config_dict: Dict[str, Any]):
        """
        Initialize configuration.

        Args:
            config_dict: Dictionary containing configuration

        Raises:
            ConfigError: If required configuration is missing
        """
        # Engine configuration
        engine_dict = config_dict.get("engine", {})
        if not engine_dict:
            raise ConfigError("Configuration must include 'engine' section")

        try:
            self.engine = ChessEngineConfig(engine_dict)
        except ConfigError as e:
            raise ConfigError(f"Invalid engine configuration: {e}")

        # Server configuration
        server_dict = config_dict.get("server", {})
        self.server = ServerConfig(server_dict)

        # Other settings
        self.default_think_time = config_dict.get("default_think_time", 1000)  # ms


def load_config(config_path: Optional[Union[str, Path]] = None) -> Config:
    """
    Load configuration from a YAML file.

    Args:
        config_path: Path to configuration file (optional)

    Returns:
        Config instance

    Raises:
        ConfigError: If configuration can't be loaded or is invalid
    """
    # Default config locations
    default_locations = [
        "./chess_uci_mcp.yaml",
        "./config.yaml",
        os.path.expanduser("~/.config/chess_uci_mcp/config.yaml"),
        "/etc/chess_uci_mcp/config.yaml",
    ]

    # If config_path is provided, try that first
    if config_path:
        config_path = Path(config_path)
        if not config_path.exists():
            raise ConfigError(f"Configuration file not found: {config_path}")

        try:
            with open(config_path, "r") as f:
                config_dict = yaml.safe_load(f)
                return Config(config_dict)
        except Exception as e:
            raise ConfigError(f"Failed to load configuration: {e}")

    # Try default locations
    for location in default_locations:
        path = Path(location)
        if path.exists():
            try:
                with open(path, "r") as f:
                    config_dict = yaml.safe_load(f)
                    logger.info(f"Loaded configuration from {path}")
                    return Config(config_dict)
            except Exception as e:
                logger.warning(f"Failed to load configuration from {path}: {e}")

    # Use default configuration with Stockfish
    stockfish_path = "/usr/local/bin/stockfish"  # Default for macOS

    # Try common Windows locations
    if os.name == "nt":
        for path in [
            "C:\\Program Files\\Stockfish\\stockfish.exe",
            "C:\\Program Files (x86)\\Stockfish\\stockfish.exe",
        ]:
            if os.path.isfile(path):
                stockfish_path = path
                break

    logger.warning("No configuration file found, using defaults")
    config_dict = {
        "engine": {
            "path": stockfish_path,
            "name": "Stockfish",
            "options": {
                "Threads": 4,
                "Hash": 128,
            },
        },
        "server": {
            "host": "localhost",
            "port": 8765,
        },
        "default_think_time": 1000,
    }

    return Config(config_dict)


def create_default_config_file(path: Union[str, Path]) -> None:
    """
    Create a default configuration file.

    Args:
        path: Path where to create the configuration file
    """
    path = Path(path)

    # Create parent directories if they don't exist
    path.parent.mkdir(parents=True, exist_ok=True)

    # Determine default engine path based on platform
    stockfish_path = "/usr/local/bin/stockfish"  # Default for macOS/Linux
    if os.name == "nt":
        stockfish_path = "C:\\Program Files\\Stockfish\\stockfish.exe"

    config = {
        "engine": {
            "path": stockfish_path,
            "name": "Stockfish",
            "options": {
                "Threads": 4,
                "Hash": 128,
            },
        },
        "server": {
            "host": "localhost",
            "port": 8765,
            "timeout": 30,
            "log_level": "INFO",
        },
        "default_think_time": 1000,
    }

    with open(path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
