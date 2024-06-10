import itertools
import logging
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from eth_abi import decode as eth_abi_decode
from eth_abi.exceptions import InsufficientDataBytes, NonEmptyPaddingBytes
from eth_utils import to_checksum_address
from eth_utils.abi import (
    event_signature_to_log_topic,
    function_signature_to_4byte_selector,
)
from web3._utils.abi import (
    exclude_indexed_event_inputs,  # Separates data from topics for Event decoding
)
from web3._utils.abi import get_abi_input_types  # For feeding into eth_abi.decode()
from web3._utils.abi import get_abi_output_types  # ...
from web3._utils.abi import (
    get_indexed_event_inputs,  # Separates data from topics for Event decoding
)
from web3._utils.abi import (
    normalize_event_input_types,  # Handles enums and other Event Abstractions
)
from web3._utils.events import get_event_abi_types_for_decoding
from web3.types import ABI  # List of ABIElements
from web3.types import ABIEvent  # Dict containing all params in Event Definition
from web3.types import ABIFunction  # Dict containing all params in Function Definition

from nethermind.entro.exceptions import DecodingError

from .utils import abi_to_signature, filter_events, filter_functions, signature_to_name

root_logger = logging.getLogger("nethermind")
logger = root_logger.getChild("entro").getChild("decoding")


@dataclass
class FunctionDecoder:
    """Stores precomputed data for Decoding Functions and Traces"""

    function_signature: str
    function_input_types: list[str]
    function_input_names: list[str]
    function_output_types: list[str]
    function_output_names: list[str]


@dataclass
class EventDecoder:
    """Stores precomputed data for Decoding Events"""

    event_signature: str
    log_data_types: list[str]
    log_data_names: list[str]
    log_topic_types: list[str]
    log_topic_names: list[str]


class EVMDecoder:
    """
    Decodes Events, Functions, and Traces for an ABI on EVM compatible chains.

    """

    abi_name: str
    """ Name of ABI that is being decoded """

    abi_priority: int
    """ Priority of ABI.  Used for DecodingDispatcher """

    function_decoders: dict[str, FunctionDecoder]
    """ Mapping from 4byte selectors to decoding data """

    event_decoders: dict[str, EventDecoder]
    """ Mapping from 32 byte Event topics/signatures to decoding data """

    formatters: dict[str, Callable[[Any], Any]] = {"address": to_checksum_address}
    """ 
        List of formatters to use on output data.  By default, converts all addresses 
        to checksummed hexstrings
    """

    def __init__(
        self,
        abi_name: str,
        abi_data: ABI,
        abi_priority: int = 0,
    ):
        self.abi_name = abi_name
        self.abi_priority = abi_priority

        abi_functions: list[ABIFunction] = filter_functions(abi_data)
        abi_events: list[ABIEvent] = filter_events(abi_data)

        self.function_decoders = dict([self._load_function_decoder(func) for func in abi_functions])

        self.event_decoders = dict([self._load_event_decoder(event) for event in abi_events])

    def decode_abi_from_types(self, types: list[str], data: bytes | bytearray) -> tuple[Any, ...] | None:
        """
        Decodes ABI data from types and data bytes.  Properly Handles various decoding errors by logging and
        returning none.

        :param types:
        :param data:
        :return:
        """
        try:
            return eth_abi_decode(types, data)
        except InsufficientDataBytes:
            logger.debug(f"Insufficient data bytes while decoding {data.hex()} for types {types}")
            return None
        except NonEmptyPaddingBytes:
            logger.debug(f"Non-empty padding bytes while decoding {data.hex()} for types {types}")
            return None
        except OverflowError:
            logger.debug(f"Overflow error while decoding {data.hex()} for types {types}")
            return None
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"Unknown error: {e.__class__} while decoding {data.hex()} for types {types}: {e}")
            return None

    def get_function_signature(self, function_name) -> str | None:
        """Returns the signature of a function given its name.  If the function does not exist, returns None"""
        for selector, decoder in self.function_decoders.items():
            if signature_to_name(decoder.function_signature) == function_name:
                return selector
        return None

    def get_event_signature(self, event_name) -> str | None:
        """Returns the topic of an event given its name.  If the event does not exist, returns None"""
        for selector, decoder in self.event_decoders.items():
            if signature_to_name(decoder.event_signature) == event_name:
                return selector
        return None

    def get_all_decoded_functions(self, full_signature: bool = True) -> list[str]:
        """Returns a list of all function signatures"""

        return [
            decoder.function_signature if full_signature else signature_to_name(decoder.function_signature)
            for decoder in self.function_decoders.values()
        ]

    def get_all_decoded_events(self, full_signature: bool = True) -> list[str]:
        """Returns a list of all event signatures"""

        return [
            decoder.event_signature if full_signature else signature_to_name(decoder.event_signature)
            for decoder in self.event_decoders.values()
        ]

    def _load_function_decoder(self, abi_function: ABIFunction) -> tuple[str, FunctionDecoder]:
        function_input_types = get_abi_input_types(abi_function)
        function_input_names = [input["name"] for input in abi_function["inputs"]]

        function_output_types = get_abi_output_types(abi_function)
        function_output_names = [output["name"] for output in abi_function["outputs"]]

        function_signature = abi_to_signature(abi_function)
        selector = function_signature_to_4byte_selector(function_signature).hex()

        return selector, FunctionDecoder(
            function_signature=function_signature,
            function_input_types=function_input_types,
            function_input_names=function_input_names,
            function_output_types=function_output_types,
            function_output_names=function_output_names,
        )

    def _load_event_decoder(self, abi_event: ABIEvent) -> tuple[str, EventDecoder]:
        event_signature = abi_to_signature(abi_event)
        selector = event_signature_to_log_topic(event_signature).hex()

        log_topics_abi = get_indexed_event_inputs(abi_event)

        # Normalize input types has wrong signature??
        normalized_topics = normalize_event_input_types(log_topics_abi)
        log_topics_types = list(get_event_abi_types_for_decoding(normalized_topics))
        log_topic_names = [input["name"] for input in log_topics_abi]

        log_data_abi = exclude_indexed_event_inputs(abi_event)
        normalized_data = normalize_event_input_types(log_data_abi)
        log_data_types = list(get_event_abi_types_for_decoding(normalized_data))
        log_data_names = [input["name"] for input in log_data_abi]

        duplicate_names = set(log_topic_names).intersection(log_data_names)
        if duplicate_names:
            raise DecodingError(
                f"Cannot have overlapping names between topics and data.  {self.abi_name} -> {abi_event['name']}"
                f"Has duplicate names: {list(duplicate_names)}"
            )

        logger.debug(
            f"Adding Event Decoder for {event_signature} with Topic Types: {log_topics_types} and "
            f"Data Types: {log_data_types}"
        )
        return selector, EventDecoder(
            event_signature=event_signature,
            log_data_types=log_data_types,
            log_data_names=log_data_names,
            log_topic_types=log_topics_types,
            log_topic_names=log_topic_names,
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

    def decode_function(self, calldata: bytes, transaction_hash: str = "") -> tuple[str, dict[str, Any]] | None:
        """
        Decodes function from input calldata bytes

        :param calldata:
        :return: (function_signature, decoded_input)
        """
        selector = calldata[:4].hex()
        function_decoder = self.function_decoders.get(selector)
        if function_decoder is None:
            raise DecodingError(f"Function with selector {selector} not found in ABI {self.abi_name}")

        func_types = function_decoder.function_input_types
        decoding_result = self.decode_abi_from_types(func_types, calldata[4:])
        if decoding_result is None:
            logger.debug(f"Error Decoding {function_decoder.function_signature} for transaction {transaction_hash}")
            return None

        formatted_result = self.apply_formatters(decoding_result, func_types)

        return function_decoder.function_signature, dict(
            zip(function_decoder.function_input_names, formatted_result, strict=True)
        )

    def decode_trace(
        self, input_data: bytes, output_data: bytes | None, transaction_hash: str = ""
    ) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None]:
        """
        Decodes Input and Output data of Call Trace.

        :param input_data:  Calldata bytes including 4byte function selector
        :param output_data:  Result data from trace
        :return: (function_signature, decoded_input, decoded_output)
        """
        selector = input_data[:4].hex()
        fn_decoder = self.function_decoders.get(selector)
        if fn_decoder is None:
            raise DecodingError(f"Function with selector {selector} not found in ABI {self.abi_name}")

        input_types, output_types = (
            fn_decoder.function_input_types,
            fn_decoder.function_output_types,
        )

        if len(input_data) > 4:
            decoded_input = self.decode_abi_from_types(input_types, input_data[4:])
            if decoded_input is None:
                logger.debug(f"Error Decoding {fn_decoder.function_signature} Input for trace at Tx {transaction_hash}")
                return fn_decoder.function_signature, None, None
            formatted_input = self.apply_formatters(decoded_input, input_types)
            return_input = dict(zip(fn_decoder.function_input_names, formatted_input, strict=True))
        else:
            return_input = None

        if output_data and len(output_data) > 0:
            decoded_output = self.decode_abi_from_types(output_types, output_data)
            if decoded_output is None:
                logger.debug(
                    f"Error Decoding {fn_decoder.function_signature} Output for trace at Tx {transaction_hash}"
                )
                return fn_decoder.function_signature, None, None
            formatted_output = self.apply_formatters(decoded_output, output_types)
            return_output = dict(zip(fn_decoder.function_output_names, formatted_output, strict=True))
        else:
            return_output = None

        return fn_decoder.function_signature, return_input, return_output

    def decode_event(
        self, topics: list[bytes], data: bytes, transaction_hash: str = ""
    ) -> tuple[str, dict[str, Any]] | None:
        """
        Decodes Event topics and data.

        :param topics: List of full Topic Bytes, including the signature at index 0
        :param data: bytearray of indexed data
        :return: (event_signature, decoded_event)
        """
        event_decoder = self.event_decoders.get(topics[0].hex())
        if event_decoder is None:
            logger.error(f"Event with topic {topics[0].hex()} not found in ABI {self.abi_name}")
            raise DecodingError(f"Event with topic {topics[0].hex()} not found in ABI {self.abi_name}")
        decoded_data = self.decode_abi_from_types(event_decoder.log_data_types, data)
        decoded_topics = self.decode_abi_from_types(event_decoder.log_topic_types, b"".join(topics[1:]))

        if decoded_data is None or decoded_topics is None:
            logger.debug(f"Error Decoding Event {event_decoder.event_signature} for Transaction {transaction_hash}")
            return None

        formatted_data = self.apply_formatters(decoded_data, event_decoder.log_data_types)
        formatted_topics = self.apply_formatters(decoded_topics, event_decoder.log_topic_types)

        return event_decoder.event_signature, dict(
            itertools.chain(
                zip(event_decoder.log_data_names, formatted_data, strict=True),
                zip(event_decoder.log_topic_names, formatted_topics, strict=True),
            )
        )
