# type: ignore
import copy
import json
import logging
import math
import os
from pathlib import Path
from typing import List, Optional

import pytest
from eth_utils import to_checksum_address
from pydantic import BaseModel

from nethermind.entro.exceptions import UniswapV3Revert
from nethermind.entro.types.uniswap_v3 import Slot0
from nethermind.entro.uniswap_v3 import UniswapV3Pool
from nethermind.entro.uniswap_v3.math import UniswapV3Math
from nethermind.entro.uniswap_v3.math.shared import (
    MAX_SQRT_RATIO,
    MAX_TICK,
    MIN_SQRT_RATIO,
    MIN_TICK,
)
from tests.uniswap_v3.utils import decode_sqrt_price, encode_sqrt_price
from tests.utils import expand_to_decimals

UniswapV3Math.initialize_exact_math()


class TestArbitrages:
    pass


class SwapCase(BaseModel):
    zero_for_one: bool
    exact_out: Optional[bool]
    amount_0: Optional[int]
    amount_1: Optional[int]
    sqrt_price_limit: Optional[int]


class Position(BaseModel):
    tick_lower: int
    tick_upper: int
    liquidity: int


class PoolTestCase(BaseModel):
    fee_amount: int
    tick_spacing: int
    starting_price: int
    positions: List[Position]


LIQUIDITY_PROVIDER_ADDRESS = to_checksum_address("0xabcde12345abcde12345abcde12345abcde12345")

MID_FEE_MIN_TICK = math.ceil(MIN_TICK / 60) * 60
MID_FEE_MAX_TICK = math.floor(MAX_TICK / 60) * 60

SWAP_CASES = {
    # Swap Large Amounts In <-> Out
    "swap_exact_1000000000000000000_token_0_for_token_1": SwapCase(
        zero_for_one=True,
        exact_out=False,
        amount_0=expand_to_decimals(1, 18),
    ),
    "swap_exact_1000000000000000000_token_1_for_token_0": SwapCase(
        zero_for_one=False,
        exact_out=False,
        amount_1=expand_to_decimals(1, 18),
    ),
    "swap_token_0_for_exact_1000000000000000000_token_1": SwapCase(
        zero_for_one=True,
        exact_out=True,
        amount_1=expand_to_decimals(1, 18),
    ),
    "swap_token_1_for_exact_1000000000000000000_token_0": SwapCase(
        zero_for_one=False,
        exact_out=True,
        amount_0=expand_to_decimals(1, 18),
    ),
    # Swap Large Amounts In <-> Out with price limit
    "swap_exact_1000000000000000000_token_0_for_token_1_to_price_0_5": SwapCase(
        zero_for_one=True,
        exact_out=False,
        amount_0=expand_to_decimals(1, 18),
        sqrt_price_limit=encode_sqrt_price(50, 100),
    ),
    "swap_exact_1000000000000000000_token_1_for_token_0_to_price_2": SwapCase(
        zero_for_one=False,
        exact_out=False,
        amount_1=expand_to_decimals(1, 18),
        sqrt_price_limit=encode_sqrt_price(200, 100),
    ),
    "swap_token_0_for_exact_1000000000000000000_token_1_to_price_0_5": SwapCase(
        zero_for_one=True,
        exact_out=True,
        amount_1=expand_to_decimals(1, 18),
        sqrt_price_limit=encode_sqrt_price(50, 100),
    ),
    "swap_token_1_for_exact_1000000000000000000_token_0_to_price_2": SwapCase(
        zero_for_one=False,
        exact_out=True,
        amount_0=expand_to_decimals(1, 18),
        sqrt_price_limit=encode_sqrt_price(200, 100),
    ),
    # Swap Small Amounts In <-> Out
    "swap_exact_10000_token_0_for_token_1": SwapCase(
        zero_for_one=True,
        exact_out=False,
        amount_0=1000,
    ),
    "swap_exact_10000_token_1_for_token_0": SwapCase(
        zero_for_one=False,
        exact_out=False,
        amount_1=1000,
    ),
    "swap_token_0_for_exact_10000_token_1": SwapCase(
        zero_for_one=True,
        exact_out=True,
        amount_1=1000,
    ),
    "swap_token_1_for_exact_10000_token_0": SwapCase(
        zero_for_one=False,
        exact_out=True,
        amount_0=1000,
    ),
    # Swap Arbitrary Input to Price
    # swap token0 for token1 to price 0.40000
    "swap_token_1_for_token_0_to_price_2_5": SwapCase(
        zero_for_one=False,
        sqrt_price_limit=encode_sqrt_price(5, 2),
    ),
    "swap_token_0_for_token_1_to_price_0_4": SwapCase(
        zero_for_one=True,
        sqrt_price_limit=encode_sqrt_price(2, 5),
    ),
    "swap_token_0_for_token_1_to_price_2_5": SwapCase(
        zero_for_one=True,
        sqrt_price_limit=encode_sqrt_price(5, 2),
    ),
    "swap_token_1_for_token_0_to_price_0_4": SwapCase(
        zero_for_one=False,
        sqrt_price_limit=encode_sqrt_price(2, 5),
    ),
}

TEST_POOLS = {
    "low_fee_1_1_price_2e18_max_range_liquidity": PoolTestCase(
        fee_amount=500,
        tick_spacing=10,
        starting_price=encode_sqrt_price(1, 1),
        positions=[
            Position(
                tick_lower=math.ceil(MIN_TICK / 10) * 10,
                tick_upper=math.floor(MAX_TICK / 10) * 10,
                liquidity=expand_to_decimals(2, 18),
            )
        ],
    ),
    "medium_fee_1_1_price_2e18_max_range_liquidity": PoolTestCase(
        fee_amount=3000,
        tick_spacing=60,
        starting_price=encode_sqrt_price(1, 1),
        positions=[
            Position(
                tick_lower=MID_FEE_MIN_TICK,
                tick_upper=MID_FEE_MAX_TICK,
                liquidity=expand_to_decimals(2, 18),
            )
        ],
    ),
    "high_fee_1_1_price_2e18_max_range_liquidity": PoolTestCase(
        fee_amount=10000,
        tick_spacing=200,
        starting_price=encode_sqrt_price(1, 1),
        positions=[
            Position(
                tick_lower=math.ceil(MIN_TICK / 200) * 200,
                tick_upper=math.floor(MAX_TICK / 200) * 200,
                liquidity=expand_to_decimals(2, 18),
            )
        ],
    ),
    "medium_fee_10_1_price_2e18_max_range_liquidity": PoolTestCase(
        fee_amount=3000,
        tick_spacing=60,
        starting_price=encode_sqrt_price(10, 1),
        positions=[
            Position(
                tick_lower=MID_FEE_MIN_TICK,
                tick_upper=MID_FEE_MAX_TICK,
                liquidity=expand_to_decimals(2, 18),
            )
        ],
    ),
    "medium_fee_1_10_price_2e18_max_range_liquidity": PoolTestCase(
        fee_amount=3000,
        tick_spacing=60,
        starting_price=encode_sqrt_price(1, 10),
        positions=[
            Position(
                tick_lower=MID_FEE_MIN_TICK,
                tick_upper=MID_FEE_MAX_TICK,
                liquidity=expand_to_decimals(2, 18),
            )
        ],
    ),
    "medium_fee_1_1_price_0_liquidity_all_liquidity_around_current_price": PoolTestCase(
        fee_amount=3000,
        tick_spacing=60,
        starting_price=encode_sqrt_price(1, 1),
        positions=[
            Position(
                tick_lower=MID_FEE_MIN_TICK,
                tick_upper=-60,
                liquidity=expand_to_decimals(2, 18),
            ),
            Position(
                tick_lower=60,
                tick_upper=MID_FEE_MAX_TICK,
                liquidity=expand_to_decimals(2, 18),
            ),
        ],
    ),
    "medium_fee_1_1_price_additional_liquidity_around_current_price": PoolTestCase(
        fee_amount=3000,
        tick_spacing=60,
        starting_price=encode_sqrt_price(1, 1),
        positions=[
            Position(
                tick_lower=MID_FEE_MIN_TICK,
                tick_upper=MID_FEE_MAX_TICK,
                liquidity=expand_to_decimals(2, 18),
            ),
            Position(
                tick_lower=MID_FEE_MIN_TICK,
                tick_upper=-60,
                liquidity=expand_to_decimals(2, 18),
            ),
            Position(
                tick_lower=60,
                tick_upper=MID_FEE_MAX_TICK,
                liquidity=expand_to_decimals(2, 18),
            ),
        ],
    ),
    "low_fee_large_liquidity_around_current_price_stableswap": PoolTestCase(
        fee_amount=500,
        tick_spacing=10,
        starting_price=encode_sqrt_price(1, 1),
        positions=[Position(tick_lower=-10, tick_upper=10, liquidity=expand_to_decimals(2, 18))],
    ),
    "medium_fee_token_0_liquidity_only": PoolTestCase(
        fee_amount=3000,
        tick_spacing=60,
        starting_price=encode_sqrt_price(1, 1),
        positions=[
            Position(
                tick_lower=0,
                tick_upper=2000 * 60,
                liquidity=expand_to_decimals(2, 18),
            ),
        ],
    ),
    "medium_fee_token_1_liquidity_only": PoolTestCase(
        fee_amount=3000,
        tick_spacing=60,
        starting_price=encode_sqrt_price(1, 1),
        positions=[
            Position(
                tick_lower=-2000 * 60,
                tick_upper=0,
                liquidity=expand_to_decimals(2, 18),
            ),
        ],
    ),
    "close_to_max_price": PoolTestCase(
        fee_amount=3000,
        tick_spacing=60,
        starting_price=encode_sqrt_price(2**127, 1),
        positions=[
            Position(
                tick_lower=MID_FEE_MIN_TICK,
                tick_upper=MID_FEE_MAX_TICK,
                liquidity=expand_to_decimals(2, 18),
            )
        ],
    ),
    "close_to_min_price": PoolTestCase(
        fee_amount=3000,
        tick_spacing=60,
        starting_price=encode_sqrt_price(1, 2**127),
        positions=[
            Position(
                tick_lower=MID_FEE_MIN_TICK,
                tick_upper=MID_FEE_MAX_TICK,
                liquidity=expand_to_decimals(2, 18),
            )
        ],
    ),
    "max_full_range_liquidity_at_1_1_price_default_fee": PoolTestCase(
        fee_amount=3000,
        tick_spacing=60,
        starting_price=encode_sqrt_price(1, 1),
        positions=[
            Position(
                tick_lower=MID_FEE_MIN_TICK,
                tick_upper=MID_FEE_MAX_TICK,
                liquidity=UniswapV3Math.get_max_liquidity_per_tick(60),
            )
        ],
    ),
    "initialized_at_max_ratio": PoolTestCase(
        fee_amount=3000,
        tick_spacing=60,
        starting_price=MAX_SQRT_RATIO - 1,
        positions=[
            Position(
                tick_lower=MID_FEE_MIN_TICK,
                tick_upper=MID_FEE_MAX_TICK,
                liquidity=expand_to_decimals(2, 18),
            )
        ],
    ),
    "initialized_at_min_ratio": PoolTestCase(
        fee_amount=3000,
        tick_spacing=60,
        starting_price=MIN_SQRT_RATIO,
        positions=[
            Position(
                tick_lower=MID_FEE_MIN_TICK,
                tick_upper=MID_FEE_MAX_TICK,
                liquidity=expand_to_decimals(2, 18),
            )
        ],
    ),
}


def pytest_assert_skip(val_1, val_2):
    if val_1 == val_2:
        return

    delta = abs((val_1 - val_2) / val_1)
    if delta < 0.000001:  # One ten-thousandth of a percent
        pytest.skip(f"Values should be Equal, but are off by {delta * 100}%")

    pytest.fail(
        f"Values should be equal, but are more than a ten-thousandth of a percent different: {val_1} != {val_2}"
    )


class TestSwaps:
    expected_swap_results = json.load(open(Path(__file__).parent.joinpath("swap_outputs.json"), "r"))

    def setup_class(self):
        UniswapV3Pool.enable_exact_math()

    def set_up_test_pool(
        self,
        pool_test_case: PoolTestCase,
    ) -> UniswapV3Pool:
        pool = UniswapV3Pool(
            tick_spacing=pool_test_case.tick_spacing,
            fee=pool_test_case.fee_amount,
        )
        pool.slot0 = Slot0(
            sqrt_price=pool_test_case.starting_price,
            tick=pool.math.tick_math.get_tick_at_sqrt_ratio(pool_test_case.starting_price),
            observation_index=0,
            observation_cardinality=20,
            observation_cardinality_next=0,
            fee_protocol=0,
        )

        for position in pool_test_case.positions:
            pool.mint(
                recipient=LIQUIDITY_PROVIDER_ADDRESS,
                tick_lower=position.tick_lower,
                tick_upper=position.tick_upper,
                amount=position.liquidity,
            )

        return pool

    def execute_swap(
        self,
        pool: UniswapV3Pool,
        test_case: SwapCase,
    ):
        max_tokens = 2**128
        if test_case.sqrt_price_limit is None:
            sqrt_price_limit = MIN_SQRT_RATIO + 1 if test_case.zero_for_one else MAX_SQRT_RATIO - 1

        else:
            sqrt_price_limit = test_case.sqrt_price_limit

        if test_case.exact_out is None:
            pool.swap(
                zero_for_one=test_case.zero_for_one,
                amount_specified=max_tokens,
                sqrt_price_limit=sqrt_price_limit,
                log_swap=False,
            )

        else:
            amount_specified = (-1 if test_case.exact_out else 1) * (
                test_case.amount_1 if test_case.zero_for_one == test_case.exact_out else test_case.amount_0
            )

            pool.swap(
                zero_for_one=test_case.zero_for_one,
                amount_specified=amount_specified,
                sqrt_price_limit=sqrt_price_limit,
                log_swap=False,
            )

    @pytest.mark.timeout(5)
    @pytest.mark.parametrize("swap_test_case", SWAP_CASES.keys())
    @pytest.mark.parametrize("pool_test_case", TEST_POOLS.keys())
    def test_pool_swaps(self, pool_test_case, swap_test_case):
        test_fixture = self.expected_swap_results[f"{pool_test_case}___{swap_test_case}"]

        initialized_pool = self.set_up_test_pool(TEST_POOLS[pool_test_case])

        pool_balance_0, pool_balance_1 = (
            initialized_pool.state.balance_0,
            initialized_pool.state.balance_1,
        )
        fee_growth_global_0 = initialized_pool.state.fee_growth_global_0
        fee_growth_global_1 = initialized_pool.state.fee_growth_global_1
        slot_0_before = copy.deepcopy(initialized_pool.slot0)

        if "swapError" in test_fixture:
            with pytest.raises(UniswapV3Revert):
                self.execute_swap(initialized_pool, SWAP_CASES[swap_test_case])
            return

        self.execute_swap(initialized_pool, SWAP_CASES[swap_test_case])

        amount_0_delta = initialized_pool.state.balance_0 - pool_balance_0
        amount_1_delta = initialized_pool.state.balance_1 - pool_balance_1
        fee_growth_0_delta = initialized_pool.state.fee_growth_global_0 - fee_growth_global_0
        fee_growth_1_delta = initialized_pool.state.fee_growth_global_1 - fee_growth_global_1

        if "executionPrice" in test_fixture:
            if test_fixture["executionPrice"] == "NaN":
                assert amount_0_delta == amount_1_delta == 0
            else:
                execution_price = amount_1_delta / amount_0_delta * -1 if amount_0_delta else 0
                delta = (execution_price - float(test_fixture["executionPrice"])) / execution_price
                assert delta < 0.0001

        if "tickBefore" in test_fixture:
            assert slot_0_before.tick == test_fixture["tickBefore"]

        if "tickAfter" in test_fixture:
            assert initialized_pool.slot0.tick == test_fixture["tickAfter"]

        if "poolPriceBefore" in test_fixture:
            price = decode_sqrt_price(slot_0_before.sqrt_price)
            delta = (price - float(test_fixture["poolPriceBefore"])) / price
            assert delta < 0.00001

        if "poolPriceAfter" in test_fixture:
            price = decode_sqrt_price(initialized_pool.slot0.sqrt_price)
            delta = (price - float(test_fixture["poolPriceAfter"])) / price
            assert delta < 0.00001

        if "amount0Before" and "amount0Delta" and "amount1Before" and "amount1Delta" in test_fixture:
            pytest_assert_skip(pool_balance_0, int(test_fixture["amount0Before"]))
            pytest_assert_skip(amount_0_delta, int(test_fixture["amount0Delta"]))
            pytest_assert_skip(pool_balance_1, int(test_fixture["amount1Before"]))
            pytest_assert_skip(amount_1_delta, int(test_fixture["amount1Delta"]))

        if "feeGrowthGlobal0X128Delta" and "feeGrowthGlobal1X128Delta" in test_fixture:
            pytest_assert_skip(fee_growth_0_delta, int(test_fixture["feeGrowthGlobal0X128Delta"]))
            pytest_assert_skip(fee_growth_1_delta, int(test_fixture["feeGrowthGlobal1X128Delta"]))

        # After each swap verify that positions can be burned and collected
        for position in TEST_POOLS[pool_test_case].positions:
            initialized_pool.burn(
                owner_address=LIQUIDITY_PROVIDER_ADDRESS,
                tick_lower=position.tick_lower,
                tick_upper=position.tick_upper,
                amount=position.liquidity,
            )

        # assert initialized_pool.state.balance_0 == 0
        # assert initialized_pool.state.balance_1 == 1
