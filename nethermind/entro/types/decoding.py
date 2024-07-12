from dataclasses import dataclass
from typing import Any


@dataclass
class DecodedFunction:
    """Function Decoding Result"""

    abi_name: str
    name: str

    function_signature: str
    input: dict[str, Any] | None
    output: list[Any] | None


@dataclass
class DecodedEvent:
    """Event Decoding Result"""

    abi_name: str
    name: str
    event_signature: str

    data: dict[str, Any]


@dataclass
class DecodedTrace:
    """Decoded Trace with decoded inputs and outputs"""

    abi_name: str
    name: str
    signature: str

    decoded_input: dict[str, Any] | None
    decoded_output: dict[str, Any] | None
