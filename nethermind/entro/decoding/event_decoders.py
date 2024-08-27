import itertools
import logging
from typing import Any, Callable, Sequence

from eth_typing.abi import ABIEvent  # Dict containing all params in Event Definition
from eth_utils import to_checksum_address
from eth_utils.abi import event_signature_to_log_topic
from web3._utils.abi import (
    exclude_indexed_event_inputs,
    get_indexed_event_inputs,
    normalize_event_input_types,
)
from web3._utils.events import get_event_abi_types_for_decoding

from nethermind.entro.decoding.utils import decode_evm_abi_from_types
from nethermind.entro.exceptions import DecodingError
from nethermind.entro.types.decoding import DecodedEvent
from nethermind.starknet_abi import AbiEvent
from nethermind.starknet_abi.abi_types import StarknetType
from nethermind.starknet_abi.exceptions import InvalidCalldataError, TypeDecodeError

from .utils import abi_to_signature

root_logger = logging.getLogger("nethermind")
logger = root_logger.getChild("entro").getChild("decoding")


class CairoEventDecoder(AbiEvent):
    """
    Represents a single Starknet Cairo Event.  Parses input & output types to efficiently decode Starknet events
    """

    priority: int
    abi_name: str
    indexed_params: int

    def __init__(
        self,
        name: str,
        parameters: list[str],
        data: dict[str, StarknetType],
        keys: dict[str, StarknetType],
        abi_name: str,
        priority: int = 0,
    ):
        super().__init__(name, parameters, data, keys)
        self.priority = priority
        self.abi_name = abi_name
        self.indexed_params = len(self.keys)

    def decode(self, data: list[bytes], keys: list[bytes]) -> DecodedEvent | None:
        """Decode Starknet Event from binary calldata"""
        try:
            return super().decode(
                data=[int.from_bytes(d, "big") for d in data],
                keys=[int.from_bytes(k, "big") for k in keys],
            )

        except (InvalidCalldataError, TypeDecodeError):
            return None

    def id_str(self, full_signature: bool = True) -> str:
        """
        If full_signature is True, returns Event name with parameter names and types.
        If False, returns event name
        """

        if full_signature:
            return super().id_str()
        return self.name


class EVMEventDecoder:
    """
    Stores precomputed data for Efficiently Decoding EVM Events
    """

    event_signature: str
    signature: bytes
    abi_name: str
    name: str
    priority: int
    indexed_params: int

    _data_types: list[str]
    _data_names: list[str]
    _topic_types: list[str]
    _topic_names: list[str]

    formatters: dict[str, Callable[[Any], Any]] = {}

    def __init__(self, abi_event: ABIEvent, abi_name: str, priority: int = 0):
        event_signature = abi_to_signature(abi_event)
        selector = event_signature_to_log_topic(event_signature)

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
        self._data_names = log_data_names
        self._data_types = log_data_types
        self._topic_names = log_topic_names
        self._topic_types = log_topics_types
        self.abi_name = abi_name
        self.event_signature = event_signature
        self.signature = selector
        self.name = abi_event["name"]
        self.priority = priority
        self.formatters = {"address": to_checksum_address}

        self.indexed_params = len(log_topic_names)

        if self.indexed_params < 0 or self.indexed_params > 4:
            raise DecodingError("Logs must emit between 0 and 4 indexed parameters")

    def decode(self, data: list[bytes], keys: list[bytes]) -> DecodedEvent | None:
        """
        Decodes Event data and topics using the provided keys.

        :param data: List of data bytes
        :param keys: List of topic bytes
        :return: DecodedEventDataclass
        """
        decoded_data = decode_evm_abi_from_types(self._data_types, b"".join(data))
        decoded_topics = decode_evm_abi_from_types(self._topic_types, b"".join(keys[1:]))

        if decoded_data is None or decoded_topics is None:
            logger.debug(
                f"Error Decoding Event {self.event_signature} for keys {[k.hex() for k in keys]} "
                f"and data {[d.hex() for d in data]}"
            )
            return None

        formatted_data = self.apply_formatters(decoded_data, self._data_types)
        formatted_topics = self.apply_formatters(decoded_topics, self._topic_types)

        return DecodedEvent(
            abi_name=self.abi_name,
            name=self.name,
            data=dict(itertools.chain(zip(self._topic_names, formatted_topics), zip(self._data_names, formatted_data))),
            event_signature=self.event_signature,
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
        """If full_signature is True, returns EventName(types,...) Otherwise, returns event name"""
        if full_signature:
            return self.event_signature
        return self.name
