import json
import logging
import shutil
from typing import Any, Literal, Sequence, TypedDict

from eth_typing import ABIEvent, ABIFunction
from rich.table import Table
from sqlalchemy import Connection, Engine
from sqlalchemy.orm import Session, sessionmaker

from nethermind.entro.exceptions import DecodingError
from nethermind.entro.types.backfill import (
    Dataclass,
    ExporterDataType,
    SupportedNetwork,
)
from nethermind.entro.utils import pprint_list
from nethermind.starknet_abi import StarknetAbi

from ..database.readers.internal import get_abis
from .base import AbiEventDecoder, AbiFunctionDecoder
from .event_decoders import CairoEventDecoder, EVMEventDecoder
from .function_decoders import CairoFunctionDecoder, EVMFunctionDecoder
from .utils import filter_events, filter_functions

root_logger = logging.getLogger("nethermind")
logger = root_logger.getChild("entro").getChild("decoding")


def _split_evm_data(data: bytes) -> list[bytes]:
    """Splits EVM Calldata into function selector and a list of 32 byte words"""
    return [data[i : i + 32] for i in range(0, len(data), 32)]


class GroupedAbi(TypedDict):
    """Grouped Abi Data Helper Class for Visualizing DecodingDispatcher to console"""

    priority: int
    functions: list[AbiFunctionDecoder]
    events: list[AbiEventDecoder]


class DecodingDispatcher:
    """

    Dispatcher for Handing Multi-ABI Decoding.  Can add ABIs for different contracts, and handle conflicts between
    ABIs with conflicting function and Event Signatures

    """

    decoder_os: Literal["EVM", "Cairo"]
    """ Type of data to decode.  Supports EVM chains, and Starknet Cairo chains  """

    loaded_abis: list[str]
    """ Mapping between ABI Names and Decoders """

    all_abis: bool = False
    """ True if all ABIs from database are loaded """

    function_decoders: dict[bytes, AbiFunctionDecoder]
    """ Dictionary mapping function selectors to the correctly prioritized Decoder """

    event_decoders: dict[bytes, AbiEventDecoder | dict[int, AbiEventDecoder]]
    """ 
    Dictionary mapping event signatures to the correctly prioritized Decoder.  If an event has the same 
    signature, but a different number of indexed parameters, these will be as a dict.  Ie, if a Transfer() event with
    both addresses indexed can be decoded alongside a transfer event with no indexed parameters.  They are same event,
    but have different amounts of data stored between the data and topics/keys.
    """

    db_session: Session | None = None
    """ DB Session for storing ABI JSON.  If none is supplied, ABIs are stored as JSON """

    def __init__(
        self,
        decoder_os: Literal["EVM", "Cairo"] = "EVM",
        bind: Connection | Engine | None = None,
    ):
        self.decoder_os = decoder_os
        if bind:
            self.db_session = sessionmaker(bind)()
        self.loaded_abis = []
        self.function_decoders = {}
        self.event_decoders = {}

    def add_abi(
        self,
        abi_name: str,
        abi_data: Any,
        priority: int = 0,
        **kwargs,
    ):
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

        match self.decoder_os:
            case "EVM":
                abi_functions: list[ABIFunction] = filter_functions(abi_data)
                abi_events: list[ABIEvent] = filter_events(abi_data)
                functions = [EVMFunctionDecoder(f, abi_name, priority) for f in abi_functions]
                events = [EVMEventDecoder(e, abi_name, priority) for e in abi_events]
            case "Cairo":
                abi = StarknetAbi.from_json(
                    abi_json=abi_data, abi_name=abi_name, class_hash=kwargs.get("class_hash", b"")
                )
                functions = [
                    CairoFunctionDecoder(name, list(f.inputs), list(f.outputs), abi_name, priority)
                    for name, f in abi.functions.items()
                ]
                events = [
                    CairoEventDecoder(name, e.parameters, e.data, e.keys, abi_name, priority)
                    for name, e in abi.events.items()
                ]
            case _:
                raise ValueError(f"Invalid Decoder OS: {self.decoder_os}")

        self.add_function_decoders(functions)
        self.add_event_decoders(events)

        self.loaded_abis.append(abi_name)
        logger.info(f"Successfully Added {abi_name} ABI to DecodingDispatcher")

    def add_function_decoders(
        self,
        functions: Sequence[AbiFunctionDecoder],
    ):
        """
        Adds function decoders from a given ABI to the dispatcher.  If a function selector is already present, the
        decoder with the higher priority will be used to decode that function selector.

        :param functions:
        :return:
        """
        logger.debug(f"Adding {functions[0].abi_name} Functions: {', '.join([f.name for f in functions])}")
        for func in functions:
            existing_decoder = self.function_decoders.get(func.signature, None)
            if existing_decoder is None or existing_decoder.priority < func.priority:
                logger.debug(
                    f"Adding function {func.name} from ABI {func.abi_name} to dispatcher "
                    f"with selector 0x{func.signature.hex()}"
                )
                self.function_decoders[func.signature] = func

            elif existing_decoder.priority > func.priority:
                logger.debug(
                    f"Function {func.name} with Signature 0x{func.signature.hex()} already "
                    f"defined in ABI {existing_decoder.abi_name} with Priority: {existing_decoder.priority}"
                )
                continue

            else:
                logger.warning(
                    f"ABI {func.abi_name} and {existing_decoder.abi_name} share the decoder for the function "
                    f"{func.name}, and both are set to priority {func.priority}.  "
                    f"Increase or decrease the priority of an ABI to resolve this conflict."
                )
                continue

    def add_event_decoders(self, events: Sequence[AbiEventDecoder]):
        """
        Adds event decoders from a given ABI to the dispatcher.  If an event selector is already present, the
        decoder with the higher priority will be used to decode that event selector.  If an event selector is already
        present, but the new decoder has a different number of indexed parameters, the new decoder will be used to
        decode that event selector.
        :param events:
        :return:
        """
        logger.debug(f"Adding {events[0].abi_name} Events: {', '.join(e.name for e in events)}")

        for new_event in events:
            existing_event = self.event_decoders.get(new_event.signature, None)

            if existing_event is None:
                logger.debug(f"Adding event {new_event} from ABI {new_event.abi_name} to dispatcher")
                self._set_event_decoder(new_event)

            elif isinstance(existing_event, dict):
                logger.debug("Event Signature Already loaded for multiple index levels")
                existing_indexed_decoder: AbiEventDecoder | None = existing_event.get(new_event.indexed_params, None)

                if existing_indexed_decoder is None:
                    self._set_event_decoder(new_event, set_index=True)
                    return

                if existing_indexed_decoder.priority < new_event.priority:
                    self._set_event_decoder(new_event, set_index=True)
                elif existing_indexed_decoder.priority > new_event.priority:
                    continue
                else:
                    logger.warning(
                        f"Event {new_event.name} (0x{new_event.signature.hex()}) already loaded with same priority.  "
                        f"Defaulting to first loaded decoder..."
                    )
                    continue

            else:
                if existing_event.indexed_params != new_event.indexed_params:
                    logger.debug("Loading Event Signatures at multiple Levels")
                    self._set_event_decoder(new_event, True)
                    return

                if existing_event.priority > new_event.priority:
                    continue

                if existing_event.priority < new_event.priority:
                    self._set_event_decoder(new_event, True)
                else:
                    logger.warning(
                        f"Event {new_event.name} (0x{new_event.signature.hex()}) already loaded with same priority.  "
                        f"Defaulting to first loaded decoder..."
                    )

    @classmethod
    def from_abis(
        cls,
        classify_abis: list[str],
        db_session: Session | None,
        decoder_os: Literal["EVM", "Cairo"] = "EVM",
        all_abis: bool = False,
    ) -> "DecodingDispatcher":
        """
        Loads DecodingDispatcher from ABIs saved within database.  Used for the CLI

        :param classify_abis:
            List of ABI Names to load into Dispatcher.  All abi names passed must be available within the database
        :param db_session:
            SQLAlchemy ORM Session
        :param decoder_os:
            Type of ABI to Decode.
        :param all_abis:
            If True, loads all ABIs currently stored in database into decoder
        """
        if not classify_abis and not all_abis:
            logger.warning("No ABIs loaded into Dispatcher.  Returning empty Dispatcher... ")
            return DecodingDispatcher(decoder_os=decoder_os)

        dispatcher = DecodingDispatcher(decoder_os=decoder_os)
        dispatcher.db_session = db_session
        dispatcher.all_abis = all_abis

        decoding_abis = get_abis(
            db_session=db_session,
            abi_names=classify_abis if not all_abis else None,
            decoder_os=decoder_os,
        )

        if len(decoding_abis) != len(classify_abis) and not all_abis:
            raise DecodingError(
                f"Some ABIs passed to DecodingDispatcher.from_abis() not present.  Missing ABIs: "
                f"{','.join(set(classify_abis) - set(abi.abi_name for abi in decoding_abis))}"
            )

        for abi in decoding_abis:
            dispatcher.add_abi(
                abi_name=abi.abi_name,
                abi_data=(
                    json.loads(abi.abi_json) if isinstance(abi.abi_json, (str, bytes)) else abi.abi_json  # type: ignore
                ),
                priority=abi.priority,
            )

        return dispatcher

    def _set_event_decoder(self, event: AbiEventDecoder, set_index: bool = False):
        """
        Sets Event Decoder for a given event selector.  Used to handle multiple index levels for a single event.
        If add_decoder_index is none, decoder is stored as selector -> Decoder.  If add_decoder_index is an integer,
        decoder is stored as selector -> index -> Decoder

        :param event:
        :param set_index: If False, just sets decoder, if true, sets dict of decoders
        """

        if not set_index:
            self.event_decoders.update({event.signature: event})
            return

        try:
            self.event_decoders[event.signature].update({event.indexed_params: event})  # type: ignore
        except AttributeError:
            existing_event = self.event_decoders[event.signature]

            if isinstance(existing_event, dict):
                raise DecodingError("Event Signature already loaded with multiple index levels")

            self.event_decoders.update(
                {
                    event.signature: {
                        existing_event.indexed_params: existing_event,
                        event.indexed_params: event,
                    }
                }
            )

    def get_flattened_events(self) -> list[AbiEventDecoder]:
        """
        Returns a list of all event decoders currently loaded into the dispatcher.  If there are multiple index
        levels for an event, will return the event implementation with the fewest indexed parameters.

        """
        output_events = []
        for event in self.event_decoders.values():
            if isinstance(event, dict):
                indicies = sorted(event.keys())
                output_events.append(event[indicies[0]])
            else:
                output_events.append(event)

        return output_events

    def _group_abis(self) -> dict[str, GroupedAbi]:

        output_dict: dict[str, GroupedAbi] = {
            name: {"priority": -1, "functions": [], "events": []} for name in self.loaded_abis
        }

        for func in self.function_decoders.values():
            output_dict[func.abi_name]["functions"].append(func)
            output_dict[func.abi_name]["priority"] = func.priority

        for event in self.get_flattened_events():
            output_dict[event.abi_name]["events"].append(event)
            output_dict[event.abi_name]["priority"] = event.priority

        return output_dict

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
        fs = full_signatures
        term_width = shutil.get_terminal_size().columns
        abi_table = Table(title=f"[bold magenta]{self.decoder_os} Decoder ABIs", min_width=80, show_lines=True)

        abi_table.add_column("Name")
        abi_table.add_column("Priority")

        if print_functions:
            abi_table.add_column("Functions")
        if print_events:
            abi_table.add_column("Events")

        grouped_abis = self._group_abis()

        sorted_abis = sorted(grouped_abis.items(), key=lambda x: x[1]["priority"], reverse=True)

        for abi_name, abi_params in sorted_abis:
            events, funcs = abi_params["events"], abi_params["functions"]
            match print_functions, print_events:
                case True, True:
                    sig_cols = [
                        "\n".join(pprint_list(sorted(f.id_str(fs) for f in funcs), int(term_width * 0.4))),
                        "\n".join(pprint_list(sorted(e.id_str(fs) for e in events), int(term_width * 0.2))),
                    ]
                case True, False:
                    sig_cols = [
                        "\n".join(pprint_list(sorted(f.id_str(fs) for f in funcs), int(term_width * 0.7))),
                    ]
                case False, True:
                    sig_cols = [
                        "\n".join(pprint_list(sorted(e.id_str(fs) for e in events), int(term_width * 0.6))),
                    ]
                case False, False:
                    sig_cols = []
                case _:
                    raise NotImplementedError("Invalid Printout Case")

            abi_table.add_row(abi_name, str(abi_params["priority"]), *sig_cols)

        return abi_table

    def decode_transaction(self, tx: Dataclass):
        """
        Decodes Transaction Response JSON Dict with currently loaded ABIs

        :param tx:
        :return:
        """

        match self.decoder_os:
            case "EVM":
                assert hasattr(tx, "input") and isinstance(tx.input, bytes), "EVM Transactions must have input bytes"

                function_decoder = self.function_decoders.get(tx.input[:4])
                if function_decoder is None:
                    return
                decode_result = function_decoder.decode(calldata=_split_evm_data(tx.input[4:]))
                if decode_result:
                    tx.decoded_input = decode_result.inputs  # type: ignore
                    tx.function_name = decode_result.name  # type: ignore

            case "Cairo":
                assert hasattr(tx, "calldata") and isinstance(
                    tx.calldata, list
                ), "Cairo Transactions must have calldata array"

                assert hasattr(tx, "selector"), "Cairo Transactions must have selector"

                function_decoder = self.function_decoders.get(tx.selector)
                if function_decoder is None:
                    return
                decode_result = function_decoder.decode(calldata=tx.calldata)
                if decode_result:
                    tx.decoded_input = decode_result.inputs  # type: ignore
                    tx.function_name = decode_result.name  # type: ignore

            case _:
                raise ValueError(f"Invalid Decoder OS: {self.decoder_os}")

    def decode_event(self, event: Dataclass):
        """
        Decodes Event Response JSON Dict with currently loaded ABIs

        :param event:
        :return:
        """
        match self.decoder_os:
            case "EVM":
                assert hasattr(event, "topics") and isinstance(event.topics, list), "EVM Events must have Topic Array"
                assert hasattr(event, "data") and isinstance(event.data, bytes), "EVM Events must have Data Bytes"

                event_decoder = self.event_decoders.get(event.topics[0])
                if event_decoder is None:
                    return

                if isinstance(event_decoder, dict):  # Multiple Index Levels
                    event_decoder = event_decoder.get(len(event.topics) - 1)
                    if event_decoder is None:
                        return

                decoded = event_decoder.decode(data=_split_evm_data(event.data), keys=event.topics)
                if decoded:
                    event.decoded_params = decoded.data  # type: ignore
                    event.event_name = decoded.name  # type: ignore

            case "Cairo":
                assert hasattr(event, "keys") and isinstance(event.keys, list), "Cairo Events must have Keys Array"
                assert hasattr(event, "data") and isinstance(event.data, list), "Cairo Events must have Data Array"

                event_decoder = self.event_decoders.get(event.keys[0])
                if event_decoder is None:
                    return

                if isinstance(event_decoder, dict):  # Multiple Index Levels
                    event_decoder = event_decoder.get(len(event.keys) - 1)
                    if event_decoder is None:
                        return

                decoded = event_decoder.decode(data=event.data, keys=event.keys)
                if decoded:
                    event.decoded_params = decoded.data  # type: ignore
                    event.event_name = decoded.name  # type: ignore

            case _:
                raise ValueError(f"Invalid Decoder OS: {self.decoder_os}")

    def decode_dataclasses(
        self,
        data_kind: ExporterDataType,
        dataclasses: list[Dataclass],
    ):
        """
        Decodes a list of Dataclasses with the current ABI Decoders.
        Accepts mutable list of dataclasses & modifies them in place with decoded data if applicable

        :param data_kind:  Matches the data key for the dict returned by importer callables
        :param dataclasses: List of Dataclasses to decode

        """
        match data_kind:
            case ExporterDataType.transactions:
                for tx in dataclasses:
                    self.decode_transaction(tx)

            case ExporterDataType.events:
                for event in dataclasses:
                    self.decode_event(event)

            case ExporterDataType.traces:
                raise NotImplementedError("Trace Decoding not yet implemented")

    @classmethod
    def decoder_os_for_network(cls, network: SupportedNetwork) -> Literal["EVM", "Cairo"]:
        """
        Returns the Decoder OS for a given network.  Currently only supports Starknet and EVM
        """
        match network:
            case SupportedNetwork.starknet:
                return "Cairo"
            case _:
                return "EVM"
