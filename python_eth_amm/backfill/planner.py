import logging
import shutil
from dataclasses import dataclass
from typing import Any, Optional, Sequence, TypedDict

from eth_utils import to_checksum_address as tca
from rich.console import Console
from rich.table import Table
from sqlalchemy import select
from sqlalchemy.orm import Session

from python_eth_amm.abi_decoder import DecodingDispatcher
from python_eth_amm.database.models import BackfilledRange
from python_eth_amm.database.writers.utils import model_to_dict
from python_eth_amm.exceptions import BackfillError
from python_eth_amm.types.backfill import BackfillDataType as BDT
from python_eth_amm.types.backfill import SupportedNetwork as SN
from python_eth_amm.utils import pprint_list

from ..types import BlockIdentifier
from .utils import block_identifier_to_block, get_current_block_number

package_logger = logging.getLogger("python_eth_amm")
backfill_logger = package_logger.getChild("backfill")
logger = backfill_logger.getChild("planner")

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
        options=["contract_address", "event_names"],
        required=["contract_address"],
        exclusions=[],
    ),
    BDT.transfers: BackfillFilter(
        options=["token_address", "from_address", "to_address"],
        required=["token_address"],
        exclusions=[("from_address", "to_address")],
    ),
    BDT.spot_prices: BackfillFilter(
        options=["contract_address"],
        required=["contract_address"],
        exclusions=[],
    ),
}


@dataclass
class BackfillRangePlan:
    """Describes the backfill plan for a given block range"""

    required_backfill_ranges: list[tuple[int, int]]
    remove_backfills: list[BackfilledRange]
    add_backfill_range: tuple[int, int] | None


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
    logger.debug(
        f"Cleaning Block Inputs...  Start Parameter: {start_block_id},  End Parameter: {end_block_id}"
    )

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
        raise ValueError(
            f"Invalid block range. start_block must be less than end_block ({start_block} - {end_block})"
        )

    if end_block <= 0 or start_block < 0:
        raise ValueError(
            f"Invalid block range. start_block ({start_block}) must be >= 0 and end_block ({end_block}) "
            f"must be greater than 0 "
        )

    logger.debug(
        f"Returning Cleaned Block Inputs:  Start: {start_block}, End: {end_block}"
    )
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
                raise ValueError(
                    f"Address {value} could not be checksummed...  Double check that addresses are valid "
                )

    # Verify required filters are present
    for required_filter in valid_filters.get("required", []):
        if required_filter not in filter_params.keys():
            raise BackfillError(
                f"'{required_filter}' must be set to backfill {backfill_name}"
            )

    # Verify mutually exclusive options are not present
    for exclusion in valid_filters.get("exclusions", []):
        if (
            exclusion[0] in filter_params.keys()
            and exclusion[1] in filter_params.keys()
        ):
            raise BackfillError(
                f"{backfill_name} cannot be filtered by both {exclusion[0]} and {exclusion[1]}"
            )


def _fetch_backfills(
    db_session: Session,
    data_type: BDT,
    network: SN,
) -> Sequence[BackfilledRange]:
    """Fetches all existing backfills from the database"""
    select_stmt = (
        select(BackfilledRange)
        .where(
            BackfilledRange.data_type == data_type.value,
            BackfilledRange.network == network.value,
        )
        .order_by(BackfilledRange.start_block)  # type: ignore
    )
    existing_backfills = db_session.scalars(select_stmt).all()
    logger.info(f"Selected {len(existing_backfills)} Existing Backfills from Database")
    return existing_backfills


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
        return_data = [
            backfill for backfill in backfills if backfill.filter_data is None
        ]
        logger.info(
            f"Filtered out {len(backfills) - len(return_data)} {data_type.value.capitalize()} Backfills.  "
            f"{len(return_data)} Conflicting Backfills Remaining"
        )
        logger.debug(
            f"Remaining Backfills: [{[model_to_dict(b) for b in return_data]}]"
        )
        return return_data

    if valid_filters and filter_params:
        required_filters = valid_filters.get("required", [])

        for required_filter in required_filters:  # required filters have priority
            filter_val = filter_params.pop(required_filter)
            # _verify_filters ensures Required filter keys are present
            backfills = [
                backfill
                for backfill in backfills
                if backfill.filter_data
                and backfill.filter_data.get(required_filter) == filter_val
            ]

        for filter_key, filter_value in filter_params.items():
            backfills = [
                backfill
                for backfill in backfills
                if backfill.filter_data
                and backfill.filter_data.get(filter_key) == filter_value
            ]

        return_data = sorted(backfills, key=lambda x: x.start_block)
        logger.info(
            f"Filtered out {len(backfills) - len(return_data)} {data_type.value.capitalize()} "
            f"Backfills containing unmatched filters"
        )
        logger.debug(
            f"Remaining Backfills: [{[model_to_dict(b) for b in return_data]}]"
        )
        return return_data

    raise ValueError("Invalid Filter Parameters")


def _compute_backfill_ranges(
    from_block: int,
    to_block: int,
    conflicting_backfills: Sequence[BackfilledRange],
) -> BackfillRangePlan:
    """
    Generates a backfill plan for a given block range and conflicting backfills.
    :param from_block:
    :param to_block:
    :param conflicting_backfills:
    :return:
    """
    ranges: list[tuple[int, int]] = []
    remove_backfills: list[BackfilledRange] = []

    logger.info(
        f"Computing Backfill Ranges for Blocks ({from_block} - {to_block}) with "
        f"{len(conflicting_backfills)} Conflicting Backfills"
    )

    search_block = from_block
    search_backfills = sorted(
        [b for b in conflicting_backfills if b.end_block >= from_block],
        key=lambda x: x.start_block,
    )

    logger.debug(
        f"Sorted Backfill Ranges to Search: {[(b.start_block, b.end_block) for b in search_backfills]}"
    )
    if len(search_backfills) == 0:
        logger.debug("Block Ranges do not overlap.  returning single range")
        return BackfillRangePlan(
            required_backfill_ranges=[(from_block, to_block)],
            remove_backfills=[],
            add_backfill_range=(from_block, to_block),
        )

    while True:
        next_backfill = search_backfills.pop(0)
        next_start, next_end = next_backfill.start_block, next_backfill.end_block
        logger.debug(
            f"Running Iteration of Loop:  Next Backfill: {(next_start, next_end)}\tSearch Block: {search_block}\t"
            f"Current Ranges: {ranges}\tRemove Backfills: {remove_backfills}\tSearch Backfills Remaining: "
            f"{[(b.start_block, b.end_block) for b in search_backfills]}"
        )

        if to_block <= next_start:
            ranges.append((search_block, to_block))

            if to_block == next_start:
                remove_backfills.append(next_backfill)
            break

        if search_block < next_start:
            ranges.append((search_block, next_start))
            remove_backfills.append(next_backfill)
        else:
            if to_block <= next_end:
                break
            remove_backfills.append(next_backfill)

        if next_end >= to_block:
            break

        if len(search_backfills) == 0:
            ranges.append((next_end, to_block))
            break

        search_block = next_end

    logger.debug(
        f"Broke out of Loop...  Computed Ranges: {ranges}\tRemove Backfills: {remove_backfills}"
    )

    if not ranges:
        return BackfillRangePlan(
            required_backfill_ranges=[],
            remove_backfills=[],
            add_backfill_range=None,
        )

    updated_start = min(
        [x[0] for x in ranges] + [b.start_block for b in remove_backfills]
    )
    updated_end = max([x[1] for x in ranges] + [b.end_block for b in remove_backfills])

    logger.debug(
        f"Computed Range for Add Backfill...  ({updated_start} - {updated_end})"
    )

    return BackfillRangePlan(
        required_backfill_ranges=ranges,
        remove_backfills=remove_backfills,
        add_backfill_range=(updated_start, updated_end),
    )


def _unpack_kwargs(
    kwargs: dict[str, Any], backfill_type: BDT
) -> tuple[dict[str, str], dict[str, Any]]:
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


@dataclass
class BackfillPlan:
    """
    Describes the backfill plan for a given backfill request.  Contains the block ranges to backfill, the backfills
    to remove, and the backfill to add.
    """

    backfill_type: BDT
    """ The type of backfill to perform """

    network: SN
    """ The network to backfill """

    block_ranges: list[tuple[int, int]]
    """ The block ranges to backfill """

    remove_backfills: list[BackfilledRange]
    """ The backfills to remove """

    decoder: DecodingDispatcher
    """ The ABI Decoder to use for decoding the backfill data """

    metadata_dict: dict[str, Any]
    """ Metadata for executing the backfill """

    filter_params: dict[str, Any]
    """ The filter parameters to use for the backfill """

    add_backfill: BackfilledRange | None = None
    """ The backfill to add """

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
        start_block, end_block = _clean_block_inputs(
            start_block, end_block, backfill_type, network
        )
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

        _verify_filters(backfill_type, filter_params)

        conflicting_backfills = _filter_conflicting_backfills(
            backfill_type,
            _fetch_backfills(db_session, backfill_type, network),
            filter_params.copy() if filter_params else None,
        )

        backfill_plan = _compute_backfill_ranges(
            from_block=start_block,
            to_block=end_block,
            conflicting_backfills=conflicting_backfills,
        )

        if backfill_type == BDT.events:
            if len(decoder.loaded_abis) != 1:
                raise BackfillError(
                    f"Expected 1 ABI for Event backfill, but found {len(decoder.loaded_abis)}.  "
                    f"Specify an ABI using --contract-abi"
                )

        logger.info("Computed Backfill Plan.... ")
        logger.info(
            f"\tRequired Backfill Ranges: {[f'({b[0]} - {b[1]})' for b in backfill_plan.required_backfill_ranges]}",
        )
        logger.info(
            f"\tRemove Backfills: {[f'({b.start_block} - {b.end_block})' for b in backfill_plan.remove_backfills]}"
        )
        logger.info(f"\tAdd Backfill Range: {backfill_plan.add_backfill_range}")

        if backfill_plan.add_backfill_range is None:
            # The planned backfill is redundant, data is already in db
            return None

        return BackfillPlan(
            backfill_type=backfill_type,
            network=network,
            filter_params=filter_params,
            block_ranges=backfill_plan.required_backfill_ranges,
            metadata_dict=metadata_dict,
            remove_backfills=backfill_plan.remove_backfills,
            decoder=decoder,
            add_backfill=BackfilledRange(
                data_type=backfill_type.value,
                network=network.value,
                start_block=backfill_plan.add_backfill_range[0],
                end_block=backfill_plan.add_backfill_range[1],
                filter_data=filter_params,
                metadata_dict=metadata_dict,
                decoded_abis=decode_abis,
            ),
        )

    def print_backfill_plan(self, console: Console):  # pylint: disable=too-many-locals
        """Prints the backfill plan to the console"""

        if len(self.block_ranges) == 0:
            console.print("[green]No blocks to backfill")
            return

        backfill_type, network = (
            self.backfill_type.value.capitalize(),
            self.network.value.capitalize(),
        )
        term_width = shutil.get_terminal_size().columns

        console.print(
            f"[bold]------ Backfill Plan for {network} {backfill_type} ------"
        )

        block_range_table = Table(title="Backfill Block Ranges", min_width=80)
        block_range_table.add_column("Start Block")
        block_range_table.add_column("End Block")
        block_range_table.add_column("Total Blocks", justify="right")

        for block_range in self.block_ranges:
            block_range_table.add_row(
                f"{block_range[0]:,}",
                f"{block_range[1]:,}",
                f"{block_range[1] - block_range[0]:,}",
            )
        console.print(block_range_table)

        filter_meta_table = Table(
            title="Backfill [green]Filters [white]& [cyan]Metadata", min_width=80
        )
        filter_meta_table.add_column("Key")
        filter_meta_table.add_column("Value")
        for key, val in self.filter_params.items():
            filter_meta_table.add_row(f"[green]{key}", f"{val}")
        for key, val in self.metadata_dict.items():
            filter_meta_table.add_row(f"[cyan]{key}", f"{val}")
        console.print(filter_meta_table)

        if self.metadata_dict.get("all_abis", False):
            console.print(
                f"[bold]Decoding with All {len(self.decoder.loaded_abis)} ABIs in DB:"
            )
            print_data = pprint_list(
                sorted(list(self.decoder.loaded_abis.keys())), int(term_width * 0.9)
            )
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
                console.print(
                    f"[bold green]Querying Events for Contract: {self.get_filter_param('contract_address')}"
                )
                console.print(f"[bold]{abi_name} ABI Decoding Events:")
                event_name_print = pprint_list(
                    self.filter_params.get(
                        "event_names", decoder_instance.get_all_decoded_events(False)
                    ),
                    int(term_width * 0.8),
                )
                for row in event_name_print:
                    console.print(f"\t{row}")

            case BDT.transactions | BDT.traces:
                if not self.filter_params:
                    console.print(f"[bold]Querying all {backfill_type} in each block")

            case BDT.full_blocks:
                console.print(
                    "[bold]Querying Transactions, Logs, and Receipts for Block Range"
                )
            case BDT.blocks:
                pass
            case _:
                raise NotImplementedError(f"Cannot Printout {backfill_type} Backfills")

        console.print(f"[bold]{'-' * int(term_width * .8)}")

    def total_blocks(self) -> int:
        """Returns the total number of blocks within backfill plan"""
        return sum(
            end_block - start_block for start_block, end_block in self.block_ranges
        )

    def get_filter_param(self, filter_key) -> str:
        """Safely Fetch value of Filter Key.  If filter_key is None, will raise error"""
        if self.filter_params is None:
            raise BackfillError(
                f"No Filters set for backfill plan, but Filter Key: {filter_key} expected"
            )
        try:
            return self.filter_params[filter_key]
        except KeyError:
            raise BackfillError(
                f"Filter Key: {filter_key} expected for backfill but not found in filter params"
            )

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
        if self.add_backfill is None or not self.block_ranges:
            raise BackfillError("No backfill to process")

        for remove in self.remove_backfills:
            if remove.start_block > end_block:
                # Remove backfill not yet reached
                self.remove_backfills.remove(remove)

        self.add_backfill.end_block = max(
            [end_block] + [b.end_block for b in self.remove_backfills]
        )

    def save_to_db(self, db_session):
        """
        Saves backfill plan to database

        :param db_session:
        :return:
        """
        for delete_backfill in self.remove_backfills:
            db_session.delete(delete_backfill)

        if self.add_backfill:
            db_session.add(self.add_backfill)

        db_session.commit()

    def mark_failed(self):
        """
        Marks the backfill plan as failed.  This will remove the add-backfill, and reset the remove-backfills
        :return:
        """
        self.remove_backfills = []
        self.add_backfill = None

    def backfill_label(self, range_index: int = 0):
        """
        Returns a label for the backfilled range.  For a mainnet transaction backfill with the ranges
        [(0, 100), (100, 200)], the label label at range index 0 would be
        "Backfill Ethereum Transactions Between (0 - 100)"
        :param range_index:
        :return:
        """

        from_block, to_block = self.block_ranges[range_index]
        net = self.network.value.capitalize()
        typ = self.backfill_type.value.capitalize()

        match self.backfill_type:
            case BDT.events:
                abi_name = list(self.decoder.loaded_abis.keys())[0]
                return f"Backfill {abi_name} Events Between ({from_block} - {to_block})"
            case _:
                return f"Backfill {net} {typ} Between ({from_block} - {to_block})"
