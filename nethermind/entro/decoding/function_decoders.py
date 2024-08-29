import logging
from typing import Any, Callable, Sequence

from eth_typing.abi import (
    ABIFunction,  # Dict containing all params in Function Definition
)
from eth_utils import to_checksum_address
from eth_utils.abi import (
    function_signature_to_4byte_selector,
    get_abi_input_types,
    get_abi_output_types,
)

from nethermind.starknet_abi import AbiFunction, AbiParameter, DecodedFunction
from nethermind.starknet_abi.abi_types import StarknetType

from .utils import abi_to_signature, decode_evm_abi_from_types

root_logger = logging.getLogger("nethermind")
logger = root_logger.getChild("entro").getChild("decoding")


class CairoFunctionDecoder(AbiFunction):
    """
    Represents a single Starknet Cairo Function.  Parses input & output types to efficiently decode
    starknet traces
    """

    priority: int
    abi_name: str

    def __init__(
        self, name: str, inputs: list[AbiParameter], outputs: list[StarknetType], abi_name: str, priority: int
    ):
        super().__init__(name, inputs, outputs)
        self.priority = priority
        self.abi_name = abi_name

    def decode(self, calldata: list[bytes], result: list[bytes] | None = None) -> DecodedFunction | None:
        """
        Decode function calldata & result data into a DecodedFunction object.  Converts calldata into int calldata
        for starknet decoder
        """
        return super().decode(
            calldata=[int.from_bytes(data, "big") for data in calldata],
            result=[int.from_bytes(data, "big") for data in result or []],
        )

    def id_str(self, full_signature: bool = True) -> str:
        """
        If full_signature is true, returns function name with parameter names and types.
        If false, returns function name
        """
        if full_signature:
            return super().id_str()
        return self.name


class EVMFunctionDecoder:
    """
    Represents a single EVM function selector.  Parses input & output types to efficiently decode
    transactions & traces with its selector
    """

    name: str
    abi_name: str
    function_signature: str
    signature: bytes
    priority: int

    _input_types: list[str]
    _input_names: list[str]
    _output_types: list[str]
    _output_names: list[str]

    _formatters: dict[str, Callable[[Any], Any]] = {}

    def __init__(self, abi_function: ABIFunction, abi_name: str, priority: int):
        self.priority = priority
        self.abi_name = abi_name
        self.name = abi_function["name"]

        self._input_types = get_abi_input_types(abi_function)
        self._input_names = [input["name"] for input in abi_function["inputs"]]

        self._output_types = get_abi_output_types(abi_function)
        self._output_names = [output["name"] for output in abi_function["outputs"]]

        self.function_signature = abi_to_signature(abi_function)
        self.signature = function_signature_to_4byte_selector(self.function_signature)

        self._formatters = {"address": to_checksum_address}

    def decode(self, calldata: list[bytes], result: list[bytes] | None = None) -> DecodedFunction | None:
        """
        Decodes Function data using the provided calldata.

        :param calldata: List of data bytes
        :param result: List of data bytes
        :return: DecodedFunction
        """

        decoded_input = decode_evm_abi_from_types(self._input_types, b"".join(calldata))
        if decoded_input is None:
            logger.debug(f"Error Decoding {self.function_signature} For Input {[c.hex() for c in calldata]}")
            return None

        formatted_input = self.apply_formatters(decoded_input, self._input_types)
        return_input = dict(zip(self._input_names, formatted_input, strict=True))

        if result and len(result) > 0:
            decoded_output = decode_evm_abi_from_types(self._output_types, b"".join(result))
            if decoded_output is None:
                logger.debug(
                    f"Error Decoding {self.function_signature} for "
                    f"Function Result {[f'0x{r.hex()}' for r in result]}"
                )
                return None

            formatted_output = self.apply_formatters(decoded_output, self._output_types)
            return_output = dict(zip(self._output_names, formatted_output, strict=True))
        else:
            return_output = None

        return DecodedFunction(
            abi_name=self.abi_name,
            name=self.name,
            inputs=return_input,
            outputs=return_output,
        )

    def apply_formatters(self, decoding_result: Sequence[Any], types: list[str]) -> list[Any]:
        """
        Applies currently loaded formatted to decoding result.

        :param decoding_result: List of values returned from ABI Decoding
        :param types: List of types for each entry in decoding_result
        """
        formatted_values = []
        for value, typ in zip(decoding_result, types, strict=True):
            formatter = self._formatters.get(typ)
            if formatter is not None:
                formatted_values.append(formatter(value))
            else:
                formatted_values.append(value)

        return formatted_values

    def id_str(self, full_signature: bool = True) -> str:
        """
        Returns ID string for function.  If full_signature is True, returns the function name & parameter types.
        If full_signature is false, returns function name
        """
        if full_signature:
            return self.function_signature
        return self.name
