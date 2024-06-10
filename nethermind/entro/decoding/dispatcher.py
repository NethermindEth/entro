import json
import logging
import shutil
from typing import Any, Literal

from rich.table import Table
from sqlalchemy import Connection, Engine
from sqlalchemy.orm import Session, sessionmaker
from web3.types import ABI

from nethermind.entro.database.readers.internal import query_abis
from nethermind.entro.exceptions import DatabaseError, DecodingError
from nethermind.entro.types.decoding import DecodedEvent, DecodedFunction, DecodedTrace
from nethermind.entro.utils import pprint_list, to_bytes, to_hex

from .evm_decoder import EVMDecoder

root_logger = logging.getLogger("nethermind")
logger = root_logger.getChild("entro").getChild("decoding")

# pylint: disable=raise-missing-from


class DecodingDispatcher:
    """

    Dispatcher for Handing Multi-ABI Decoding.  Can add ABIs for different contracts, and handle conflicts between
    ABIs with conflicting function and Event Signatures

    """

    os: Literal["EVM", "Cairo"]
    """ Type of data to decode.  Supports EVM chains, and Cairo/Starknet Support coming soon """

    loaded_abis: dict[str, EVMDecoder]
    """ Mapping between ABI Names and Decoders """

    all_abis: bool = False
    """ True if all ABIs from database are loaded """

    function_decoders: dict[str, EVMDecoder]
    """ Dictionary mapping function selectors to the correctly prioritized Decoder """

    event_decoders: dict[str, EVMDecoder | dict[int, EVMDecoder]]
    """ Dictionary mapping event signatures to the correctly prioritized Decoder """

    def __init__(
        self,
        os: Literal["EVM", "Cairo"] = "EVM",
        bind: Connection | Engine | None = None,
    ):
        self.os = os
        if bind:
            self.db_session = sessionmaker(bind)()
        self.loaded_abis = {}
        self.function_decoders = {}
        self.event_decoders = {}

    def add_abi(self, abi_name: str, abi_data: ABI, priority: int = 0):
        """
        Adds ABI to DecodingDispatcher.  Dispatcher will track all the currently loaded ABIs, and their priorities.
        If 2 abis share a function/event selector, the ABI with the higher priority will be used to decode those
        selectors.
        :param abi_name: Name of ABI
        :param abi_data: ABI data in form of Typed Dict
        :param priority: Priority of ABI.  Higher is better, negative priority is lower than default
        :return:
        """
        if abi_name in self.loaded_abis:
            error_msg = f"{abi_name} ABI already loaded into dispatcher"
            logger.error(error_msg)
            raise DecodingError(error_msg)

        logger.info(f"Adding ABI {abi_name} to dispatcher with priority {priority}")

        match self.os:
            case "EVM":
                decoder = EVMDecoder(abi_name, abi_data, priority)
            case "Cairo":
                raise NotImplementedError("Cairo ABI decoding not yet implemented")
            case _:
                raise ValueError(f"Invalid OS: {self.os}")

        self.add_function_decoders(decoder)
        self.add_event_decoders(decoder)

        self.loaded_abis.update({abi_name: decoder})
        logger.info(f"Successfully Added {abi_name} ABI to DecodingDispatcher")

    def decode_function(self, calldata: bytes | str, transaction_hash: str = "") -> DecodedFunction | None:
        """
        Decodes Function Input with currently loaded ABIs

        :param calldata:
        :param transaction_hash:  Tx hash to use for debug logging when decoding fails
        :return:
        """
        calldata_bytes = to_bytes(calldata)

        decoder = self.function_decoders.get(calldata_bytes[:4].hex(), None)
        if decoder is None:
            return None

        decoding_res = decoder.decode_function(calldata=calldata_bytes, transaction_hash=transaction_hash)

        if decoding_res is None:
            return None

        function_signature, decoded_input = decoding_res
        return DecodedFunction(
            abi_name=decoder.abi_name,
            function_signature=function_signature,
            decoded_input=decoded_input,
        )

    def decode_receipt(self, receipt_data: dict[str, Any]) -> list[DecodedEvent]:
        """
        Decodes Full Receipt Dictionary from JSON-RPC Response

        :param receipt_data:  JSON response from RPC
        """
        output_logs = []

        for log in receipt_data["logs"]:
            decoded_log = self.decode_log(log)
            if decoded_log:
                output_logs.append(decoded_log)

        return output_logs

    def decode_log(self, log: dict[str, Any]) -> DecodedEvent | None:
        """
        Decodes Log with currently loaded ABIs
        :param log:  Log response from JSON RPC response
        :return:
        """

        topics = log["topics"]
        if len(topics) == 0:
            logger.debug(f"Attempting to Decode log with no Topics: {log}")
            return None

        selector = to_hex(topics[0]).replace("0x", "")

        selector_entry: EVMDecoder | dict[int, EVMDecoder] | None = self.event_decoders.get(selector, None)
        if isinstance(selector_entry, dict):
            event_decoder: EVMDecoder | None = selector_entry.get(len(topics) - 1, None)
        else:
            event_decoder = selector_entry

        if event_decoder is None:
            return None

        topic_bytes = [to_bytes(topic) for topic in topics]

        decoding_res = event_decoder.decode_event(
            topics=topic_bytes,
            data=to_bytes(log.get("data", "")),
            transaction_hash=log.get("transactionHash", ""),
        )

        if decoding_res is None:
            logger.debug(
                f"Error Decoding Event {selector} from ABI {event_decoder.abi_name} for Transaction "
                f"{log['transactionHash']}"
            )
            return None

        (event_signature, event_data) = decoding_res

        return DecodedEvent(
            abi_name=event_decoder.abi_name,
            event_signature=event_signature,
            event_data=event_data,
        )

    def decode_trace(self, trace_response: dict[str, Any]) -> DecodedTrace | None:
        """
        Decodes Trace with currently loaded ABIs
        :param trace_response: Trace response from JSON RPC response
        :return:
        """
        input_data = trace_response["action"]["input"]
        output_data = trace_response["result"]["output"]

        return self.decode_trace_data(input_data, output_data, trace_response["transactionHash"])

    def decode_trace_data(
        self,
        input_data: bytes | str,
        output_data: bytes | str,
        tx_hash: str = "",
    ) -> DecodedTrace | None:
        """
        Decodes Call Trace using ABI decoder
        :param input_data:
        :param output_data:
        :param tx_hash:
        :return: DecodedTrace if selector is present
        """
        input_bytes = to_bytes(input_data)
        output_bytes = to_bytes(output_data)

        selector = input_bytes[:4].hex()
        fn_decoder = self.function_decoders.get(selector, None)
        if fn_decoder is None:
            return None

        function_signature, decoded_input, decoded_output = fn_decoder.decode_trace(input_bytes, output_bytes, tx_hash)

        return DecodedTrace(
            abi_name=fn_decoder.abi_name,
            function_signature=function_signature,
            decoded_input=decoded_input,
            decoded_output=decoded_output,
        )

    @classmethod
    def from_database(
        cls,
        classify_abis: list[str],
        db_session: Session,
        os: Literal["EVM", "Cairo"] = "EVM",
        all_abis: bool = False,
    ) -> "DecodingDispatcher":
        """
        Loads DecodingDispatcher from ABIs saved within database.  Used for the CLI

        :param classify_abis:
            List of ABI Names to load into Dispatcher.  All abi names passed must be available within the database
        :param db_session:
            SQLAlchemy ORM Session
        :param os:
            Type of ABI to Decode.  Currently supports EVM, cairo decoding support coming soon.
        :param all_abis:
            If True, loads all ABIs currently stored in database into decoder
        :return:
        """
        if not classify_abis and not all_abis:
            logger.warning("No ABIs loaded into Dispatcher.  Returning empty Dispatcher... ")
            return DecodingDispatcher(os=os)

        dispatcher = DecodingDispatcher(os=os)
        dispatcher.db_session = db_session
        dispatcher.all_abis = all_abis

        decoding_abis = query_abis(db_session, classify_abis if not all_abis else None)

        if len(decoding_abis) != len(classify_abis) and not all_abis:
            raise DatabaseError(
                f"Some ABIs passed to DecodingDispatcher.from_database() not in database.  ABIs not in DB: "
                f"{','.join(set(classify_abis) - set(abi.abi_name for abi in decoding_abis))}"
            )

        for abi in decoding_abis:
            dispatcher.add_abi(
                abi_name=abi.abi_name,
                abi_data=json.loads(abi.abi_json)  # type: ignore
                if isinstance(abi.abi_json, (str, bytes))
                else abi.abi_json,
                priority=abi.priority,
            )

        return dispatcher

    def get_decoder(self, abi_name: str) -> EVMDecoder:
        """
        Returns decoder for a given ABI name
        :param abi_name:
        :return:
        """
        if self.loaded_abis is None:
            raise ValueError("No ABIs loaded into decoder")

        return self.loaded_abis[abi_name]

    def set_event_decoder(
        self,
        event_selector: str,
        add_decoder_index: int | None,
        decoder: EVMDecoder,
    ):
        """
        Sets Event Decoder for a given event selector.  Used to handle multiple index levels for a single event.
        If add_decoder_index is none, decoder is stored as selector -> Decoder.  If add_decoder_index is an integer,
        decoder is stored as selector -> index -> Decoder

        :param event_selector:
        :param add_decoder_index: int index level to add decoder at valid range: [0-4]
        :param decoder: Decoder instance to add
        :return:
        """

        if add_decoder_index is None:
            self.event_decoders.update({event_selector: decoder})
            return
        if add_decoder_index < 0 or add_decoder_index > 4:
            raise DecodingError("Logs must emit between 0 and 4 indexed parameters")

        try:
            self.event_decoders[event_selector].update({add_decoder_index: decoder})  # type: ignore
        except AttributeError:
            existing_decoder = self.event_decoders[event_selector]

            if isinstance(existing_decoder, dict):
                raise DecodingError("Event Signature already loaded with multiple index levels")

            update_index = len(existing_decoder.event_decoders[event_selector].log_topic_names)

            self.event_decoders.update(
                {
                    event_selector: {
                        update_index: existing_decoder,
                        add_decoder_index: decoder,
                    }
                }
            )

    def add_function_decoders(self, decoder: EVMDecoder):
        """
        Adds function decoders from a given ABI to the dispatcher.  If a function selector is already present, the
        decoder with the higher priority will be used to decode that function selector.

        :param decoder:
        :return:
        """
        logger.debug(f"Adding {decoder.abi_name} Functions: {', '.join(decoder.get_all_decoded_functions())}")
        for func_selector, func_decoder_dict in decoder.function_decoders.items():
            existing_decoder = self.function_decoders.get(func_selector, None)
            if existing_decoder is None or existing_decoder.abi_priority < decoder.abi_priority:
                logger.debug(
                    f"Adding function {func_decoder_dict.function_signature} from ABI {decoder.abi_name} to dispatcher "
                    f"with selector {func_selector}"
                )
                self.function_decoders[func_selector] = decoder

            elif existing_decoder.abi_priority > decoder.abi_priority:
                logger.debug(
                    f"Function {func_decoder_dict.function_signature} with Selector {func_selector} already "
                    f"present in ABI {existing_decoder.abi_name} with Priority: {existing_decoder.abi_priority}"
                )
                continue

            else:
                logger.warning(
                    f"ABI {decoder.abi_name} and {existing_decoder.abi_name} share the decoder for the function "
                    f"{func_decoder_dict.function_signature}, and both are set to priority "
                    f"{decoder.abi_priority}.  Increase or decrease the priority of an ABI to resolve this conflict."
                )
                continue

    def add_event_decoders(self, decoder: EVMDecoder):
        """
        Adds event decoders from a given ABI to the dispatcher.  If an event selector is already present, the
        decoder with the higher priority will be used to decode that event selector.  If an event selector is already
        present, but the new decoder has a different number of indexed parameters, the new decoder will be used to
        decode that event selector.
        :param decoder:
        :return:
        """
        logger.debug(f"Adding {decoder.abi_name} Events: {', '.join(decoder.get_all_decoded_events())}")
        for event_selector, event_decoder_dict in decoder.event_decoders.items():
            add_decoder_index_level = len(event_decoder_dict.log_topic_names)

            selector_entry: EVMDecoder | dict[int, EVMDecoder] | None = self.event_decoders.get(event_selector, None)

            if selector_entry is None:
                logger.debug(f"Adding event {event_selector} from ABI {decoder.abi_name} to dispatcher")
                self.set_event_decoder(event_selector, None, decoder)

            elif isinstance(selector_entry, dict):
                logger.debug("Event Signature Already loaded for multiple index levels")
                existing_indexed_decoder: EVMDecoder | None = selector_entry.get(add_decoder_index_level, None)

                if existing_indexed_decoder is None:
                    self.set_event_decoder(event_selector, add_decoder_index_level, decoder)

                else:
                    if existing_indexed_decoder.abi_priority < decoder.abi_priority:
                        self.set_event_decoder(event_selector, add_decoder_index_level, decoder)
                    elif existing_indexed_decoder.abi_priority > decoder.abi_priority:
                        continue
                    else:
                        logger.warning(
                            f"Event {event_decoder_dict.event_signature} already loaded with same priority.  "
                            f"Defaulting to first loaded"
                        )
                        continue

            elif isinstance(selector_entry, EVMDecoder):
                existing_decoder_index_level = len(selector_entry.event_decoders[event_selector].log_topic_names)

                if existing_decoder_index_level != add_decoder_index_level:
                    logger.debug("Loading Event Signatures at multiple Levels")
                    self.set_event_decoder(event_selector, add_decoder_index_level, decoder)

                else:
                    if selector_entry.abi_priority > decoder.abi_priority:
                        pass
                    elif selector_entry.abi_priority < decoder.abi_priority:
                        self.set_event_decoder(event_selector, None, decoder)
                    else:
                        logger.warning(
                            f"Event {event_decoder_dict.event_signature} already loaded with same priority.  "
                            f"Defaulting to first loaded"
                        )

    def decoder_table(
        self,
        print_functions: bool = True,
        print_events: bool = True,
        full_signatures: bool = False,
    ) -> Table:
        """
        Returns a rich table with all the currently loaded ABIs, and their functions and events.
        Used for printing out abi information in the CLI

        :param print_functions:
        :param print_events:
        :param full_signatures:
        :return:
        """
        term_width = shutil.get_terminal_size().columns
        abi_table = Table(title="Decoding with ABIs", min_width=80, show_lines=True)

        abi_table.add_column("Name")
        abi_table.add_column("Priority")

        if print_functions:
            abi_table.add_column("Functions")
        if print_events:
            abi_table.add_column("Events")

        sorted_abis = sorted(self.loaded_abis.items(), key=lambda x: x[1].abi_priority, reverse=True)

        for abi_name, abi in sorted_abis:
            match print_functions, print_events:
                case True, True:
                    sig_cols = [
                        "\n".join(
                            pprint_list(
                                sorted(abi.get_all_decoded_functions(full_signatures)),
                                int(term_width * 0.4),
                            )
                        ),
                        "\n".join(
                            pprint_list(
                                sorted(abi.get_all_decoded_events(full_signatures)),
                                int(term_width * 0.2),
                            )
                        ),
                    ]
                case True, False:
                    sig_cols = [
                        "\n".join(
                            pprint_list(
                                sorted(abi.get_all_decoded_functions(full_signatures)),
                                int(term_width * 0.7),
                            )
                        ),
                    ]
                case False, True:
                    sig_cols = [
                        "\n".join(
                            pprint_list(
                                sorted(abi.get_all_decoded_events(full_signatures)),
                                int(term_width * 0.6),
                            )
                        ),
                    ]
                case False, False:
                    sig_cols = []
                case _:
                    raise NotImplementedError("Invalid Printout Case")

            abi_table.add_row(abi_name, str(abi.abi_priority), *sig_cols)

        return abi_table

    def decode_transaction(self, tx: dict[str, Any]) -> DecodedFunction | None:
        """
        Decodes Transaction Response JSON Dict with currently loaded ABIs

        :param tx:
        :return:
        """
        tx_hash = tx["hash"]
        calldata = to_bytes(tx["input"])

        match self.os:
            case "EVM":
                return self.decode_function(calldata=calldata, transaction_hash=tx_hash)
            case "Cairo":
                raise NotImplementedError("Cairo ABI decoding not yet implemented")
            case _:
                raise ValueError(f"Invalid OS: {self.os}")
