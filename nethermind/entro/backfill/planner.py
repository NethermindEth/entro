import logging
import shutil
import uuid
from dataclasses import dataclass
from typing import Any, Literal, Optional, Sequence, Type, TypedDict

from eth_utils import to_checksum_address as tca
from rich.console import Console
from rich.table import Table
from sqlalchemy.orm import DeclarativeBase, Session

from nethermind.entro.decoding import DecodingDispatcher
from nethermind.entro.database.models import BackfilledRange
from nethermind.entro.database.readers.internal import fetch_backfills_by_datatype
from nethermind.entro.database.writers.utils import (
    automap_sqlalchemy_model,
    model_to_dict,
)
from nethermind.entro.exceptions import BackfillError
from nethermind.entro.types.backfill import BackfillDataType as BDT
from nethermind.entro.types.backfill import SupportedNetwork as SN
from nethermind.entro.utils import pprint_list

from nethermind.entro.decoding.evm_decoder import EVMDecoder
from ..types import BlockIdentifier
from .utils import block_identifier_to_block, get_current_block_number

root_logger = logging.getLogger("nethermind")
logger = root_logger.getChild("entro").getChild("backfill").getChild("planner")


# pylint: disable=raise-missing-from


class BackfillFilter(TypedDict):
    """Describes the valid filters for each backfill type"""

    options: list[str]
    required: list[str]
    exclusions: list[tuple[str, str]]


VALID_FILTERS = {
    BDT.transactions: BackfillFilter(
        options=["for_address"],
        required=[],
        exclusions=[],
    ),
    BDT.traces: BackfillFilter(
        options=["from_address"],
        # for_address and to_address cant be options since there is no way get all internal calls.
        required=[],
        exclusions=[],
    ),
    BDT.events: BackfillFilter(
        options=["contract_address", "event_names", "abi_name"],
        required=["contract_address", "abi_name"],
        exclusions=[],
    ),
    BDT.transfers: BackfillFilter(
        options=["token_address", "from_address", "to_address"],
        required=["token_address"],
        exclusions=[("from_address", "to_address")],
    ),
    BDT.spot_prices: BackfillFilter(
        options=["market_address", "market_protocol"],
        required=["market_address", "market_protocol"],
        exclusions=[],
    ),
}


def _clean_block_inputs(
    start_block_id: BlockIdentifier,
    end_block_id: BlockIdentifier,
    backfill_type: BDT,
    network: SN,
) -> tuple[int, int]:
    """
    Cleans the start_block and end_block parameters for a backfill.  If start_block is None, will set to 0 for
    events and transfers, and the block number of contract creation for transactions.  If end_block is None, will
    set to the current block number.  If end_block is less than start_block, will raise an error.

    :param start_block_id:
    :param end_block_id:
    :param backfill_type:
    :param network:
    :return:
    """
    logger.debug(f"Cleaning Block Inputs...  Start Parameter: {start_block_id},  End Parameter: {end_block_id}")

    # The try excepts are required since all data is passed as strings from the CLI.
    try:
        start_block = int(start_block_id)
    except ValueError:
        start_block = block_identifier_to_block(start_block_id, network)

    try:
        end_block = int(end_block_id)
    except ValueError:
        end_block = block_identifier_to_block(end_block_id, network)

    if backfill_type in [BDT.events, BDT.transfers]:
        # If possible, move up the start block until contract creation block
        pass

    if isinstance(end_block_id, int):
        # Guarantee End block is less than current block if end_block is an integer
        end_block = min(end_block_id, get_current_block_number(network))

    if end_block < start_block:
        raise ValueError(f"Invalid block range. start_block must be less than end_block ({start_block} - {end_block})")

    if end_block <= 0 or start_block < 0:
        raise ValueError(
            f"Invalid block range. start_block ({start_block}) must be >= 0 and end_block ({end_block}) "
            f"must be greater than 0 "
        )

    logger.debug(f"Returning Cleaned Block Inputs:  Start: {start_block}, End: {end_block}")
    return start_block, end_block


def _verify_filters(backfill_type: BDT, filter_params: dict[str, Any]):
    """
    Verifies that the filter parameters are valid for the given backfill type.  Raises an error if the filter
    parameters are invalid.

    :param backfill_type:
    :param filter_params:
    :return:
    """
    logger.info(f"Verifying Filters for {backfill_type} Backfill:  {filter_params}")

    if backfill_type not in VALID_FILTERS:
        if filter_params == {}:
            return
        raise BackfillError(f"{backfill_type.value} backfill does not support filters.")

    valid_filters = VALID_FILTERS[backfill_type]
    backfill_name = backfill_type.value.capitalize()

    # Verify options are valid & addresses are correct
    for filter_key, value in filter_params.items():
        if filter_key not in valid_filters["options"]:
            raise BackfillError(
                f"{backfill_name} cannot be filtered by {filter_key}.  Valid filters for {backfill_name} "
                f"are {valid_filters['options']}"
            )

        if (isinstance(value, str) and value[:2] == "0x") or "address" in filter_key:
            try:
                filter_params[filter_key] = tca(value)
            except ValueError:
                raise ValueError(f"Address {value} could not be checksummed...  Double check that addresses are valid ")

    # Verify required filters are present
    for required_filter in valid_filters.get("required", []):
        if required_filter not in filter_params.keys():
            raise BackfillError(f"'{required_filter}' must be set to backfill {backfill_name}")

    # Verify mutually exclusive options are not present
    for exclusion in valid_filters.get("exclusions", []):
        if exclusion[0] in filter_params.keys() and exclusion[1] in filter_params.keys():
            raise BackfillError(f"{backfill_name} cannot be filtered by both {exclusion[0]} and {exclusion[1]}")


def _filter_conflicting_backfills(
    data_type: BDT,
    backfills: Sequence[BackfilledRange],
    filter_params: dict[str, Any] | None = None,
):
    """
    Filters out backfills that conflict with the potential backfill.  For events, data from the same contract
    address will conflict, and for transactions, conflicts are between the same from_address or to_address

    :param data_type:
    :param backfills:
    :param filter_params:
    :return:
    """
    # Filters & returns the relevant backfills that conflict with the potential backfill.  For events, data from
    # the same contract address will conflict, and for transactions, conflicts are between the same from_address
    # or to_address
    valid_filters = VALID_FILTERS.get(data_type, None)

    if valid_filters is None and filter_params is None:
        return backfills
    if valid_filters is None and filter_params:
        raise BackfillError("Filter Parse Error Occured")
    if valid_filters and filter_params is None:
        return_data = [backfill for backfill in backfills if backfill.filter_data is None]
        logger.info(
            f"Filtered out {len(backfills) - len(return_data)} {data_type.value.capitalize()} Backfills.  "
            f"{len(return_data)} Conflicting Backfills Remaining"
        )
        logger.debug(f"Remaining Backfills: [{[model_to_dict(b) for b in return_data]}]")
        return return_data

    if valid_filters and filter_params:
        required_filters = valid_filters.get("required", [])

        for required_filter in required_filters:  # required filters have priority
            filter_val = filter_params.pop(required_filter)
            # _verify_filters ensures Required filter keys are present
            backfills = [
                backfill
                for backfill in backfills
                if backfill.filter_data and backfill.filter_data.get(required_filter) == filter_val
            ]

        for filter_key, filter_value in filter_params.items():
            backfills = [
                backfill
                for backfill in backfills
                if backfill.filter_data and backfill.filter_data.get(filter_key) == filter_value
            ]

        return_data = sorted(backfills, key=lambda x: x.start_block)
        logger.info(
            f"Filtered out {len(backfills) - len(return_data)} {data_type.value.capitalize()} "
            f"Backfills containing unmatched filters"
        )
        logger.debug(f"Remaining Backfills: [{[model_to_dict(b) for b in return_data]}]")
        return return_data

    raise ValueError("Invalid Filter Parameters")


def _unpack_kwargs(kwargs: dict[str, Any], backfill_type: BDT) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Unpacks kwargs from the CLI.  If kwargs is None, will return empty dicts for filter_params and metadata_dict.

    :param kwargs:
    :return: (filter_params, metadata_dict)
    """
    filter_dict, meta_dict = {}, {}
    valid_fiters = VALID_FILTERS.get(backfill_type, None)
    filter_keys = valid_fiters.get("options", []) if valid_fiters else []
    for key, val in kwargs.items():
        if val is None:
            continue

        if isinstance(val, tuple):
            if len(val) == 0:
                continue
            val = list(val)

        if key in filter_keys:
            filter_dict.update({key: val})
        else:
            meta_dict.update({key: val})

    return filter_dict, meta_dict


def _generate_topics(decoder: EVMDecoder, event_names: list[str]) -> list[str | list[str]]:
    """
        Generates the event topics for an event backfill
    :return:
    """
    if len(event_names) == 0:
        event_names = decoder.get_all_decoded_events(False)

    selectors = []
    for event_name in event_names:
        event_sig = decoder.get_event_signature(event_name)
        if event_sig is None:
            continue
        selectors.append("0x" + event_sig)

    if len(selectors) != len(event_names):
        error_msg = (
            f"{decoder.abi_name} ABI does not contain all of the events specified in the filter. "
            f"ABI Missing events: {set(event_names) - set(decoder.get_all_decoded_events(False))}"
        )
        logger.error(error_msg)
        raise BackfillError(error_msg)

    topics: list[str | list[str]] = []
    if len(selectors) == 1:
        # If only one event is being queried, pass event signatures as a string instead of array
        topics.append(selectors[0])
    else:
        topics.append(selectors)

    return topics


class BackfillRangePlan:
    """Describes the backfill plan for a given block range"""

    backfill_ranges: list[tuple[int, int]]
    backfill_mode: Literal["new", "extend", "join", "empty"]
    conflicts: list[BackfilledRange]
    backfill_kwargs: dict[str, Any]

    remove_backfills: list[BackfilledRange]
    add_backfill: BackfilledRange | None = None

    def __init__(
        self,
        from_block: int,
        to_block: int,
        conflicts: list[BackfilledRange],
        backfill_kwargs: dict[str, Any],
    ):
        self.conflicts = conflicts
        self.backfill_kwargs = backfill_kwargs
        self.remove_backfills = []
        self.add_backfill = None

        if len(conflicts) == 0:
            self.backfill_ranges = [(from_block, to_block)]
            self.backfill_mode = "new"
        elif len(conflicts) == 1:
            self._compute_extend(from_block=from_block, to_block=to_block)
        elif len(conflicts) > 1:
            self._compute_join(from_block=from_block, to_block=to_block)
        else:
            raise BackfillError("Invalid Backfill Range Plan")

    def _compute_extend(self, from_block: int, to_block: int):
        ranges = []
        backfill = self.conflicts[0]
        if from_block < backfill.start_block:
            ranges.append((from_block, backfill.start_block))
        if to_block > backfill.end_block:
            ranges.append((backfill.end_block, to_block))

        self.backfill_ranges = ranges
        self.backfill_mode = "extend" if ranges else "empty"

    def _compute_join(
        self,
        from_block: int,
        to_block: int,
    ):
        ranges: list[tuple[int, int]] = []
        search_block = from_block

        for index, conflict_bfill in enumerate(self.conflicts):
            # -- Handle Start Block Conditions --
            if search_block < conflict_bfill.start_block:
                ranges.append((search_block, conflict_bfill.start_block))

            # -- Handle End Block Conditions --
            if conflict_bfill.end_block >= to_block:
                # To block inside current backfill (This is also final iter)
                break
            if index == len(self.conflicts) - 1:
                # Reached end of conflicts, but to_block is after last end_block
                ranges.append((conflict_bfill.end_block, to_block))
            else:
                search_block = conflict_bfill.end_block

        # Ranges should never be empty
        self.backfill_ranges = ranges
        self.backfill_mode = "join"

    @classmethod
    def compute_db_backfills(
        cls,
        from_block: int,
        to_block: int,
        conflicting_backfills: Sequence[BackfilledRange],
        backfill_kwargs: dict[str, Any],
    ) -> "BackfillRangePlan":
        """
        Generates a backfill plan for a given block range and conflicting backfills.

        :param from_block:
        :param to_block:
        :param conflicting_backfills:
        :param backfill_kwargs:  List of kwargs to pass during ORM model construction
        :return:
        """

        in_range_backfills = [
            b for b in conflicting_backfills if b.end_block >= from_block and b.start_block <= to_block
        ]

        logger.info(
            f"Computing Backfill Ranges for Blocks ({from_block} - {to_block}) with Conflicting Backfills: "
            f"{[(b.start_block, b.end_block) for b in in_range_backfills]}"
        )

        return BackfillRangePlan(
            from_block=from_block,
            to_block=to_block,
            conflicts=sorted(in_range_backfills, key=lambda x: x.start_block),
            backfill_kwargs=backfill_kwargs,
        )

    def _process_extend(self, finished_range: tuple[int, int]):
        if self.add_backfill is None:
            raise BackfillError("Cannot Extend Non-existent Add Backfill")

        if finished_range[0] == self.add_backfill.end_block:
            # First backfill range starts after first conflict
            self.add_backfill.end_block = finished_range[1]
        elif finished_range[1] == self.add_backfill.start_block:
            # First backfill range starts before first conflict
            self.add_backfill.start_block = finished_range[0]
        else:
            raise BackfillError("Cannot Join Backfill to Non-Adjacent Range")

    def mark_finalized(self, range_index: int):
        """
        Marks a given range as finalized, updating remove and add backfills accordingly

        :param range_index: 0-indexed position of backfill range completed
        :return:
        """
        r_len = len(self.backfill_ranges)
        if range_index >= r_len:
            raise BackfillError(
                f"Backfill only contains {r_len} range{'s' if r_len > 1 else ''}... Cannot finalize Range "
                f"#{range_index + 1}"
            )

        finalized_range = self.backfill_ranges[range_index]

        match self.backfill_mode:
            case "new":
                self.add_backfill = BackfilledRange(
                    backfill_id=uuid.uuid4().hex,
                    start_block=finalized_range[0],
                    end_block=finalized_range[1],
                    **self.backfill_kwargs,
                )

            case "extend":
                if not self.add_backfill:
                    self.add_backfill = self.conflicts.pop(0)
                self._process_extend(finalized_range)

            case "join":
                if self.add_backfill is None:  # First Iteration
                    self.add_backfill = self.conflicts.pop(0)
                    self._process_extend(finalized_range)

                try:
                    next_bfill = self.conflicts[0]
                except IndexError:
                    self.add_backfill.end_block = finalized_range[1]
                    return

                if next_bfill.start_block == finalized_range[1]:
                    self.add_backfill.end_block = next_bfill.end_block
                    self.remove_backfills.append(self.conflicts.pop(0))

    def mark_failed(self, range_index, final_block):
        """
        Marks a backfill range as failed, saving current state to database.

        :param range_index:  0-indexed position of backfill range that failure occurred in
        :param final_block:  Block number that failure occurred at
        :return:
        """
        if range_index >= len(self.backfill_ranges):
            raise BackfillError("Backfill Range for Failiure Does Not Exist")
        fail_range = self.backfill_ranges[range_index]
        if not fail_range[0] <= final_block < fail_range[1]:
            raise BackfillError(f"Failiure Occured at block {final_block} Outside of Expected Range {fail_range}")
        if fail_range[0] == final_block:
            # No blocks in range were backfilled
            return

        if self.add_backfill:
            self.add_backfill.end_block = final_block
        else:
            match self.backfill_mode:
                case "new":
                    self.add_backfill = BackfilledRange(
                        backfill_id=uuid.uuid4().hex,
                        start_block=fail_range[0],
                        end_block=final_block,
                        **self.backfill_kwargs,
                    )
                case "extend":
                    if fail_range[0] == self.conflicts[0].end_block:
                        self.add_backfill = self.conflicts[0]
                        self.add_backfill.end_block = final_block
                    else:
                        self.add_backfill = BackfilledRange(
                            backfill_id=uuid.uuid4().hex,
                            start_block=fail_range[0],
                            end_block=final_block,
                            **self.backfill_kwargs,
                        )
                case "join":
                    if self.add_backfill:
                        self.add_backfill.end_block = final_block
                    else:
                        self.add_backfill = BackfilledRange(
                            backfill_id=uuid.uuid4().hex,
                            start_block=fail_range[0],
                            end_block=final_block,
                            **self.backfill_kwargs,
                        )


@dataclass
class BackfillPlan:
    """
    Describes the backfill plan for a given backfill request.  Contains the block ranges to backfill, the backfills
    to remove, and the backfill to add.
    """

    db_session: Session
    """ The database session to use for Backfill CRUD Operations """

    range_plan: BackfillRangePlan
    """ The backfill range plan for the backfill """

    backfill_type: BDT
    """ The type of backfill to perform """

    network: SN
    """ The network to backfill """

    decoder: DecodingDispatcher
    """ The ABI Decoder to use for decoding the backfill data """

    metadata_dict: dict[str, Any]
    """ Metadata for executing the backfill """

    filter_params: dict[str, Any]
    """ The filter parameters to use for the backfill """

    @classmethod
    def generate(
        cls,
        db_session: Session,
        backfill_type: BDT,
        network: SN,
        start_block: BlockIdentifier,
        end_block: BlockIdentifier,
        **kwargs,
    ) -> Optional["BackfillPlan"]:
        """
        Generates a backfill plan for a given backfill request.  Contains the block ranges to backfill, the backfills
        to remove, and the backfill to add.

        :param db_session:
        :param backfill_type:
        :param network:
        :param start_block:
        :param end_block:
        :return:
        """
        start_block, end_block = _clean_block_inputs(start_block, end_block, backfill_type, network)
        filter_params, metadata_dict = _unpack_kwargs(kwargs, backfill_type)

        decode_abis = metadata_dict.pop("decode_abis", [])

        decoder: DecodingDispatcher = (
            metadata_dict.pop("decoder")
            if "decoder" in metadata_dict
            else DecodingDispatcher.from_database(
                classify_abis=decode_abis,
                db_session=db_session,
                all_abis=metadata_dict.get("all_abis", False),
            )
        )
        if backfill_type in [BDT.events]:
            if len(decoder.loaded_abis) != 1:
                raise BackfillError(
                    f"Expected 1 ABI for Event backfill, but found {len(decoder.loaded_abis)}.  "
                    f"Specify an ABI using --contract-abi"
                )
            abi_name, decoder_instance = list(decoder.loaded_abis.items())[0]
            filter_params.update({"abi_name": abi_name})
            metadata_dict.update(
                {
                    "topics": _generate_topics(
                        decoder_instance,
                        filter_params.get("event_names", []),
                    )
                }
            )

        _verify_filters(backfill_type, filter_params)

        conflicting_backfills = _filter_conflicting_backfills(
            backfill_type,
            fetch_backfills_by_datatype(db_session, backfill_type, network),
            filter_params.copy() if filter_params else None,
        )

        backfill_range_plan = BackfillRangePlan.compute_db_backfills(
            from_block=start_block,
            to_block=end_block,
            conflicting_backfills=conflicting_backfills,
            backfill_kwargs={
                "data_type": backfill_type.value,
                "network": network.value,
                "filter_data": filter_params,
                "metadata_dict": metadata_dict,
                "decoded_abis": decode_abis,
            },
        )

        if backfill_range_plan.backfill_mode == "empty":
            # The planned backfill is redundant, data is already in db
            return None

        return BackfillPlan(
            db_session=db_session,
            range_plan=backfill_range_plan,
            backfill_type=backfill_type,
            network=network,
            filter_params=filter_params,
            metadata_dict=metadata_dict,
            decoder=decoder,
        )

    def print_backfill_plan(self, console: Console):  # pylint: disable=too-many-locals
        """Prints the backfill plan to the console"""

        if len(self.range_plan.backfill_ranges) == 0:
            console.print("[green]No blocks to backfill")
            return

        backfill_type, network = (
            self.backfill_type.value.capitalize(),
            self.network.value.capitalize(),
        )
        term_width = shutil.get_terminal_size().columns

        console.print(f"[bold]------ Backfill Plan for {network} {backfill_type} ------")

        block_range_table = Table(title="Backfill Block Ranges", min_width=80)
        block_range_table.add_column("Start Block")
        block_range_table.add_column("End Block")
        block_range_table.add_column("Total Blocks", justify="right")

        for start_block, end_block in self.range_plan.backfill_ranges:
            block_range_table.add_row(
                f"{start_block:,}",
                f"{end_block:,}",
                f"{end_block - start_block:,}",
            )
        console.print(block_range_table)

        filter_meta_table = Table(title="Backfill [green]Filters [white]& [cyan]Metadata", min_width=80)
        filter_meta_table.add_column("Key")
        filter_meta_table.add_column("Value")
        for key, val in self.filter_params.items():
            filter_meta_table.add_row(f"[green]{key}", f"{val}")
        for key, val in self.metadata_dict.items():
            filter_meta_table.add_row(f"[cyan]{key}", f"{val}")
        console.print(filter_meta_table)

        if self.metadata_dict.get("all_abis", False):
            console.print(f"[bold]Decoding with All {len(self.decoder.loaded_abis)} ABIs in DB:")
            print_data = pprint_list(sorted(list(self.decoder.loaded_abis.keys())), int(term_width * 0.9))
            for row in print_data:
                console.print(f"\t{row}")

        else:
            print_funcs = self.backfill_type not in [BDT.events, BDT.transfers]
            print_events = self.backfill_type in [BDT.events, BDT.full_blocks]

            abi_table = self.decoder.decoder_table(print_funcs, print_events)
            console.print(abi_table)

        match self.backfill_type:
            case BDT.events:
                abi_name, decoder_instance = list(self.decoder.loaded_abis.items())[0]
                console.print(f"[bold green]Querying Events for Contract: {self.get_filter_param('contract_address')}")
                console.print(f"[bold]{abi_name} ABI Decoding Events:")
                event_name_print = pprint_list(
                    self.filter_params.get("event_names", decoder_instance.get_all_decoded_events(False)),
                    int(term_width * 0.8),
                )
                for row in event_name_print:
                    console.print(f"\t{row}")

            case BDT.transactions | BDT.traces:
                if not self.filter_params:
                    console.print(f"[bold]Querying all {backfill_type} in each block")

            case BDT.full_blocks:
                console.print("[bold]Querying Transactions, Logs, and Receipts for Block Range")
            case BDT.blocks:
                pass
            case _:
                raise NotImplementedError(f"Cannot Printout {backfill_type} Backfills")

        console.print(f"[bold]{'-' * int(term_width * .8)}")

    def total_blocks(self) -> int:
        """Returns the total number of blocks within backfill plan"""
        return sum(end_block - start_block for start_block, end_block in self.range_plan.backfill_ranges)

    def get_filter_param(self, filter_key) -> str:
        """Safely Fetch value of Filter Key.  If filter_key is None, will raise error"""
        if self.filter_params is None:
            raise BackfillError(f"No Filters set for backfill plan, but Filter Key: {filter_key} expected")
        try:
            return self.filter_params[filter_key]
        except KeyError:
            raise BackfillError(f"Filter Key: {filter_key} expected for backfill but not found in filter params")

    def get_metadata(self, metadata_key: str) -> Any:
        """Safely Fetch value of Metadata Key.  If metadata_key is None, will raise error"""
        if self.metadata_dict is None:
            raise BackfillError(
                f"No Metadata set for {self.backfill_type.value.capitalize()} backfill, "
                f"but Metadata Key: {metadata_key} expected"
            )
        try:
            return self.metadata_dict[metadata_key]
        except KeyError:
            raise BackfillError(
                f"Metadata Key: {metadata_key} expected for {self.backfill_type.value.capitalize()} "
                f"backfill but not found in metadata"
            )

    def process_failed_backfill(self, end_block: int):
        """
        Updates the backfill plan to account for a failed backfill. Updates the add and remove backfill
        parameters so they are correctly reflected in the database.

        :param end_block: The block number that the backfill failed on
        """

        for index, (from_blk, to_blk) in enumerate(self.range_plan.backfill_ranges):
            if from_blk <= end_block < to_blk:
                self.range_plan.mark_failed(index, end_block)
                break

            self.range_plan.mark_finalized(index)

    def save_to_db(self):
        """Saves backfill plan to database"""

        for remove_bfill in self.range_plan.remove_backfills:
            self.db_session.delete(remove_bfill)

        if self.range_plan.add_backfill:
            self.db_session.add(self.range_plan.add_backfill)

        self.db_session.commit()

    def backfill_label(self, range_index: int = 0):  # pylint: disable=unused-argument
        """
        Returns a label for the backfilled range.  For a mainnet transaction backfill with the ranges
        [(0, 100), (100, 200)], the label label at range index 0 would be
        "Backfill Ethereum Transactions Between (0 - 100)"
        :param range_index:
        :return:
        """

        net = self.network.pretty()
        typ = self.backfill_type.pretty()

        match self.backfill_type:
            case BDT.events:
                abi_name = list(self.decoder.loaded_abis.keys())[0]
                return f"Backfill {abi_name} Events"
            case _:
                return f"Backfill {net} {typ}"

    def load_model_overrides(self) -> dict[str, Type[DeclarativeBase]]:
        """
        Generates the event topics and model overrides for an event backfill

        :return: (topics, event_model_overrides)
        """
        model_override_dict: dict[str, str] = self.metadata_dict.get("db_models", {})
        if len(model_override_dict) == 0:
            return {}

        _, decoder = list(self.decoder.loaded_abis.items())[0]
        model_overrides = {}

        all_events_in_decoder = decoder.get_all_decoded_events()

        for event, model in model_override_dict.items():
            if "(" not in event:
                event = [sig for sig in all_events_in_decoder if event in sig][0]
            split = list(reversed(model.split(".")))
            res = automap_sqlalchemy_model(
                db_engine=self.db_session.get_bind(),
                table_names=[split[0]],
                schema=split[1] if split[1:] else "public",
            )
            model_overrides.update({event: res[split[0]]})

        return model_overrides
