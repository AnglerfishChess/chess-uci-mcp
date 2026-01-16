"""Type definitions for chess-uci-mcp."""

from typing import Optional, TypedDict, Union


# Type alias matching python-chess's ConfigValue
ConfigValue = Union[str, int, bool, None]


class EngineId(TypedDict, total=False):
    """
    Engine identification from UCI protocol.

    Uses total=False since different engines may return different keys.
    Common keys are 'name' and 'author', but engines may include others.
    """

    name: str
    author: str


class OptionMetadata(TypedDict):
    """Metadata for a single UCI engine option."""

    name: str
    type: str  # 'check', 'spin', 'combo', 'button', 'string'
    default: ConfigValue
    min: Optional[int]  # Only for 'spin' type
    max: Optional[int]  # Only for 'spin' type
    var: Optional[list[str]]  # Only for 'combo' type


class OptionInfo(TypedDict):
    """Full information about an option including current value."""

    metadata: OptionMetadata
    current_value: ConfigValue


class EngineInfo(TypedDict):
    """Return type for engine_info tool."""

    path: str
    id: EngineId
    configured_options: dict[str, ConfigValue]


class GetEngineOptionsResult(TypedDict):
    """Return type for get_engine_options tool."""

    options: dict[str, OptionInfo]


class SetEngineOptionsResult(TypedDict):
    """Return type for set_engine_options tool."""

    success: bool
    applied_options: dict[str, ConfigValue]
    errors: dict[str, str]  # option_name -> error_message
