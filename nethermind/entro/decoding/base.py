from typing import Any, Protocol


class DecodedFuncDataclass(Protocol):
    """Function Decoding Result"""

    abi_name: str
    name: str
    input: dict[str, Any] | None
    output: list[Any] | None


class DecodedEventDataclass(Protocol):
    """Event Decoding Result"""

    abi_name: str
    name: str
    data: dict[str, Any]


# class DecodedTraceDataclass(Protocol):
#     """ Decoded Trace with decoded inputs and outputs """
#
#     abi_name: str
#     name: str
#     input: dict[str, Any] | None
#     output: dict[str, Any] | None


class AbiFunctionDecoder(Protocol):
    name: str
    signature: bytes
    abi_name: str

    priority: int

    def decode(self, calldata: list[bytes], result: list[bytes] | None = None) -> DecodedEventDataclass | None:
        ...

    def id_str(self, full_signature: bool = True) -> str:
        """Return Human Readable representation of the function signature"""
        ...


class AbiEventDecoder(Protocol):
    name: str
    signature: bytes
    abi_name: str

    priority: int
    indexed_params: int

    def decode(self, data: list[bytes], keys: list[bytes]) -> DecodedEventDataclass | None:
        ...

    def id_str(self, full_signature: bool = True) -> str:
        """Return Human Readable representation of the event signature"""
        ...
