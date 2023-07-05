from logging import Logger
from math import ceil, floor
from typing import Dict, List, Tuple, Union

from eth_abi.packed import encode_packed
from eth_typing import ChecksumAddress
from eth_utils import keccak
from eth_utils import to_checksum_address as tca
from sqlalchemy import tuple_
from sqlalchemy.orm import Session
from tqdm import tqdm
from web3 import Web3
from web3.contract import Contract
from web3.exceptions import BadFunctionCallOutput

from python_eth_amm.base.token import ERC20Token
from python_eth_amm.events import backfill_events
from python_eth_amm.exceptions import UniswapV3Revert
from python_eth_amm.math import TickMathModule, UniswapV3SwapMath
from python_eth_amm.uniswap_v3.db import UniV3MintEvent, _parse_uniswap_events
from python_eth_amm.uniswap_v3.types import (
    OracleObservation,
    PoolImmutables,
    PoolState,
    PositionInfo,
    Slot0,
    Tick,
)

# pylint: disable=invalid-name


def fetch_initialization_block(contract: Contract) -> int:
    """
    Fetches the block number of the pool's initialization.  This data is extracted from the Initialize event.
    :param contract: web3.eth.Contract object for UniswapV3Pool
    :return:
    """
    initialize_log = contract.events.Initialize.get_logs(fromBlock=0, toBlock="latest")
    return initialize_log[0]["blockNumber"]


def fetch_pool_immutables(
    w3: Web3,
    contract: Contract,
    logger: Logger,
) -> PoolImmutables:
    """Fetches Immutable Parameters for a V3 Pool"""
    token_0 = ERC20Token.from_chain(w3, tca(contract.functions.token0().call()))
    token_1 = ERC20Token.from_chain(w3, tca(contract.functions.token1().call()))
    fee = contract.functions.fee().call()
    tick_spacing = contract.functions.tickSpacing().call()

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
        max_liquidity_per_tick=UniswapV3SwapMath.get_max_liquidity_per_tick(
            tick_spacing
        ),
    )


def fetch_pool_state(
    contract: Contract,
    token_0: ERC20Token,
    token_1: ERC20Token,
    logger: Logger,
    at_block: Union[int, str] = "latest",
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
        raise UniswapV3Revert(
            "Likely querying state prior to pool initialization"
        ) from exc


def fetch_slot_0(
    contract: Contract, logger: Logger, at_block: Union[int, str] = "latest"
) -> Slot0:
    """
    Fetches the Slot0 data at a given block
    :param contract: web3.eth.Contract object for UniswapV3Pool
    :param logger: logger object
    :param at_block: block to query slot0 at
    :return: Slot0
    """
    try:
        slot_0 = contract.functions.slot0().call(block_identifier=at_block)
    except BadFunctionCallOutput as exc:
        raise UniswapV3Revert(
            "Likely querying state prior to pool initialization"
        ) from exc
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
    logger: Logger,
    at_block: Union[int, str] = "latest",
) -> Dict[int, Tick]:
    """
    Fetches all initialized ticks at a given block.  Returns all the initialized ticks in a pool as a dictionary
    between tick numbers and Tick objects.

    In order to fetch all the ticks in a timely manner, the TickBitmap is first searched, and then the ticks are
    queried from chain.  On a .3% fee pool, the bitmap will be searched ~700 times.  The speed of the process is
    written to the console as a tqdm progress bar.
    :param contract: web3.eth.Contract object for UniswapV3Pool
    :param tick_spacing: tick spacing of the pool.  Is either 200, 60, 10 or 1
    :param logger: Logger object
    :param at_block: block to query liquidity at
    :return: Dict[int, Tick]
    """
    logger.info(f"Fetching all Tick data at block {at_block}")
    tick_queue = _generate_tick_queue(contract, tick_spacing, logger, at_block)

    liquidity_by_tick: Dict[int, Tick] = {}
    for tick in tqdm(tick_queue, desc="Fetching Initialized Ticks"):
        tick_data = contract.functions.ticks(tick).call(block_identifier=at_block)
        liquidity_by_tick[tick] = Tick(
            liquidity_gross=tick_data[0],
            liquidity_net=tick_data[1],
            fee_growth_outside_0=tick_data[2],
            fee_growth_outside_1=tick_data[3],
            tick_cumulative_outside=tick_data[4],
            seconds_per_liquidity_outside=tick_data[5],
            seconds_outside=tick_data[6],
        )
    return liquidity_by_tick


def fetch_positions(
    contract: Contract,
    logger: Logger,
    db_session: Session,
    initialization_block: int,
    at_block: int,
) -> Dict[Tuple[ChecksumAddress, int, int], PositionInfo]:
    """
    Fetches Positions at a specific block.  Position data includes the upper and lower tick, as well as the fees
    accrued by that position.  Using this data a dollar value can be calculated for the position at the given block.

    Utilizes Mint events to generate Position Keys, and then queries the positions from chain.  When Mint events are
    queried, they are saved to the database, so the second time querying pool positions will be faster. The speed of
    the process is written to the console as a tqdm progress bar.

    :param contract: web3.eth.Contract object for UniswapV3Pool
    :param logger: Logger object
    :param db_session: sqlalchemy database session
    :param initialization_block: block the pool was initialized at (used for speeding up queries)
    :param at_block: block to query positions at
    :return:
    """
    if initialization_block > at_block:
        raise UniswapV3Revert("Cannot fetch positions before pool initialization")

    logger.info("Backfilling Mint Events to generate Position Keys")

    backfill_events(
        contract=contract,
        event_name="Mint",
        db_session=db_session,
        db_model=UniV3MintEvent,
        model_parsing_func=_parse_uniswap_events,
        logger=logger,
        from_block=initialization_block,
        to_block=at_block,
        chunk_size=100_000,
    )

    position_keys = (
        db_session.query(
            UniV3MintEvent.owner,
            UniV3MintEvent.tick_lower,
            UniV3MintEvent.tick_upper,
        )
        .distinct(
            tuple_(
                UniV3MintEvent.owner,
                UniV3MintEvent.tick_lower,
                UniV3MintEvent.tick_upper,
            )
        )
        .filter(
            UniV3MintEvent.contract_address == str(contract.address),
            UniV3MintEvent.block_number < at_block,
        )
        .all()
    )

    all_positions: Dict[Tuple[ChecksumAddress, int, int], PositionInfo] = {}

    for key in tqdm(position_keys, desc="Fetching Position Data"):
        key = (tca(key[0]), key[1], key[2])
        keccak_key = keccak(encode_packed(["address", "int24", "int24"], key))

        position = contract.functions.positions(keccak_key).call(
            block_identifier=at_block
        )

        all_positions.update(
            {
                key: PositionInfo(
                    liquidity=position[0],
                    fee_growth_inside_0_last=position[1],
                    fee_growth_inside_1_last=position[2],
                    tokens_owed_0=position[3],
                    tokens_owed_1=position[4],
                )
            }
        )

    logger.info(f"Finished Querying {len(all_positions)} Positions")
    return all_positions


def fetch_observations(
    contract: Contract,
    observation_cardinality: int,
    logger: Logger,
    at_block: Union[int, str] = "latest",
) -> List[OracleObservation]:
    """
    Fetches all observations at a given block.  Returns all the observations in a pool as a list of OracleObservation.
    :param contract: web3.eth.Contract object for UniswapV3Pool
    :param observation_cardinality: Observational cardinality of the pool.
    :param logger: Logger object
    :param at_block: block to query observations at
    :return:
    """
    logger.info(f"Fetching {observation_cardinality} Observations")
    observations: List[OracleObservation] = []
    for observation_index in tqdm(
        range(observation_cardinality), desc="Fetching Pool Observations"
    ):
        observation_data = contract.functions.observations(observation_index).call(
            block_identifier=at_block
        )
        observations.append(
            OracleObservation(
                block_timestamp=observation_data[0],
                tick_cumulative=observation_data[1],
                seconds_per_liquidity_cumulative=observation_data[2],
                initialized=observation_data[3],
            )
        )
    return observations


def _generate_tick_queue(
    contract: Contract, tick_spacing: int, logger: Logger, at_block: Union[int, str]
) -> List[int]:
    lower_bound_key = floor(TickMathModule.MIN_TICK / (256 * tick_spacing))
    upper_bound_key = ceil(TickMathModule.MAX_TICK / (256 * tick_spacing)) + 1
    logger.info(
        f"Searching bitmap for ticks between {lower_bound_key * tick_spacing * 256} "
        f"and {upper_bound_key * tick_spacing * 256}"
    )
    output_queue = []
    for search_key in tqdm(
        range(lower_bound_key, upper_bound_key), desc="Searching Tick Bitmap"
    ):
        try:
            bitmap = contract.functions.tickBitmap(search_key).call(
                block_identifier=at_block
            )
        except BadFunctionCallOutput as error:
            raise UniswapV3Revert(
                "Failed to fetch tick bitmap.  Likely querying uninitialized pool"
            ) from error

        if not bitmap:
            continue
        for sub_tick in reversed(_get_pos_from_bitmap(bitmap)):
            output_queue.append(((search_key * 256) + sub_tick) * tick_spacing)
    return output_queue


def _get_pos_from_bitmap(bitmap: int):
    output = []
    for i in reversed(range(256)):
        k = bitmap >> i
        if k & 1:
            output.append(i)
    return output
