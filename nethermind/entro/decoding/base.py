from typing import Any, Protocol


class DecodedFuncDataclass(Protocol):
    """Function Decoding Result"""

    abi_name: str
    name: str
    inputs: dict[str, Any] | None
    outputs: list[Any] | None


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
    """Abstract Protocol for ABI Function Decoders"""

    name: str
    signature: bytes
    abi_name: str

    priority: int

    def decode(self, calldata: list[bytes], result: list[bytes] | None = None) -> DecodedFuncDataclass | None:
        """Decode Function from calldata and result bytes"""
        raise NotImplementedError()

    def id_str(self, full_signature: bool = True) -> str:
        """Return Human Readable representation of the function signature"""
        raise NotImplementedError()


class AbiEventDecoder(Protocol):
    """Abstract Protocol for ABI Event"""

    name: str
    signature: bytes
    abi_name: str

    priority: int
    indexed_params: int

    def decode(self, data: list[bytes], keys: list[bytes]) -> DecodedEventDataclass | None:
        """Decode Event from lists of data and key bytes"""
        raise NotImplementedError()

    def id_str(self, full_signature: bool = True) -> str:
        """Return Human Readable representation of the event signature"""
        raise NotImplementedError()
