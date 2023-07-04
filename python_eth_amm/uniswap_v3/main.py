import bisect
import datetime
import json
from decimal import Decimal
from math import floor
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from uuid import uuid4

import numpy as np
import sqlalchemy.schema
from eth_typing import ChecksumAddress
from eth_utils import to_checksum_address
from pandas import DataFrame
from pydantic import parse_obj_as
from sqlalchemy import desc
from sqlalchemy.engine import Engine
from web3.contract import Contract

from python_eth_amm.base.token import ERC20Token
from python_eth_amm.events import backfill_events
from python_eth_amm.exceptions import UniswapV3Revert
from python_eth_amm.math import UniswapV3SwapMath
from python_eth_amm.utils import random_address, uint_over_under_flow

from .chain_interface import (
    fetch_initialization_block,
    fetch_liquidity,
    fetch_observations,
    fetch_pool_immutables,
    fetch_pool_state,
    fetch_positions,
    fetch_slot_0,
)
from .db import (
    UniswapV3Base,
    UniV3EventBase,
    UniV3MintEvent,
    UniV3PositionLogs,
    UniV3SwapLogs,
    _parse_uniswap_events,
)
from .types import (
    OracleObservation,
    PoolImmutables,
    PoolState,
    PositionInfo,
    Slot0,
    SwapCache,
    SwapState,
    SwapStep,
    Tick,
)

Q128 = 0x100000000000000000000000000000000


# pylint: disable=too-many-instance-attributes, too-many-public-methods, too-many-lines
class UniswapV3Pool:
    """
    Class to simulate behavior of Uniswap V3 pools in python.
    Reproduces solidity integer rounding behavior when exact math mode enabled.

    Re-Implements all functions of UniswapV3 pools in python, and provides research functionality.

    """

    pool_contract: Optional[Contract] = None
    """
    :class:`web3.contract.Contract` object for interacting with the on-chain pool.  Is only present when pool is
    initialized through the from_chain() method.
    """

    initialization_block: Optional[int] = None
    """
    Block that pool was initialized at if pool is queried from chain, None if pool is test initialization
    """

    immutables: PoolImmutables
    """
    PoolImmutables object containing the pool fee, token_0, token_1, and other immutable parameters
    """
    slot0: Slot0
    """
    Slot0 object containing all current state of the pool.  Used to track the current sqrt_prce and tick of the pool.
    Also tracks data for accumulating oracle
    """

    state: PoolState
    """
    PoolState object containing all current state of the pool.  Used to track the current liquidity, balances, and fees
    """

    block_number: int
    """
    Current block number of the pool.  Is used when logging analytics, and for replaying historical swaps.
    Can be manually incremented through the advance_block() method.
    """

    block_timestamp: int  # Current block timestamp
    """
    Current Block timestamp of the pool.  Is required to tracking oracle observations, and tracking 
    liquidity position fee growth.  Every time advance_block() is called, this value is incremented by 12 seconds.
    """

    protocol_fee_0: int = 0
    """
        Amount of Token 0 Owed to the protocol if fee switch is turned on
    """
    protocol_fee_1: int = 0
    """
        Amount of Token 1 Owed to the protocol if fee switch is turned on
    """
    ticks: Dict[int, Tick]  # Current state of Ticks
    """
    Dictionary of all initialized Ticks.  Ticks are initialized (added to this dictionary) when liquidity is added
    to a tick, and are deleted from the dictionary when all the liquidity is removed from a tick.  
    This dictionary is unsorted, and when it become necessary to cross a tick, the dictionary keys are sorted and
    searched.  This removes the need for the TickBitmap that is used in the on-chain implementation.
    """
    observations: List[OracleObservation]  # TWAP Oracle Observations
    """
    List of all oracle observations.  Oracle observations are not yet fully supported, so this API will likely change
    """
    positions: Dict[Tuple[ChecksumAddress, int, int], PositionInfo]  # LPs
    """
    Dictionary of all LP positions.  The key to access the info for a position is a tuple of the owner address, 
    lower tick, and upper tick of the position. 
    
    For on-chain uniswap V3 pools, the majority of all liquidity is owned by the UniswapV3NFTPositionManager 
    that is deployed at `0xC364...FE88 <https://etherscan.io/address/0xC36442b4a4522E871399CD717aBDD847Ab11FE88>`_
    """

    _rounding_mode: bool = False  # True for exact rounding, false for approx

    def __init__(self, factory) -> None:
        self.pool_factory = factory
        self._rounding_mode = factory.exact_math
        self.logger = factory.logger
        self.math: UniswapV3SwapMath = factory._get_math_module("UniswapV3SwapMath")

    @classmethod
    def initialize_empty_pool(
        cls,
        factory,
        **kwargs,
    ) -> "UniswapV3Pool":
        """
        Initializes an empty pool with default values
        """
        pool_instance = UniswapV3Pool(factory=factory)

        pool_instance.ticks = {}
        pool_instance.observations = []
        pool_instance.positions = {}

        pool_instance.immutables = PoolImmutables(
            pool_address=random_address(),
            token_0=kwargs.get("token_0", ERC20Token.default_token(0)),
            token_1=kwargs.get("token_1", ERC20Token.default_token(1)),
            fee=kwargs.get("fee", 3000),
            tick_spacing=(tick_spacing := kwargs.get("tick_spacing", 10)),
            max_liquidity_per_tick=pool_instance.math.get_max_liquidity_per_tick(
                tick_spacing
            ),
        )

        pool_instance.state = PoolState.uninitialized()
        pool_instance.slot0 = Slot0.uninitialized()

        if "initial_price" in kwargs:
            pool_instance.slot0.sqrt_price = kwargs["initial_price"]
            pool_instance.slot0.tick = (
                pool_instance.math.tick_math.get_tick_at_sqrt_ratio(
                    pool_instance.slot0.sqrt_price, pool_instance._rounding_mode
                )
            )

        pool_instance.block_timestamp = kwargs.get(
            "initial_timestamp", int(datetime.datetime.now().timestamp())
        )
        if "initial_block" in kwargs:
            pool_instance.block_number = kwargs["initial_block"]
        else:
            pool_instance.block_number = factory.w3.eth.block_number

        return pool_instance

    @classmethod
    def from_chain(
        cls,
        factory,
        pool_address: str,
        at_block: Optional[int] = None,
        load_pool_state: bool = True,
    ) -> "UniswapV3Pool":
        """Loads a pool from the chain at a given block number"""

        pool = UniswapV3Pool(factory)

        if at_block is None:
            at_block = factory.w3.eth.block_number
            pool.logger.debug(
                f"No at_block specified.  Initializing at 'latest' block: {at_block}"
            )

        contract = factory.w3.eth.contract(
            to_checksum_address(pool_address),
            abi=cls.get_abi(),
        )
        pool.pool_contract = contract
        pool.initialization_block = fetch_initialization_block(contract)
        pool.block_number = at_block
        pool.block_timestamp = factory.w3.eth.get_block(at_block)["timestamp"]

        pool.immutables = fetch_pool_immutables(
            w3=factory.w3, contract=contract, logger=factory.logger
        )

        if load_pool_state:
            pool.state = fetch_pool_state(
                contract=contract,
                token_0=pool.immutables.token_0,
                token_1=pool.immutables.token_1,
                logger=factory.logger,
                at_block=at_block,
            )

            pool.slot0 = fetch_slot_0(
                contract=contract, logger=factory.logger, at_block=at_block
            )

            pool.ticks = fetch_liquidity(
                contract=contract,
                tick_spacing=pool.immutables.tick_spacing,
                logger=factory.logger,
                at_block=at_block,
            )

            pool.positions = fetch_positions(
                contract=contract,
                logger=factory.logger,
                db_session=factory.create_db_session(),
                at_block=at_block,
                initialization_block=pool.initialization_block,
            )
            pool.observations = fetch_observations(
                contract=contract,
                observation_cardinality=pool.slot0.observation_cardinality,
                logger=factory.logger,
                at_block=at_block,
            )
        pool.logger.info(f"Pool initialized at block {pool.initialization_block}")

        return pool

    @classmethod
    def get_abi(cls, json_string: bool = False) -> Union[Dict[str, Any], str]:
        """
        Returns the ABI for a UniswapV3Pool contract

        :param json_string: If True, returns the ABI as a JSON string.  Otherwise, returns a dictionary
        """
        with open(
            Path(__file__).parent.joinpath("UniswapV3Pool.json"), "r"
        ) as abi_json:
            uniswap_v3_abi = json.load(abi_json)

            return json.dumps(uniswap_v3_abi) if json_string else uniswap_v3_abi

    # -----------------------------------------------------------------------------------------------------------
    #  Utility Functions
    # -----------------------------------------------------------------------------------------------------------

    def get_price_at_sqrt_ratio(
        self,
        sqrt_price: int,
        reverse_tokens: bool = False,
    ) -> float:
        """
        Converts a sqrt_price to a human-readable price.

        :param sqrt_price:
            sqrt_price encoded as fixed point Q64.96
        :param reverse_tokens:
            Whether to reverse the tokens in the price.  The sqrt_price represents the
            :math:`\\frac{ Token 1 }{ Token 0}`.  If reverse_tokens is True, the price will be represented as
            :math:`\\frac{ Token 0 }{ Token 1}`.
        """
        token_0, token_1 = self.immutables.token_0, self.immutables.token_1

        raw_price_float = (sqrt_price / (2**96)) ** 2
        adjusted_price = raw_price_float / (10 ** (token_1.decimals - token_0.decimals))

        if reverse_tokens:
            adjusted_price = 1 / adjusted_price

        return adjusted_price

    def get_formatted_price_at_sqrt_ratio(
        self,
        sqrt_price: int,
        reverse_tokens: bool = False,
    ) -> str:
        """
        Converts a sqrt_price to a formatted price string.  Includes rounding to 6 significant figures, and listing
        the Reference Asset, ie WETH: 2245.32 USDC.

        :param sqrt_price:
            sqrt_price encoded as fixed point Q64.96
        :param reverse_tokens:
            Whether to reverse the tokens in the price.  The sqrt_price represents the
            :math:`\\frac{ Token 1 }{ Token 0}`.  If reverse_tokens is True, the price will be represented as
            :math:`\\frac{ Token 0 }{ Token 1}`.
        """

        token_0, token_1 = self.immutables.token_0, self.immutables.token_1

        raw_price_float = (sqrt_price / (2**96)) ** 2
        adjusted_price = raw_price_float / (10 ** (token_1.decimals - token_0.decimals))

        if reverse_tokens:
            adjusted_price = 1 / adjusted_price

        rounded_price = np.format_float_positional(float(f"{adjusted_price:.6g}"))
        return (
            f"{token_0.symbol}: {rounded_price} {token_1.symbol}"
            if reverse_tokens
            else f"{token_1.symbol}: {rounded_price} {token_0.symbol}"
        )

    def get_price_at_tick(
        self, tick: int, reverse_tokens: bool = False, string_description: bool = False
    ) -> Union[float, str]:
        """
        Converts a tick to a human-readable price.

        :param tick:
            Tick value
        :param reverse_tokens:
            Whether to reverse the tokens in the price.  The sqrt_price represents the
            :math:`\\frac{ Token 1 }{ Token 0}`.  If reverse_tokens is True, the price will be represented as
            :math:`\\frac{ Token 0 }{ Token 1}`.
        :param string_description:
            If True, returns a string description of the price in the Format: [WETH: 3,456.23 USDC].
            Otherwise, returns a float.
        """
        sqrt_price = self.math.tick_math.get_sqrt_ratio_at_tick(tick)
        return self.get_price_at_sqrt_ratio(
            sqrt_price, reverse_tokens, string_description
        )

    def __repr__(self):
        return (
            f"{self.immutables.token_0.symbol} <-> {self.immutables.token_1.symbol} "
            f"@ {self.immutables.fee / 100} bips"
        )

    # -----------------------------------------------------------------------------------------------------------
    #  Caching Pool State
    # -----------------------------------------------------------------------------------------------------------

    def save_pool(self, file_path):
        """
        Saves pool state & parameters to JSON file.  This file can later be used to re-initialize a pool
        instance without requiring large numbers of on-chain queries.

        :param file_path: Filepath for JSON save location
        """
        self.logger.info("Json Encoding Pool State")

        pool_state_dict = {
            "initialization_block": self.initialization_block,
            "block_timestamp": self.block_timestamp,
            "block_number": self.block_number,
            "protocol_fee_0": self.protocol_fee_0,
            "protocol_fee_1": self.protocol_fee_1,
            "immutables": {
                **self.immutables.dict(exclude={"token_0", "token_1"}),
                "token_0": self.immutables.token_0.dict(exclude={"contract"}),
                "token_1": self.immutables.token_1.dict(exclude={"contract"}),
            },
            "state": self.state.dict(),
            "slot0": self.slot0.dict(),
            "ticks": {
                index: self.ticks[index].dict() for index in sorted(self.ticks.keys())
            },
            "positions": {
                f"{key[0]}_{key[1]}_{key[2]}": val.dict()
                for key, val in self.positions.items()
            },
            "observations": [obs.dict() for obs in self.observations],
        }
        json.dump(pool_state_dict, file_path)
        self.logger.info("Pool State Saved")

    @classmethod
    def load_pool(cls, file_path, pool_factory):
        """
        Loads a pool from a JSON File generated by the save_state() method
        :param file_path: Filepath of JSON File
        :param pool_factory: Pool Factory
        :return:
        """

        pool_factory.pool_pre_init("uniswap_v3")
        pool_params = json.load(file_path)

        pool = UniswapV3Pool(factory=pool_factory)

        pool.block_timestamp = pool_params["block_timestamp"]
        pool.block_number = pool_params["block_number"]
        pool.initialization_block = pool_params["initialization_block"]
        pool.protocol_fee_0 = pool_params["protocol_fee_0"]
        pool.protocol_fee_1 = pool_params["protocol_fee_1"]

        pool.immutables = parse_obj_as(PoolImmutables, pool_params["immutables"])

        # TODO: This ERC20Token Initialization can be optimized
        pool.immutables.token_0 = ERC20Token.from_chain(
            pool_factory.w3,
            to_checksum_address(pool_params["immutables"]["token_0"]["address"]),
        )
        pool.immutables.token_1 = ERC20Token.from_chain(
            pool_factory.w3,
            to_checksum_address(pool_params["immutables"]["token_1"]["address"]),
        )
        pool.state = parse_obj_as(PoolState, pool_params["state"])
        pool.slot0 = parse_obj_as(Slot0, pool_params["slot0"])

        pool.ticks = {
            int(index): parse_obj_as(Tick, tick)
            for index, tick in pool_params["ticks"].items()
        }
        pool.positions = {
            (
                to_checksum_address((keys := key.split("_"))[0]),
                int(keys[1]),
                int(keys[2]),
            ): parse_obj_as(PositionInfo, position)
            for key, position in pool_params["positions"].items()
        }
        pool.observations = parse_obj_as(
            List[OracleObservation], pool_params["observations"]
        )

        return pool

    # -----------------------------------------------------------------------------------------------------------
    #  Research & Simulation Functionality
    # -----------------------------------------------------------------------------------------------------------

    @classmethod
    def migrate_up(cls, sqlalchemy_engine: Engine):
        """
        Creates uniswap logging & event schema in the database
        :param sqlalchemy_engine:
        :return:
        """
        conn = sqlalchemy_engine.connect()
        if not conn.dialect.has_schema(conn, "uniswap_v3"):
            conn.execute(sqlalchemy.schema.CreateSchema("uniswap_v3"))
            conn.commit()

        UniswapV3Base.metadata.create_all(bind=sqlalchemy_engine)
        UniV3EventBase.metadata.create_all(bind=sqlalchemy_engine)

    def advance_block(self, blocks: int = 1):
        """
        Advances the current block by `blocks` and adds 12 seconds to the block_timestamp for each block progressed
        :param blocks: Number of blocks to advance forward.  Defaults to 1
        """
        self.block_number += blocks
        self.block_timestamp += 12 * blocks

    def save_events(
        self,
        event_name: Literal["Mint", "Burn", "Collect", "Swap", "Flash"],
        chunk_size: Optional[int] = 1_000,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None,
    ):
        """
        Saves events of a given type to the database.

        :param event_name:
            Name of Event to save.  Must be one of "Mint", "Burn", "Collect", "Swap", "Flash"
        :param chunk_size:
            Number of events to save per database commit.  When backfilling Mint, Burn, and Collect events, this value
            can be set to 10-50k to speed up backfilling.  Swaps are much more frequent, and the chunk size should be
            set to 5k on average pools, 1k on the largest pools.  Defaults to 1k
        :param from_block:
            Block number to start backfilling from.  Defaults to the pool's initialization block
        :param to_block:
            Block number to stop backfilling at.  Defaults to the current block number
        """
        backfill_events(
            contract=self.pool_contract,
            event_name=event_name,
            db_session=self.pool_factory.create_db_session(),
            db_model=UniV3MintEvent,
            model_parsing_func=_parse_uniswap_events,
            logger=self.logger,
            from_block=from_block if from_block else self.initialization_block,
            to_block=to_block if to_block else self.pool_factory.w3.eth.block_number,
            chunk_size=chunk_size,
        )
        self.logger.info(f"Finished saving {event_name} events to database")

    def save_position_snapshot(self):
        """
        Saves the current state of the pool to the database

        .. warning::
            Position Snapshots are stored with a primary key of (pool_address, block_number, position_key).

            If you are running multiple simulations on the same pool, you will need to delete the old position logs
            before re-running the position valuation sims.  Otherwise, you will get a primary key violation.  This
            behavior is on the improvement list, but in the meantime, you can delete the old position logs with:

            .. code-block:: sql

                DELETE FROM uniswap_v3.position_logs WHERE pool_address = '0xabcd...1234';
        """
        self.logger.info("Saving position snapshot to database")
        db_models: List[UniV3PositionLogs] = []
        db_session = self.pool_factory.create_db_session()

        for position_key, position in self.positions.items():
            if position.liquidity == 0:
                continue

            # Execute Non-committing burn to compute the token0 & token1 value of position
            token_0_value, token_1_value = self.burn(
                position_key[0],
                position_key[1],
                position_key[2],
                -position.liquidity,
                False,
            )
            token_0_adjusted = self.immutables.token_0.convert_decimals(token_0_value)
            token_1_adjusted = self.immutables.token_1.convert_decimals(token_1_value)

            db_models.append(
                UniV3PositionLogs(
                    block_number=self.block_number,
                    pool_id=self.immutables.pool_address,
                    lp_address=position_key[0],
                    tick_lower=position_key[1],
                    tick_upper=position_key[2],
                    # TODO Double check or equal conditions
                    currently_active=position_key[1]
                    < self.slot0.tick
                    <= position_key[2],
                    token_0_value=token_0_adjusted,
                    token_1_value=token_1_adjusted,
                    token_0_value_usd=None,  # TODO: Add Pricing queries from swap logs
                    token_1_value_usd=None,
                )
            )

        self.logger.info(f"Saving {len(db_models)} position snapshots to database")

        db_session.bulk_save_objects(db_models)
        db_session.commit()
        db_session.close()

    def get_position_valuation(
        self, lp_address: ChecksumAddress, tick_lower: int, tick_upper: int
    ) -> DataFrame:
        """
        Returns a dataframe of position valuation over time

        :param lp_address: Owner of the position
        :param tick_lower: lower tick of the position
        :param tick_upper: upper tick of the position
        :return:
            DataFrame containing the position valuation over time.

            * **block_number** -> Block number of the snapshot
            * **token_0_value** -> Token 0 value of the position
            * **token_1_value** -> Token 1 value of the position
            * **token_0_value_usd** -> Token 0 value of the position in USD
            * **token_1_value_usd** -> Token 1 value of the position in USD
            * **total_value_usd** -> Total value of the position in USD. (token_0_value_usd + token_1_value_usd)

        """
        db_session = self.pool_factory.create_db_session()
        position_valuation = (
            db_session.query(
                UniV3PositionLogs.block_number,
                UniV3PositionLogs.token_0_value,
                UniV3PositionLogs.token_1_value,
                UniV3PositionLogs.token_0_value_usd,
                UniV3PositionLogs.token_1_value_usd,
                UniV3PositionLogs.token_0_value_usd
                + UniV3PositionLogs.token_1_value_usd,
            )
            .filter(
                UniV3PositionLogs.pool_id == self.immutables.pool_address,
                UniV3PositionLogs.lp_address == lp_address,
                UniV3PositionLogs.tick_lower == tick_lower,
                UniV3PositionLogs.tick_upper == tick_upper,
            )
            .order_by(desc(UniV3PositionLogs.block_number))
            .all()
        )
        dataframe = DataFrame.from_records(
            position_valuation,
            columns=[
                "block_number",
                "token_0_value",
                "token_1_value",
                "token_0_value_usd",
                "token_1_value_usd",
                "position_value_usd",
            ],
            coerce_float=True,
        )
        db_session.close()
        return dataframe

    def get_position_valuations_at_block(
        self, block_number: int
    ) -> Dict[Tuple[ChecksumAddress, int, int], Dict[str, Any]]:
        """
        Returns a dictionary of position valuations at a given block number

        :param block_number: block number to query position valuations at.
        :return: Mapping of all positions: (lp_address, tick_lower, tick_upper) -> position_valuation
        """
        # TODO: If block_number is not in the database, return the <= block_number
        db_session = self.pool_factory.create_db_session()
        position_valuations = (
            db_session.query(
                UniV3PositionLogs.lp_address,
                UniV3PositionLogs.tick_lower,
                UniV3PositionLogs.tick_upper,
                UniV3PositionLogs.token_0_value,
                UniV3PositionLogs.token_1_value,
                UniV3PositionLogs.token_0_value_usd,
                UniV3PositionLogs.token_1_value_usd,
                UniV3PositionLogs.token_0_value_usd
                + UniV3PositionLogs.token_1_value_usd,
            )
            .filter(
                UniV3PositionLogs.pool_id == self.immutables.pool_address,
                UniV3PositionLogs.block_number == block_number,
            )
            .all()
        )
        db_session.close()
        output_dict = {}
        for position in position_valuations:
            output_dict.update(
                {
                    (to_checksum_address(position[0]), position[1], position[2]): {
                        "token_0_value": position[3],
                        "token_1_value": position[4],
                        "token_0_value_usd": position[5],
                        "token_1_value_usd": position[6],
                        "position_value_usd": position[7],
                    }
                }
            )
        return output_dict

    def compute_liquidity_at_price(
        self, reverse_tokens: bool = False, compress: bool = False
    ) -> DataFrame:
        """
        Computes the liquidity at each price point in the pool.

        :param reverse_tokens:
            Reverses the reference token in the price.
        :param compress:
            Compresses the output to only include price points where the liquidity changes by more than 10%.
        :return:
            Dataframe with the current token/token price and the active liquidity at that price.
        """
        current_liquidity = 0
        last_liquidity = 1
        liquidity = {"price": [], "active_liquidity": []}
        for tick_index, tick_data in sorted(
            self.ticks.items(), key=lambda t: int(t[0])
        ):
            current_liquidity += tick_data.liquidity_net
            current_price = self.get_price_at_tick(tick_index, reverse_tokens)
            if compress:
                if abs((current_liquidity - last_liquidity) / last_liquidity) > 0.1:
                    liquidity["price"].append(current_price)
                    liquidity["active_liquidity"].append(current_liquidity)

                    last_liquidity = current_liquidity
            else:
                liquidity["price"].append(current_price)
                liquidity["active_liquidity"].append(current_liquidity)

        return DataFrame(liquidity).astype(float)

    def _log_swap(
        self,
        amount_out: int,
        amount_in: int,
        slot_0_start: Slot0,
    ) -> str:
        """Logs a swap to the database"""
        # TODO: Add batching mode to accommodate pnl simulations

        amount_0_adjusted = amount_out / self.immutables.token_0.decimals
        amount_1_adjusted = amount_in / self.immutables.token_1.decimals

        swap_id = uuid4().hex
        swap_model = UniV3SwapLogs(
            swap_id=swap_id,
            write_timestamp=datetime.datetime.fromtimestamp(self.block_timestamp),
            pool_id=self.immutables.pool_address,
            token_in_symbol=self.immutables.token_0.symbol,
            token_in_amount=amount_0_adjusted,
            token_out_symbol=self.immutables.token_1.symbol,
            token_out_amount=amount_1_adjusted,
            pool_start_price=self.get_price_at_sqrt_ratio(slot_0_start.sqrt_price),
            pool_end_price=self.get_price_at_sqrt_ratio(self.slot0.sqrt_price),
            fill_price_token_0=amount_1_adjusted / amount_0_adjusted,
            fill_price_token_1=amount_0_adjusted / amount_1_adjusted,
            fee_token=0,
            fee_amount=0,
        )
        db_session = self.pool_factory.create_db_session()
        db_session.add(swap_model)
        db_session.commit()
        db_session.close()
        return swap_id

    # -----------------------------------------------------------------------------------------------------------
    #  Publicly Exposed Uniswap Pool Methods
    # -----------------------------------------------------------------------------------------------------------

    def mint(
        self,
        recipient: ChecksumAddress,
        tick_lower: int,
        tick_upper: int,
        amount: int,
    ):
        """

        :param ChecksumAddress recipient:
            Owner address of the minted liquidity.
        :param int tick_lower:
            Lower bound of the minted liquidity.
        :param int tick_upper:
            Upper bound of the minted liquidity.
        :param int amount:
            Amount of liquidity to mint.
        """

        if tick_lower >= tick_upper:
            raise UniswapV3Revert("Minting Liquidity within invalid tick bounds")

        if amount <= 0:
            raise UniswapV3Revert("Cannot Mint 0 or Negative Liquidity")

        _, amount_0_int, amount_1_int = self._modify_position(
            recipient,
            tick_lower,
            tick_upper,
            amount,
            True,
        )
        self.state.balance_0 += amount_0_int
        self.state.balance_1 += amount_1_int

    def burn(
        self,
        owner_address: ChecksumAddress,
        tick_lower: int,
        tick_upper: int,
        amount: int,
        committing: Optional[bool] = True,
    ) -> Tuple[int, int]:
        """

        :param owner_address:
            Owner of the liquidity to burn.
        :param tick_lower:
            Lower bound of the liquidity to burn.
        :param tick_upper:
            Upper bound of the liquidity to burn.
        :param amount:
            Amount of liquidity to burn.
        :param committing:
            If True, all computed values are saved into the pool state.
            If False, only computes the token_0 and token_1 value of the position without deactivating or modifying
            the fee accrual of the position
            Default: True
        :return:
        """
        position_info, amount_0_int, amount_1_int = self._modify_position(
            owner_address, tick_lower, tick_upper, -amount, committing
        )

        # TODO: Double check tokens owed
        position_info.tokens_owed_0 += -amount_0_int
        position_info.tokens_owed_1 += -amount_1_int

        if committing:
            self.state.balance_0 += amount_0_int
            self.state.balance_1 += amount_1_int

        return amount_0_int, amount_1_int

    def swap(
        self,
        zero_for_one: bool,
        amount_specified: int,
        sqrt_price_limit: int,
        log_swap: Optional[bool] = False,
    ) -> Optional[str]:
        """
        Swaps tokens in the pool.

        :param zero_for_one:
            Which direction to swap tokens.  If True, sell Token 0 and buy Token 1.  If False, sell Token 1
            and buy Token 0.
        :param amount_specified:
            Raw token amount to swap.  If amount specified is positive, this represents the quantity of tokens to
            sell.  If amount specified is negative, this represents the quantity of tokens to buy.
        :param sqrt_price_limit:
            The maximum/minimum price to allow for the swap.  If the swap would result in a price above this limit,
            the swap will only be executed up to the price sqrt_price_limit.  If the sqrt_price_limit is out of range,
            and no tokens can be swapped, a UniswapV3Revert exception will be raised.
        :param log_swap:
            If True, logs the swap to the database & returns a swap_id that can be used to query the swap data.
            If False, does not log the swap to the database & returns None.  Default: False

        """
        # Disable branch & statement checks.  This implementation will be complex regardless
        # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        self.logger.debug(
            f"------ Swapping Token {0 if zero_for_one else 1} for Token {1 if zero_for_one else 0} -------"
        )
        self.logger.debug(f"Swap Amount: {amount_specified}")
        self.logger.debug(
            f"Price Limit: {self.get_price_at_sqrt_ratio(sqrt_price_limit)}"
        )
        self.logger.debug(
            f"Current Price: {self.get_price_at_sqrt_ratio(self.slot0.sqrt_price)}"
        )

        if amount_specified == 0:
            raise UniswapV3Revert("Cannot swap 0 tokens")

        if zero_for_one:
            if sqrt_price_limit >= self.slot0.sqrt_price:
                raise UniswapV3Revert(
                    "sqrt_price_limit above current price, cannot swap 0 for 1"
                )
            if sqrt_price_limit < self.math.tick_math.MIN_SQRT_RATIO:
                raise UniswapV3Revert("sqrt_price_limit too low")
        else:
            if sqrt_price_limit <= self.slot0.sqrt_price:
                raise UniswapV3Revert(
                    "sqrt_price_limit below current price, cannot swap 1 for 0"
                )
            if sqrt_price_limit > self.math.tick_math.MAX_SQRT_RATIO:
                raise UniswapV3Revert("sqrt_price_limit too high")

        slot_0_start = self.slot0.copy()

        # Disable pylint no-member due to SwapState and SwapCache raising false positives
        # pylint: disable=no-member

        swap_cache = SwapCache(
            liquidity_start=self.state.liquidity,
            block_timestamp=self.block_timestamp,
            fee_protocol=slot_0_start.fee_protocol % 16
            if zero_for_one
            else slot_0_start.fee_protocol >> 4,
            seconds_per_liquidity_cumulative=0,
            tick_cumulative=0,
            computed_last_observation=False,
        )

        exact_input = amount_specified > 0
        state: SwapState = SwapState(
            amount_specified_remaining=amount_specified,
            amount_calculated=0,
            sqrt_price=slot_0_start.sqrt_price,
            tick=slot_0_start.tick,
            fee_growth_global=self.state.fee_growth_global_0
            if zero_for_one
            else self.state.fee_growth_global_1,
            protocol_fee=0,
            liquidity=swap_cache.liquidity_start,
        )

        while (
            state.amount_specified_remaining != 0
            and state.sqrt_price != sqrt_price_limit
        ):
            self.logger.debug("----- Stating Swap Step -----")
            self.logger.debug(f"Active Liquidity: {state.liquidity}")
            self.logger.debug(f"Current Tick: {state.tick}")

            step = SwapStep(sqrt_price_start=state.sqrt_price)
            step.tick_next = self._get_next_initialized_tick_index(
                state.tick, zero_for_one
            )

            if step.tick_next < self.math.tick_math.MIN_TICK:
                step.tick_next = self.math.tick_math.MIN_TICK
            if step.tick_next > self.math.tick_math.MAX_TICK:
                step.tick_next = self.math.tick_math.MAX_TICK

            step.sqrt_price_next = self.math.tick_math.get_sqrt_ratio_at_tick(
                step.tick_next, self._rounding_mode
            )
            sqrt_price_target = (
                sqrt_price_limit
                if (
                    step.sqrt_price_next < sqrt_price_limit
                    if zero_for_one
                    else step.sqrt_price_next > sqrt_price_limit
                )
                else step.sqrt_price_next
            )

            computed_swap_step = self.math.compute_swap_step(
                state.sqrt_price,
                sqrt_price_target,
                state.liquidity,
                state.amount_specified_remaining,
                self.immutables.fee,
                self._rounding_mode,
            )
            self.logger.debug("--- Computed Swap Step --- ")
            self.logger.debug(f"sqrt_price_current: {state.sqrt_price}")
            self.logger.debug(f"sqrt_price_target: {sqrt_price_target}")
            for name, val in computed_swap_step.dict().items():
                self.logger.debug(f"{name}: {val}")

            (
                state.sqrt_price,
                step.amount_in,
                step.amount_out,
                step.fee_amount,
            ) = (
                computed_swap_step.sqrt_price_next,
                computed_swap_step.amount_in,
                computed_swap_step.amount_out,
                computed_swap_step.fee_amount,
            )

            if exact_input:
                state.amount_specified_remaining -= step.amount_in + step.fee_amount
                state.amount_calculated = state.amount_calculated - step.amount_out
            else:
                state.amount_specified_remaining += step.amount_out
                state.amount_calculated = (
                    state.amount_calculated + step.amount_in + step.fee_amount
                )
            self.logger.debug(
                f"Amount Specified Remaining: {state.amount_specified_remaining}"
                f"\t Amount Calculated: {state.amount_calculated}"
            )

            if swap_cache.fee_protocol > 0:
                delta = floor(
                    Decimal(step.fee_amount) / Decimal(swap_cache.fee_protocol)
                )
                step.fee_amount -= delta
                state.protocol_fee += delta

            if state.liquidity > 0:
                state.fee_growth_global += self.math.full_math.mul_div(
                    step.fee_amount,
                    self.math.Q128,
                    state.liquidity,
                    self._rounding_mode,
                )

            if state.sqrt_price == step.sqrt_price_next:
                self.logger.debug(
                    "--- SQRT Price has reached limit, crossing ticks ---"
                )
                min_tick, max_tick = (
                    self.math.tick_math.MAX_TICK,
                    self.math.tick_math.MIN_TICK,
                )
                # SQRT Price has been moved to end of tick boundary.  Move to next tick or exit
                if (step.tick_next == max_tick and state.tick == max_tick) or (
                    step.tick_next == min_tick and state.tick == min_tick
                ):
                    break  # Not standard behavior

                if not swap_cache.computed_last_observation:
                    (
                        swap_cache.tick_cumulative,
                        swap_cache.seconds_per_liquidity_cumulative,
                    ) = self._observe_single(
                        self.block_timestamp,
                        0,
                        slot_0_start.tick,
                        slot_0_start.observation_index,
                        swap_cache.liquidity_start,
                        slot_0_start.observation_cardinality,
                    )
                    swap_cache.computed_last_observation = True
                liquidity_net = self._cross_tick(
                    step.tick_next,
                    state.fee_growth_global
                    if zero_for_one
                    else self.state.fee_growth_global_0,
                    self.state.fee_growth_global_1
                    if zero_for_one
                    else state.fee_growth_global,
                    swap_cache.seconds_per_liquidity_cumulative,
                    swap_cache.tick_cumulative,
                    swap_cache.block_timestamp,
                )
                self.logger.debug(
                    f"Crossing Tick {step.tick_next} & Adding Liquidity: {(-1 if zero_for_one else 1) * liquidity_net}"
                )

                state.liquidity += -liquidity_net if zero_for_one else liquidity_net
                if state.liquidity < 0 or state.liquidity >= 2**128:
                    raise ValueError("Liquidity out of range")
                state.tick = step.tick_next - 1 if zero_for_one else step.tick_next

            elif state.sqrt_price != step.sqrt_price_start:
                state.tick = self.math.tick_math.get_tick_at_sqrt_ratio(
                    state.sqrt_price, self._rounding_mode
                )

        if state.tick != slot_0_start.tick:
            observation_index, observation_cardinality = self._write_observation(
                slot_0_start.observation_index,
                swap_cache.block_timestamp,
                slot_0_start.tick,
                swap_cache.liquidity_start,
                slot_0_start.observation_cardinality,
                slot_0_start.observation_cardinality_next,
            )

            self.slot0.sqrt_price = state.sqrt_price
            self.slot0.tick = state.tick
            self.slot0.observation_index = observation_index
            self.slot0.observation_cardinality = observation_cardinality
        else:
            self.slot0.sqrt_price = state.sqrt_price

        if swap_cache.liquidity_start != state.liquidity:
            self.state.liquidity = state.liquidity

        if zero_for_one:
            self.state.fee_growth_global_0 = state.fee_growth_global
            if state.protocol_fee > 0:
                self.protocol_fee_0 += state.protocol_fee
        else:
            self.state.fee_growth_global_1 = state.fee_growth_global
            if state.protocol_fee > 0:
                self.protocol_fee_1 += state.protocol_fee

        if zero_for_one == exact_input:
            amount_0, amount_1 = (
                amount_specified - state.amount_specified_remaining,
                state.amount_calculated,
            )
        else:
            amount_0, amount_1 = (
                state.amount_calculated,
                amount_specified - state.amount_specified_remaining,
            )

        # pylint: enable=no-member,too-many-locals,too-many-branches,too-many-statements
        self.logger.debug("--- Swap Complete ---")
        self.logger.debug(f"Token 0 Delta: {amount_0} \t Token 1 Delta: {amount_1}")
        self.logger.debug(f"Current Tick: {self.slot0.tick}")
        self.logger.debug(f"Current Sqrt Price: {self.slot0.sqrt_price}")
        self.logger.debug(f"Current Liquidity: {self.state.liquidity}")

        self.state.balance_0 += amount_0
        self.state.balance_1 += amount_1

        if log_swap:
            return self._log_swap(
                amount_out=amount_1 if zero_for_one else amount_0,
                amount_in=amount_0 if zero_for_one else amount_1,
                slot_0_start=slot_0_start,
            )

        return None

    # -----------------------------------------------------------------------------------------------------------
    # Internal Uniswap Methods
    #   - These are the internal primitives V3 utilizes to track liquidity in a gas optimized fashion
    #   - While these are public methods, it is advised to use the above constructs to interact with pools
    # -----------------------------------------------------------------------------------------------------------

    def _get_next_initialized_tick_index(
        self, current_tick: int, less_than_or_equal: bool
    ) -> int:
        ticks = sorted(self.ticks.keys())
        self.logger.debug(f"Current Search Tick: {current_tick}\tTicks: {ticks}")
        try:
            current_tick_index = ticks.index(current_tick)
            lower_index, upper_index = current_tick_index, current_tick_index + 1
        except ValueError:
            upper_index = bisect.bisect_right(ticks, current_tick)
            lower_index = upper_index - 1

        if less_than_or_equal:  # Look for initialized tick below current tick
            return (
                self.math.tick_math.MIN_TICK if lower_index < 0 else ticks[lower_index]
            )

        return (
            self.math.tick_math.MAX_TICK
            if len(ticks) <= upper_index
            else ticks[upper_index]
        )

    def _update_tick(  # pylint: disable=too-many-arguments
        self,
        tick: int,
        tick_current: int,
        liquidity_delta: int,
        fee_growth_global_0: int,
        fee_growth_global_1: int,
        seconds_per_liquidity_cumulative: int,
        tick_cumulative: int,
        time: int,
        upper: bool,
        max_liquidity: int,
    ) -> bool:
        tick_info = self.ticks.get(tick, Tick.uninitialized())
        liquidity_gross_before = tick_info.liquidity_gross
        liquidity_gross_after = liquidity_gross_before + liquidity_delta

        if liquidity_gross_after > max_liquidity:
            raise UniswapV3Revert(
                f"Tick Liquidity ({liquidity_gross_after}) Overflows Max Liquidity ({max_liquidity})"
            )

        flipped = (liquidity_gross_before == 0) != (liquidity_gross_after == 0)

        if liquidity_gross_before == 0:
            if tick <= tick_current:
                tick_info.fee_growth_outside_0 = fee_growth_global_0
                tick_info.fee_growth_outside_1 = fee_growth_global_1
                tick_info.seconds_per_liquidity_outside = (
                    seconds_per_liquidity_cumulative
                )
                tick_info.tick_cumulative_outside = tick_cumulative
                tick_info.seconds_outside = time

        tick_info.liquidity_gross = liquidity_gross_after
        tick_info.liquidity_net = tick_info.liquidity_net + (
            (-1 if upper else 1) * liquidity_delta
        )

        self.ticks[tick] = tick_info

        return flipped

    def _get_tick(self, tick: int) -> Optional[Tick]:
        try:
            return self.ticks[tick]
        except KeyError:
            return None

    def _set_tick(self, tick: int, tick_data: Tick):
        self.ticks.update({tick: tick_data})

    def _clear_tick(self, tick: int):
        self.ticks.pop(tick)

    def _cross_tick(
        self,
        tick: int,
        fee_growth_global_0: int,
        fee_growth_global_1: int,
        seconds_per_liquidity_cumulative: int,
        tick_cumulative: int,
        time: int,
    ) -> int:
        tick_info = self.ticks[tick]

        tick_info.fee_growth_outside_0 = (
            fee_growth_global_0 - tick_info.fee_growth_outside_0
        )
        tick_info.fee_growth_outside_1 = (
            fee_growth_global_1 - tick_info.fee_growth_outside_1
        )
        tick_info.seconds_per_liquidity_outside = (
            seconds_per_liquidity_cumulative - tick_info.seconds_per_liquidity_outside
        )
        tick_info.tick_cumulative_outside = (
            tick_cumulative - tick_info.tick_cumulative_outside
        )
        tick_info.seconds_outside = time - tick_info.seconds_outside

        return tick_info.liquidity_net

    def _transform_oracle_observation(
        self,
        transform_observation: OracleObservation,
        block_timestamp: int,
        tick: int,
        liquidity: int,
    ) -> OracleObservation:
        delta = block_timestamp - transform_observation.block_timestamp
        seconds_per_liquidity = (
            transform_observation.seconds_per_liquidity_cumulative
            + floor(Decimal(delta << 128) / Decimal(liquidity if liquidity > 0 else 1))
        )
        return OracleObservation(
            block_timestamp=block_timestamp,
            tick_cumulative=transform_observation.tick_cumulative + (tick * delta),
            seconds_per_liquidity_cumulative=seconds_per_liquidity,
            initialized=True,
        )

    # def _initialize_oracle_observation(
    #     self, initialization_time: int
    # ) -> Tuple[int, int]:
    #     self.observations[0] = OracleObservation(
    #         block_timstamp=initialization_time,
    #         tick_cumulative=0,
    #         seconds_per_liquidity_cumulative=0,
    #         initialized=True,
    #     )
    #     return 1, 1

    def _write_observation(
        self,
        index: int,
        block_timestamp: int,
        tick: int,
        liquidity: int,
        cardinality: int,
        cardinality_next: int,
    ) -> Tuple[int, int]:
        try:
            last_observation = self.observations[index]
        except IndexError:
            last_observation = OracleObservation.uninitialized()
        if (
            last_observation.block_timestamp == block_timestamp
        ):  # Observation already written for block
            return index, cardinality

        if cardinality_next > cardinality and index == cardinality - 1:
            updated_cardinality = cardinality_next
        else:
            updated_cardinality = cardinality

        updated_index = (index + 1) % updated_cardinality
        updated_observation = self._transform_oracle_observation(
            last_observation, block_timestamp, tick, liquidity
        )
        try:
            self.observations[updated_index] = updated_observation
        except IndexError:
            self.observations.append(updated_observation)

        return updated_index, updated_cardinality

    def _observation_binary_search(
        self, target: int, index: int, cardinality: int
    ) -> Tuple[OracleObservation, OracleObservation]:
        left = (index + 1) % cardinality
        right = left + cardinality - 1

        while True:
            i = floor((left + right) / 2)
            try:
                before_or_at = self.observations[i % cardinality]
            except IndexError:
                left = i + 1
                continue

            if not before_or_at.initialized:
                left = i + 1
                continue

            at_or_after = self.observations[(i + 1) % cardinality]
            target_at_or_after = before_or_at.block_timestamp <= target

            if target_at_or_after and target <= at_or_after.block_timestamp:
                return before_or_at, at_or_after

            if not target_at_or_after:
                right = i - 1
            else:
                left = i + 1

    def _get_surrounding_observations(
        self,
        target: int,
        tick: int,
        index: int,
        liquidity: int,
        cardinality: int,
    ) -> Tuple[OracleObservation, Optional[OracleObservation]]:
        before_or_at = self.observations[index]

        if before_or_at.block_timestamp <= target:
            if before_or_at.block_timestamp == target:
                return before_or_at, None

            return before_or_at, self._transform_oracle_observation(
                before_or_at, target, tick, liquidity
            )

        try:
            before_or_at = self.observations[(index + 1) % cardinality]
        except IndexError:
            before_or_at = self.observations[0]
        if not before_or_at.initialized:
            before_or_at = self.observations[0]

        if before_or_at.block_timestamp > target:
            raise UniswapV3Revert("Oracle Observation Record Too Old")

        return self._observation_binary_search(target, index, cardinality)

    def _observe_single(
        self,
        time: int,
        seconds_ago: int,
        tick: int,
        index: int,
        liquidity: int,
        cardinality: int,
    ) -> Tuple[int, int]:
        if seconds_ago == 0:
            try:
                last_observation = self.observations[index]
            except IndexError:
                last_observation = OracleObservation.uninitialized()
            if last_observation.block_timestamp != time:
                last_observation = self._transform_oracle_observation(
                    last_observation, time, tick, liquidity
                )
            return (
                last_observation.tick_cumulative,
                last_observation.seconds_per_liquidity_cumulative,
            )

        target = time - seconds_ago
        before_or_at, at_or_after = self._get_surrounding_observations(
            target, tick, index, liquidity, cardinality
        )

        if target == before_or_at.block_timestamp or at_or_after is None:
            return (
                before_or_at.tick_cumulative,
                before_or_at.seconds_per_liquidity_cumulative,
            )
        if target == at_or_after.block_timestamp:
            return (
                at_or_after.tick_cumulative,
                at_or_after.seconds_per_liquidity_cumulative,
            )
        observation_time_delta = Decimal(
            at_or_after.block_timestamp - before_or_at.block_timestamp
        )
        target_delta = target - before_or_at.block_timestamp

        tick_cumulative = before_or_at.tick_cumulative + (
            floor(
                Decimal(at_or_after.tick_cumulative - before_or_at.tick_cumulative)
                / observation_time_delta
            )
            * target_delta
        )
        seconds_per_liquidity = before_or_at.seconds_per_liquidity_cumulative + floor(
            Decimal(
                (
                    at_or_after.seconds_per_liquidity_cumulative
                    - before_or_at.seconds_per_liquidity_cumulative
                )
                * target_delta
            )
            / observation_time_delta
        )

        return tick_cumulative, seconds_per_liquidity

    def _observe(
        self,
        time: int,
        seconds_ago: List[int],
        tick: int,
        index: int,
        liquidity: int,
        cardinality: int,
    ) -> Tuple[List[int], List[int]]:
        if cardinality <= 0:
            raise UniswapV3Revert("Cardinality of Oracle set to Zero")

        ticks_cumulative: List[int] = []
        seconds_per_liquidity_cumulative: List[int] = []

        for i, sec_ago in enumerate(seconds_ago):
            tick_cumulative, second_per_liquidity_cumulative = self._observe_single(
                time, sec_ago, tick, index, liquidity, cardinality
            )
            ticks_cumulative[i] = tick_cumulative
            seconds_per_liquidity_cumulative[i] = second_per_liquidity_cumulative

        return ticks_cumulative, seconds_per_liquidity_cumulative

    def _update_position(
        self,
        owner_address: ChecksumAddress,
        tick_lower: int,
        tick_upper: int,
        liquidity_delta: int,
        current_tick: int,
        committing: bool,
    ) -> PositionInfo:
        if committing:
            try:
                position_info = self.positions[(owner_address, tick_lower, tick_upper)]
            except KeyError:
                position_info = PositionInfo.uninitialized()
                self.positions.update(
                    {(owner_address, tick_lower, tick_upper): position_info}
                )
        else:
            position_info = self.positions.get(
                (owner_address, tick_lower, tick_upper), PositionInfo.uninitialized()
            ).copy()
        block_timestamp = self.block_timestamp

        if liquidity_delta == 0:  # Not actual revert case in solidity
            raise UniswapV3Revert("Cannot update position with Zero liquidity delta")

        if committing:
            tick_cumulative, seconds_per_liquidity_cumulative = self._observe_single(
                block_timestamp,
                0,
                self.slot0.tick,
                self.slot0.observation_index,
                self.state.liquidity,
                self.slot0.observation_cardinality,
            )
            flipped_lower = self._update_tick(
                tick_lower,
                current_tick,
                liquidity_delta,
                self.state.fee_growth_global_0,
                self.state.fee_growth_global_1,
                seconds_per_liquidity_cumulative,
                tick_cumulative,
                block_timestamp,
                False,
                self.immutables.max_liquidity_per_tick,
            )
            flipped_upper = self._update_tick(
                tick_upper,
                current_tick,
                liquidity_delta,
                self.state.fee_growth_global_0,
                self.state.fee_growth_global_1,
                seconds_per_liquidity_cumulative,
                tick_cumulative,
                block_timestamp,
                True,
                self.immutables.max_liquidity_per_tick,
            )

        fee_growth_inside_0, fee_growth_inside_1 = self._get_fee_growth_inside(
            tick_lower,
            tick_upper,
            current_tick,
            self.state.fee_growth_global_0,
            self.state.fee_growth_global_1,
        )

        position_info = self._update_position_info(
            position_info, liquidity_delta, fee_growth_inside_0, fee_growth_inside_1
        )
        if committing:
            # TODO: Clean this up.  Popping unused ticks can be done with update_tick and set_tick
            if liquidity_delta < 0:
                if flipped_lower:
                    self.ticks.pop(tick_lower)
                if flipped_upper:
                    self.ticks.pop(tick_upper)

        return position_info

    def _modify_position(
        self,
        owner_address: ChecksumAddress,
        tick_lower: int,
        tick_upper: int,
        liquidity_delta: int,
        committing: bool,
    ) -> Tuple[PositionInfo, int, int]:
        self.math.check_ticks(tick_lower, tick_upper)
        position = self._update_position(
            owner_address,
            tick_lower,
            tick_upper,
            liquidity_delta,
            self.slot0.tick,
            committing,
        )

        if liquidity_delta == 0:
            raise UniswapV3Revert("Modifying Position without Changing Liquidity")

        amount_0, amount_1 = 0, 0

        if self.slot0.tick < tick_lower:
            amount_0 = self.math.get_amount_0_delta(
                self.math.tick_math.get_sqrt_ratio_at_tick(
                    tick_lower, self._rounding_mode
                ),
                self.math.tick_math.get_sqrt_ratio_at_tick(
                    tick_upper, self._rounding_mode
                ),
                liquidity_delta,
                self._rounding_mode,
            )
        elif self.slot0.tick < tick_upper:
            if committing:
                self._write_observation(
                    self.slot0.observation_index,
                    self.block_timestamp,
                    self.slot0.tick,
                    self.state.liquidity,
                    self.slot0.observation_cardinality,
                    self.slot0.observation_cardinality_next,
                )
            amount_0 = self.math.get_amount_0_delta(
                self.slot0.sqrt_price,
                self.math.tick_math.get_sqrt_ratio_at_tick(
                    tick_upper, self._rounding_mode
                ),
                liquidity_delta,
                self._rounding_mode,
            )
            amount_1 = self.math.get_amount_1_delta(
                self.math.tick_math.get_sqrt_ratio_at_tick(
                    tick_lower, self._rounding_mode
                ),
                self.slot0.sqrt_price,
                liquidity_delta,
                self._rounding_mode,
            )
            if committing:
                self.state.liquidity += liquidity_delta
        else:
            amount_1 = self.math.get_amount_1_delta(
                self.math.tick_math.get_sqrt_ratio_at_tick(
                    tick_lower, self._rounding_mode
                ),
                self.math.tick_math.get_sqrt_ratio_at_tick(
                    tick_upper, self._rounding_mode
                ),
                liquidity_delta,
                self._rounding_mode,
            )

        return position, amount_0, amount_1

    def _update_position_info(
        self,
        position_info: PositionInfo,
        liquidity_delta: int,
        fee_growth_inside_0: int,
        fee_growth_inside_1: int,
    ):
        if liquidity_delta == 0:
            raise UniswapV3Revert("Cannot Update Positions with 0 Liquidity Delta")

        liquidity_next = position_info.liquidity + liquidity_delta

        token_0_delta = uint_over_under_flow(
            fee_growth_inside_0 - position_info.fee_growth_inside_0_last, 256
        )
        token_1_delta = uint_over_under_flow(
            fee_growth_inside_1 - position_info.fee_growth_inside_1_last, 256
        )

        self.logger.debug(
            f"Calculating Tokens Owed.  Liquidity Delta: {liquidity_delta}, "
            f"Fee Growth 0: {token_0_delta}, Fee Growth 1: {token_1_delta}"
        )

        tokens_owed_0 = self.math.full_math.mul_div(
            token_0_delta,
            position_info.liquidity,
            Q128,
            exact_rounding=self._rounding_mode,
        )

        tokens_owed_1 = self.math.full_math.mul_div(
            token_1_delta,
            position_info.liquidity,
            Q128,
            exact_rounding=self._rounding_mode,
        )

        position_info.liquidity = liquidity_next
        position_info.fee_growth_inside_0_last = fee_growth_inside_0
        position_info.fee_growth_inside_1_last = fee_growth_inside_1
        if tokens_owed_0 > 0 or tokens_owed_1 > 0:
            tokens_owed_0 += tokens_owed_0
            tokens_owed_1 += tokens_owed_1

        return position_info

    def _set_position_info(
        self,
        position_info: PositionInfo,
        owner_address: ChecksumAddress,
        tick_lower,
        tick_upper,
    ):
        self.positions.update({(owner_address, tick_lower, tick_upper): position_info})

    def _get_position_info(
        self, owner_address: ChecksumAddress, tick_lower: int, tick_upper: int
    ) -> PositionInfo:
        return self.positions[(owner_address, tick_lower, tick_upper)]

    def _get_fee_growth_inside(
        self,
        tick_lower: int,
        tick_upper: int,
        tick_current: int,
        fee_growth_global_0: int,
        fee_growth_global_1: int,
    ) -> Tuple[int, int]:
        tick_lower_data, tick_upper_data = (
            self.ticks.get(tick_lower, Tick.uninitialized()),
            self.ticks.get(tick_upper, Tick.uninitialized()),
        )

        if tick_current >= tick_lower:
            fee_growth_below_0 = tick_lower_data.fee_growth_outside_0
            fee_growth_below_1 = tick_lower_data.fee_growth_outside_1
        else:
            fee_growth_below_0 = (
                fee_growth_global_0 - tick_lower_data.fee_growth_outside_0
            )
            fee_growth_below_1 = (
                fee_growth_global_1 - tick_lower_data.fee_growth_outside_1
            )

        if tick_current < tick_upper:
            fee_growth_above_0 = tick_upper_data.fee_growth_outside_0
            fee_growth_above_1 = tick_upper_data.fee_growth_outside_1
        else:
            fee_growth_above_0 = (
                fee_growth_global_0 - tick_upper_data.fee_growth_outside_0
            )
            fee_growth_above_1 = (
                fee_growth_global_1 - tick_upper_data.fee_growth_outside_1
            )
        fee_growth_inside_0 = (
            fee_growth_global_0 - fee_growth_below_0 - fee_growth_above_0
        )
        fee_growth_inside_1 = (
            fee_growth_global_1 - fee_growth_below_1 - fee_growth_above_1
        )

        # The Uniswap V3 Code allows overflows and underflows here.  Replicating solidity behavior

        return (
            uint_over_under_flow(fee_growth_inside_0, 256),
            uint_over_under_flow(fee_growth_inside_1, 256),
        )
