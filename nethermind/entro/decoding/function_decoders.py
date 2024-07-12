import logging
from typing import Any, Callable, Sequence

from eth_utils import to_checksum_address
from eth_utils.abi import function_signature_to_4byte_selector
from web3._utils.abi import get_abi_input_types  # For feeding into eth_abi.decode()
from web3._utils.abi import get_abi_output_types  # ...
from web3.types import ABIFunction  # Dict containing all params in Function Definition

from nethermind.starknet_abi import AbiFunction, AbiParameter, DecodedFunction
from nethermind.starknet_abi.abi_types import StarknetType

from .utils import abi_to_signature, decode_evm_abi_from_types

root_logger = logging.getLogger("nethermind")
logger = root_logger.getChild("entro").getChild("decoding")


class CairoFunctionDecoder(AbiFunction):
    priority: int
    abi_name: str

    def __init__(
        self, name: str, inputs: list[AbiParameter], outputs: list[StarknetType], abi_name: str, priority: int
    ):
        super().__init__(name, inputs, outputs)
        self.priority = priority
        self.abi_name = abi_name

    def decode(self, calldata: list[bytes], result: list[bytes] | None = None) -> DecodedFunction | None:
        return super().decode(
            calldata=[int.from_bytes(data, "big") for data in calldata],
            result=[int.from_bytes(data, "big") for data in result],
        )

    def id_str(self, full_signature: bool = True) -> str:
        if full_signature:
            return super().id_str()
        return self.name


class EVMFunctionDecoder:
    name: str
    abi_name: str
    function_signature: str
    signature: bytes
    priority: int

    input_types: list[str]
    input_names: list[str]
    output_types: list[str]
    output_names: list[str]

    formatters: dict[str, Callable[[Any], Any]] = {}

    def __init__(self, abi_function: ABIFunction, abi_name: str, priority: int):
        self.priority = priority
        self.abi_name = abi_name
        self.name = abi_function["name"]

        self.input_types = get_abi_input_types(abi_function)
        self.input_names = [input["name"] for input in abi_function["inputs"]]

        self.output_types = get_abi_output_types(abi_function)
        self.output_names = [output["name"] for output in abi_function["outputs"]]

        self.function_signature = abi_to_signature(abi_function)
        self.signature = function_signature_to_4byte_selector(self.function_signature)

        self.formatters = {"address": to_checksum_address}

    def decode(self, calldata: list[bytes], result: list[bytes] | None = None) -> DecodedFunction | None:
        """
        Decodes Function data using the provided calldata.

        :param calldata: List of data bytes
        :param result: List of data bytes
        :return: DecodedFunction
        """

        decoded_input = decode_evm_abi_from_types(self.input_types, b"".join(calldata))
        if decoded_input is None:
            logger.debug(f"Error Decoding {self.function_signature} For Input {[c.hex() for c in calldata]}")
            return None

        formatted_input = self.apply_formatters(decoded_input, self.input_types)
        return_input = dict(zip(self.input_names, formatted_input, strict=True))

        if result and len(result) > 0:
            decoded_output = decode_evm_abi_from_types(self.output_types, b"".join(result))
            if decoded_output is None:
                logger.debug(f"Error Decoding {self.function_signature} for Function Result {r}")
                return None

            formatted_output = self.apply_formatters(decoded_output, self.output_types)
            return_output = dict(zip(self.output_names, formatted_output, strict=True))
        else:
            return_output = None

        return DecodedFunction(
            abi_name=self.abi_name,
            func_name=self.name,
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
            formatter = self.formatters.get(typ)
            if formatter is not None:
                formatted_values.append(formatter(value))
            else:
                formatted_values.append(value)

        return formatted_values

    def id_str(self, full_signature: bool = True) -> str:
        if full_signature:
            return self.function_signature
        return self.name
