import logging
from typing import Any, Sequence, TypedDict

from eth_utils import to_checksum_address as tca

from nethermind.entro.database.models import BackfilledRange
from nethermind.entro.database.writers.utils import model_to_dict
from nethermind.entro.decoding.evm_decoder import EVMDecoder
from nethermind.entro.exceptions import BackfillError
from nethermind.entro.types.backfill import BackfillDataType as BDT
from nethermind.entro.types.backfill import SupportedNetwork as SN

from ..types import BlockIdentifier
from .utils import block_identifier_to_block, get_current_block_number

root_logger = logging.getLogger("nethermind")
logger = root_logger.getChild("entro").getChild("backfill").getChild("filter")


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
