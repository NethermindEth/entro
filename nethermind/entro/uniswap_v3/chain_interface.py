import logging
from math import ceil, floor

from eth_abi.packed import encode_packed
from eth_typing import ChecksumAddress
from eth_utils import keccak
from eth_utils import to_checksum_address as tca
from rich.logging import RichHandler
from rich.progress import Progress
from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session
from web3.contract import Contract
from web3.exceptions import BadFunctionCallOutput

from nethermind.entro.backfill.utils import block_identifier_to_block
from nethermind.entro.database.models.uniswap import UniV3MintEvent
from nethermind.entro.exceptions import UniswapV3Revert
from nethermind.entro.tokens import ERC20Token
from nethermind.entro.types import BlockIdentifier
from nethermind.entro.types.backfill import SupportedNetwork
from nethermind.entro.types.uniswap_v3 import (
    OracleObservation,
    PoolImmutables,
    PoolState,
    PositionInfo,
    Slot0,
    Tick,
)
from nethermind.entro.uniswap_v3.math import MAX_TICK, MIN_TICK, UniswapV3Math

root_logger = logging.getLogger("nethermind")
logger = root_logger.getChild("entro").getChild("uniswap_v3").getChild("chain_interface")


def fetch_initialization_block(contract: Contract) -> int:
    """
    Fetches the block number of the pool's initialization.  This data is extracted from the Initialize event.
    :param contract: web3.eth.Contract object for UniswapV3Pool
    :return:
    """
    initialize_log = contract.events.Initialize.get_logs(fromBlock=0, toBlock="latest")  # type: ignore
    return initialize_log[0]["blockNumber"]


def fetch_pool_immutables(
    contract: Contract,
) -> PoolImmutables:
    """
    Fetches Immutable Parameters for a V3 Pool

    :param contract: web3.eth.Contract object bound to address of UniswapV3Pool
    :return: PoolImmutables
    """
    token_0 = ERC20Token.from_chain(contract.w3, tca(contract.functions.token0().call()))
    token_1 = ERC20Token.from_chain(contract.w3, tca(contract.functions.token1().call()))
    fee = contract.functions.fee().call()
    tick_spacing = contract.functions.tickSpacing().call()
    initialization_block = fetch_initialization_block(contract)

    logger.info("Queried Pool Immutables ------------------")
    logger.info(f"\tToken 0:  {token_0.name}\t\tDecimals: {token_0.decimals}")
    logger.info(f"\tToken 1:  {token_1.name}\t\tDecimals: {token_1.decimals}")
    logger.info(f"\tPool Fee: {fee}\tQueried Tick Spacing: {tick_spacing}")

    return PoolImmutables(
        pool_address=contract.address,
        token_0=token_0,
        token_1=token_1,
        fee=fee,
        tick_spacing=tick_spacing,
        max_liquidity_per_tick=UniswapV3Math.get_max_liquidity_per_tick(tick_spacing),
        initialization_block=initialization_block,
    )


def fetch_pool_state(
    contract: Contract,
    token_0: ERC20Token,
    token_1: ERC20Token,
    at_block: BlockIdentifier = "latest",
) -> PoolState:
    """Fetches the PoolState at a given block"""

    try:
        # fmt: off
        balance_0 = token_0.contract.functions.balanceOf(contract.address).call(block_identifier=at_block)
        balance_1 = token_1.contract.functions.balanceOf(contract.address).call(block_identifier=at_block)
        liquidity = contract.functions.liquidity().call(block_identifier=at_block)
        fee_growth_global_0 = contract.functions.feeGrowthGlobal0X128().call(block_identifier=at_block)
        fee_growth_global_1 = contract.functions.feeGrowthGlobal1X128().call(block_identifier=at_block)
        prec_0, prec_1 = 10 ** token_0.decimals, 10 ** token_1.decimals
        logger.info("Queried Pool State ------------------")
        logger.info(f"\t{token_0.symbol} Balance: {balance_0 / prec_0}\t{token_1.symbol} Balance: {balance_1/ prec_1}")
        logger.info(f"\tPool Liquidity: {liquidity}")
        logger.info(
            f"\tGlobal {token_0.symbol} Fees: {fee_growth_global_0 / prec_0}\t"
            f"Global {token_1.symbol} Fees: {fee_growth_global_1 / prec_1}"
        )

        return PoolState(
            balance_0=balance_0,
            balance_1=balance_1,
            liquidity=liquidity,
            fee_growth_global_0=fee_growth_global_0,
            fee_growth_global_1=fee_growth_global_1,
        )
        # fmt: on

    except BadFunctionCallOutput as exc:
        raise UniswapV3Revert("Likely querying state prior to pool initialization") from exc


def fetch_slot_0(contract: Contract, at_block: BlockIdentifier = "latest") -> Slot0:
    """
    Fetches the Slot0 data at a given block
    :param contract: web3.eth.Contract object for UniswapV3Pool
    :param at_block: block to query slot0 at
    :return: Slot0
    """
    try:
        slot_0 = contract.functions.slot0().call(block_identifier=at_block)
    except BadFunctionCallOutput as exc:
        raise UniswapV3Revert("Likely querying state prior to pool initialization") from exc
    logger.info("Queried Slot0 ------------------")
    logger.info(f"\tCurrent Sqrt Price: {slot_0[0]}")
    logger.info(f"\tCurrent Tick: {slot_0[1]}")
    logger.info(f"\tObservation Index: {slot_0[2]}")
    logger.info(f"\tObservation Cardinality: {slot_0[3]}")
    logger.info(f"\tObservation Cardinality Next: {slot_0[4]}")
    logger.info(f"\tFee Protocol: {slot_0[5]}")
    return Slot0(
        sqrt_price=slot_0[0],
        tick=slot_0[1],
        observation_index=slot_0[2],
        observation_cardinality=slot_0[3],
        observation_cardinality_next=slot_0[4],
        fee_protocol=slot_0[5],
    )


def fetch_liquidity(
    contract: Contract,
    tick_spacing: int,
    at_block: BlockIdentifier = "latest",
    progress: Progress | None = None,
) -> dict[int, Tick]:
    """
    Fetches all initialized ticks at a given block.  Returns all the initialized ticks in a pool as a dictionary
    between tick numbers and Tick objects.

    In order to fetch all the ticks in a timely manner, the TickBitmap is first searched, and then the ticks are
    queried from chain.  On a .3% fee pool, the bitmap will be searched ~700 times.  The speed of the process is
    written to the console as a tqdm progress bar.
    :param contract: web3.eth.Contract object for UniswapV3Pool
    :param tick_spacing: tick spacing of the pool.  Is either 200, 60, 10 or 1
    :param at_block: block to query liquidity at
    :return: dict[int, Tick]
    """
    logger.info(f"Fetching all Tick data at block {at_block}")
    tick_queue = _generate_tick_queue(contract, tick_spacing, at_block, progress)

    if progress:
        get_liquidity_task = progress.add_task("Fetching Ticks", total=len(tick_queue))

    return_ticks = {}
    for tick in tick_queue:
        if progress:
            progress.advance(get_liquidity_task)
        return_ticks.update({tick: _get_tick(contract, tick, at_block)})

    return return_ticks


def _get_tick(contract: Contract, tick_number: int, at_block: BlockIdentifier) -> Tick:
    tick_data = contract.functions.ticks(tick_number).call(block_identifier=at_block)
    return Tick(
        liquidity_gross=tick_data[0],
        liquidity_net=tick_data[1],
        fee_growth_outside_0=tick_data[2],
        fee_growth_outside_1=tick_data[3],
        tick_cumulative_outside=tick_data[4],
        seconds_per_liquidity_outside=tick_data[5],
        seconds_outside=tick_data[6],
    )


def fetch_positions(
    contract: Contract,
    db_session: Session,
    initialization_block: int | None,
    at_block: BlockIdentifier = "latest",
    progress: Progress | None = None,
) -> dict[tuple[ChecksumAddress, int, int], PositionInfo]:
    """
    Fetches Positions at a specific block.  Position data includes the upper and lower tick, as well as the fees
    accrued by that position.  Using this data a dollar value can be calculated for the position at the given block.

    Utilizes Mint events to generate Position Keys, and then queries the positions from chain.  When Mint events are
    queried, they are saved to the database, so the second time querying pool positions will be faster. The speed of
    the process is written to the console as a tqdm progress bar.

    :param contract: web3.eth.Contract object for UniswapV3Pool
    :param db_session: sqlalchemy database session
    :param initialization_block: block the pool was initialized at (used for speeding up queries)
    :param at_block: block to query positions at
    :return:
    """
    if initialization_block is None:
        initialization_block = fetch_initialization_block(contract)

    at_block = block_identifier_to_block(at_block, SupportedNetwork.ethereum)

    if initialization_block > at_block:
        raise UniswapV3Revert("Cannot fetch positions before pool initialization")

    logger.info("Backfilling Mint Events to generate Position Keys")

    #  TODO: Overhaul Event Query with Updated Idealis functions
    # mint_event_requests = [
    #     parse_event_request(
    #         start_block=start_block,
    #         end_block=start_block + 100_000,
    #         contract_address=contract.address,
    #         topics=["0x7a53080ba414158be7ec69b987b5fb7d07dee101fe85488f0853ae16239d0bde"],
    #         network=SupportedNetwork.ethereum,
    #     )
    #     for start_block in range(initialization_block, at_block, 100_000)
    # ]
    #
    # decode_events_for_requests(
    #     request_objects=mint_event_requests,
    #     json_rpc=contract.w3.provider.endpoint_uri,  # type: ignore
    #     event_writer=EventWriter(db_session.get_bind(), SupportedNetwork.ethereum),
    #     decoder=DecodingDispatcher.from_abis(["UniswapV3Pool"], db_session),
    #     batch_size=50_000,
    #     progress=progress,
    #     task_name="Backfilling Mint Events",
    # )

    position_keys = db_session.execute(
        select(
            UniV3MintEvent.owner,
            UniV3MintEvent.tickLower,
            UniV3MintEvent.tickUpper,
        )
        .distinct(
            tuple_(
                UniV3MintEvent.owner,
                UniV3MintEvent.tickLower,
                UniV3MintEvent.tickUpper,
            )
        )
        .filter(  # type: ignore
            UniV3MintEvent.contract_address == str(contract.address),
            UniV3MintEvent.block_number < at_block,
        )
    ).scalars()
    parsed_keys = [(tca(key[0]), key[1], key[2]) for key in position_keys]

    if progress:
        position_task = progress.add_task("Fetching LP Positions", total=len(parsed_keys))

    output_positions: dict[tuple[ChecksumAddress, int, int], PositionInfo] = {}
    for key in parsed_keys:
        logger.info(f"Queried Position Key: {key}")
        output_positions.update({key: _get_position(contract, key, at_block)})
        if progress:
            progress.advance(position_task)

    logger.info(f"Finished Querying {len(output_positions)} Positions")
    return output_positions


def _get_position(
    contract: Contract,
    position_key: tuple[ChecksumAddress, int, int],
    at_block: BlockIdentifier,
) -> PositionInfo:
    keccak_key = keccak(encode_packed(["address", "int24", "int24"], position_key))

    position = contract.functions.positions(keccak_key).call(block_identifier=at_block)

    return PositionInfo(
        liquidity=position[0],
        fee_growth_inside_0_last=position[1],
        fee_growth_inside_1_last=position[2],
        tokens_owed_0=position[3],
        tokens_owed_1=position[4],
    )


def fetch_observations(
    contract: Contract,
    observation_cardinality: int,
    at_block: BlockIdentifier = "latest",
    progress: Progress | None = None,
) -> list[OracleObservation]:
    """
    Fetches all observations at a given block.  Returns all the observations in a pool as a list of OracleObservation.
    :param contract: web3.eth.Contract object for UniswapV3Pool
    :param observation_cardinality: Observational cardinality of the pool.
    :param at_block: block to query observations at
    :param progress: Optional Rich Progress Bar
    :return:
    """
    logger.info(f"Fetching {observation_cardinality} Observations")
    if progress:
        observation_task = progress.add_task("Fetching TWAP Oracle Observations", total=observation_cardinality)

    observations = []
    for i in range(observation_cardinality):
        observations.append(_fetch_observation(contract, i, at_block))
        if progress:
            progress.advance(observation_task)

    return observations


def _fetch_observation(
    contract: Contract,
    observation_index: int,
    at_block: BlockIdentifier,
) -> OracleObservation:
    observation_data = contract.functions.observations(observation_index).call(block_identifier=at_block)
    return OracleObservation(
        block_timestamp=observation_data[0],
        tick_cumulative=observation_data[1],
        seconds_per_liquidity_cumulative=observation_data[2],
        initialized=observation_data[3],
    )


def _generate_tick_queue(
    contract: Contract,
    tick_spacing: int,
    at_block: BlockIdentifier = "latest",
    progress: Progress | None = None,
) -> list[int]:
    lower_bound_key = floor(MIN_TICK / (256 * tick_spacing))
    upper_bound_key = ceil(MAX_TICK / (256 * tick_spacing)) + 1
    logger.info(
        f"Searching bitmap for ticks between {lower_bound_key * tick_spacing * 256} "
        f"and {upper_bound_key * tick_spacing * 256}"
    )
    output_queue = []
    if progress:
        bitmap_task = progress.add_task("Generating Tick Queue from Bitmap", total=upper_bound_key - lower_bound_key)

    for search_key in range(lower_bound_key, upper_bound_key):
        try:
            bitmap = contract.functions.tickBitmap(search_key).call(block_identifier=at_block)
        except BadFunctionCallOutput as error:
            raise UniswapV3Revert("Failed to fetch tick bitmap.  Likely querying uninitialized pool") from error

        if progress:
            progress.advance(bitmap_task)

        if not bitmap:
            continue
        for sub_tick in reversed(_get_pos_from_bitmap(bitmap)):
            output_queue.append(((search_key * 256) + sub_tick) * tick_spacing)

    logger.info(f"Finished Querying Tick Bitmap.  Generated Tick Queue with {len(output_queue)} ticks")
    return output_queue


def _get_pos_from_bitmap(bitmap: int):
    output = []
    for i in reversed(range(256)):
        k = bitmap >> i
        if k & 1:
            output.append(i)
    return output


def fetch_simulation_state(
    contract: Contract,
    db_session: Session,
    immutables: PoolImmutables,
    slot0: Slot0,
    at_block: BlockIdentifier,
) -> tuple[
    dict[int, Tick],
    dict[tuple[ChecksumAddress, int, int], PositionInfo],
    list[OracleObservation],
]:
    """
    Fetches the current simulation state from RPC, with Rich Progress Bars and Logging

    :return: (ticks, positions, observations)
    """
    with Progress() as progress:
        old_log_level = logger.level
        rich_handler = RichHandler(console=progress.console, show_path=False)

        logger.addHandler(rich_handler)
        logger.setLevel(logging.INFO)

        ticks = fetch_liquidity(
            contract=contract,
            tick_spacing=immutables.tick_spacing,
            at_block=at_block,
            progress=progress,
        )
        positions = fetch_positions(
            contract=contract,
            db_session=db_session,
            initialization_block=immutables.initialization_block,
            at_block=at_block,
            progress=progress,
        )
        observations = fetch_observations(
            contract=contract,
            observation_cardinality=slot0.observation_cardinality,
            at_block=at_block,
        )

        logger.info("Finished Fetching Simulation State")

        logger.removeHandler(rich_handler)
        logger.setLevel(old_log_level)

    return ticks, positions, observations
