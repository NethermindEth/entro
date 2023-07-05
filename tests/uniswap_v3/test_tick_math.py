import logging
import math
import os

import pytest

from python_eth_amm import PoolFactory
from python_eth_amm.exceptions import TickMathRevert, UniswapV3Revert
from python_eth_amm.math import TickMathModule
from python_eth_amm.uniswap_v3 import UniswapV3Pool
from python_eth_amm.uniswap_v3.types import Tick

from ..utils import uint_max
from .utils import encode_sqrt_price

TICK_MATH_FACTORY = PoolFactory(
    exact_math=True,
    logger=logging.Logger("test"),
    sqlalchemy_uri=os.environ["SQLALCHEMY_DB_URI"],
)


class TestTickSpacingToMaxLiquidityPerTick:
    def test_returns_correct_value_for_low_fee(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        assert (
            pool.math.get_max_liquidity_per_tick(10)
            == 1917569901783203986719870431555990
        )

    def test_returns_correct_value_for_medium_fee(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        assert (
            pool.math.get_max_liquidity_per_tick(60)
            == 11505743598341114571880798222544994
        )

    def test_returns_correct_value_for_high_fee(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        assert (
            pool.math.get_max_liquidity_per_tick(200)
            == 38350317471085141830651933667504588
        )

    def test_returns_correct_value_for_full_range(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        assert (
            pool.math.get_max_liquidity_per_tick(887272)
            == 113427455640312821154458202477256070485
        )

    def test_returns_correct_value_for_2032(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        assert (
            pool.math.get_max_liquidity_per_tick(2302)
            == 441351967472034323558203122479595605
        )


class TestGetFeeGrowthInside:
    def test_returns_all_for_two_uninitialized_ticks_if_tick_is_inside(
        self, initialize_empty_pool
    ):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        growth_inside_0, growth_inside_1 = pool._get_fee_growth_inside(-2, 2, 0, 15, 15)
        assert growth_inside_0 == 15
        assert growth_inside_1 == 15

    def test_returns_zero_for_two_uninitialized_ticks_if_tick_is_above(
        self, initialize_empty_pool
    ):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        growth_inside_0, growth_inside_1 = pool._get_fee_growth_inside(-2, 2, 4, 15, 15)
        assert growth_inside_0 == 0
        assert growth_inside_1 == 0

    def test_returns_zero_for_two_uninitialized_ticks_if_tick_is_below(
        self, initialize_empty_pool
    ):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        growth_inside_0, growth_inside_1 = pool._get_fee_growth_inside(
            -2, 2, -4, 15, 15
        )
        assert growth_inside_0 == 0
        assert growth_inside_1 == 0

    def test_subtracts_upper_tick_if_below(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        tick_data = Tick(
            liquidity_gross=0,
            liquidity_net=0,
            fee_growth_outside_0=2,
            fee_growth_outside_1=3,
            tick_cumulative_outside=0,
            seconds_per_liquidity_outside=0,
            seconds_outside=0,
        )
        pool._set_tick(2, tick_data)

        growth_inside, growth_outside = pool._get_fee_growth_inside(-2, 2, 0, 15, 15)
        assert growth_inside == 13
        assert growth_outside == 12

    def test_subtracts_lower_tick_if_above(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        tick_data = Tick(
            liquidity_gross=0,
            liquidity_net=0,
            fee_growth_outside_0=2,
            fee_growth_outside_1=3,
            tick_cumulative_outside=0,
            seconds_per_liquidity_outside=0,
            seconds_outside=0,
        )
        pool._set_tick(-2, tick_data)

        growth_inside_0, growth_inside_1 = pool._get_fee_growth_inside(-2, 2, 0, 15, 15)
        assert growth_inside_0 == 13
        assert growth_inside_1 == 12

    def test_subtracts_lower_tick_if_inside(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        lower_tick_data = Tick(
            liquidity_gross=0,
            liquidity_net=0,
            fee_growth_outside_0=2,
            fee_growth_outside_1=3,
            tick_cumulative_outside=0,
            seconds_per_liquidity_outside=0,
            seconds_outside=0,
        )
        upper_tick_data = Tick(
            liquidity_gross=0,
            liquidity_net=0,
            fee_growth_outside_0=4,
            fee_growth_outside_1=1,
            tick_cumulative_outside=0,
            seconds_per_liquidity_outside=0,
            seconds_outside=0,
        )
        pool._set_tick(-2, lower_tick_data)
        pool._set_tick(2, upper_tick_data)

        growth_inside_0, growth_inside_1 = pool._get_fee_growth_inside(-2, 2, 0, 15, 15)
        assert growth_inside_0 == 9
        assert growth_inside_1 == 11

    def test_overflow_with_inside_tick(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        lower_tick_data = Tick(
            liquidity_gross=0,
            liquidity_net=0,
            fee_growth_outside_0=uint_max(256) - 3,
            fee_growth_outside_1=uint_max(256) - 2,
            tick_cumulative_outside=0,
            seconds_per_liquidity_outside=0,
            seconds_outside=0,
        )
        upper_tick_data = Tick(
            liquidity_gross=0,
            liquidity_net=0,
            fee_growth_outside_0=3,
            fee_growth_outside_1=5,
            tick_cumulative_outside=0,
            seconds_per_liquidity_outside=0,
            seconds_outside=0,
        )
        pool._set_tick(-2, lower_tick_data)
        pool._set_tick(2, upper_tick_data)

        growth_inside_0, growth_inside_1 = pool._get_fee_growth_inside(-2, 2, 0, 15, 15)
        assert growth_inside_0 == 16
        assert growth_inside_1 == 13


class TestUpdateTick:
    ZERO_PARAMS = {
        "tick": 0,
        "tick_current": 0,
        "fee_growth_global_0": 0,
        "fee_growth_global_1": 0,
        "seconds_per_liquidity_cumulative": 0,
        "tick_cumulative": 0,
        "time": 0,
    }

    def test_flips_from_zero_to_nonzero(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        assert (
            pool._update_tick(
                liquidity_delta=1, upper=False, max_liquidity=3, **self.ZERO_PARAMS
            )
            == True
        )

    def test_does_not_flip_from_nonzero_to_greater_nonzero(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        pool._update_tick(
            liquidity_delta=1, upper=False, max_liquidity=3, **self.ZERO_PARAMS
        )
        assert (
            pool._update_tick(
                liquidity_delta=1, upper=False, max_liquidity=3, **self.ZERO_PARAMS
            )
            == False
        )

    def test_flips_from_non_zero_to_zero(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        pool._update_tick(
            liquidity_delta=1, upper=False, max_liquidity=3, **self.ZERO_PARAMS
        )
        assert (
            pool._update_tick(
                liquidity_delta=-1, upper=False, max_liquidity=3, **self.ZERO_PARAMS
            )
            == True
        )

    def test_does_not_flip_from_non_zero_to_negative(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        pool._update_tick(
            liquidity_delta=2, upper=False, max_liquidity=3, **self.ZERO_PARAMS
        )
        assert (
            pool._update_tick(
                liquidity_delta=-1, upper=False, max_liquidity=3, **self.ZERO_PARAMS
            )
            == False
        )

    def test_reverts_if_total_liquidity_gross_is_greater_than_max(
        self, initialize_empty_pool
    ):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        pool._update_tick(
            liquidity_delta=2, upper=False, max_liquidity=3, **self.ZERO_PARAMS
        )
        pool._update_tick(
            liquidity_delta=1, upper=True, max_liquidity=3, **self.ZERO_PARAMS
        )
        with pytest.raises(UniswapV3Revert):
            pool._update_tick(
                liquidity_delta=1, upper=False, max_liquidity=3, **self.ZERO_PARAMS
            )

    def test_nets_the_liquidity_based_on_upper_flag(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        pool._update_tick(
            liquidity_delta=2, upper=False, max_liquidity=10, **self.ZERO_PARAMS
        )
        pool._update_tick(
            liquidity_delta=1, upper=True, max_liquidity=10, **self.ZERO_PARAMS
        )
        pool._update_tick(
            liquidity_delta=3, upper=True, max_liquidity=10, **self.ZERO_PARAMS
        )
        pool._update_tick(
            liquidity_delta=1, upper=False, max_liquidity=10, **self.ZERO_PARAMS
        )
        tick = pool._get_tick(0)
        assert tick.liquidity_gross == 2 + 1 + 3 + 1
        assert tick.liquidity_net == 2 - 1 - 3 + 1

    def test_reverts_on_overflow_liqidity_gross(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        pool._update_tick(
            liquidity_delta=(uint_max(128) / 2) - 1,
            upper=False,
            max_liquidity=uint_max(128),
            **self.ZERO_PARAMS,
        )
        with pytest.raises(UniswapV3Revert):
            pool._update_tick(
                liquidity_delta=(uint_max(128) / 2) - 1,
                upper=False,
                max_liquidity=uint_max(128),
                **self.ZERO_PARAMS,
            )

    def test_assumes_all_growth_happens_below_ticks_lte_current_tick(
        self, initialize_empty_pool
    ):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        pool._update_tick(
            tick=1,
            tick_current=1,
            liquidity_delta=1,
            fee_growth_global_0=1,
            fee_growth_global_1=2,
            seconds_per_liquidity_cumulative=3,
            tick_cumulative=4,
            time=5,
            upper=False,
            max_liquidity=uint_max(128),
        )
        assert 1 in pool.ticks.keys()
        tick = pool._get_tick(1)
        assert tick.fee_growth_outside_0 == 1
        assert tick.fee_growth_outside_1 == 2
        assert tick.seconds_per_liquidity_outside == 3
        assert tick.tick_cumulative_outside == 4
        assert tick.seconds_outside == 5

    def test_does_not_set_growth_fields_if_tick_is_already_initialized(
        self, initialize_empty_pool
    ):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        pool._update_tick(
            tick=1,
            tick_current=1,
            liquidity_delta=1,
            fee_growth_global_0=1,
            fee_growth_global_1=2,
            seconds_per_liquidity_cumulative=3,
            tick_cumulative=4,
            time=5,
            upper=False,
            max_liquidity=uint_max(128),
        )
        pool._update_tick(
            tick=1,
            tick_current=1,
            liquidity_delta=1,
            fee_growth_global_0=6,
            fee_growth_global_1=7,
            seconds_per_liquidity_cumulative=8,
            tick_cumulative=9,
            time=10,
            upper=False,
            max_liquidity=uint_max(128),
        )
        assert 1 in pool.ticks.keys()

        tick = pool._get_tick(1)
        assert tick.fee_growth_outside_0 == 1
        assert tick.fee_growth_outside_1 == 2
        assert tick.seconds_per_liquidity_outside == 3
        assert tick.tick_cumulative_outside == 4
        assert tick.seconds_outside == 5

    def test_does_not_set_any_growth_fields_for_ticks_gt_current_tick(
        self, initialize_empty_pool
    ):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        pool._update_tick(
            tick=2,
            tick_current=1,
            liquidity_delta=1,
            fee_growth_global_0=1,
            fee_growth_global_1=2,
            seconds_per_liquidity_cumulative=3,
            tick_cumulative=4,
            time=5,
            upper=False,
            max_liquidity=uint_max(128),
        )
        assert 2 in pool.ticks.keys()
        tick = pool._get_tick(2)
        assert tick.fee_growth_outside_0 == 0
        assert tick.fee_growth_outside_1 == 0
        assert tick.seconds_per_liquidity_outside == 0
        assert tick.tick_cumulative_outside == 0
        assert tick.tick_cumulative_outside == 0
        assert tick.seconds_outside == 0


def test_clear_tick_deletes_all_tick_data(initialize_empty_pool):
    pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
    tick_data = Tick(
        liquidity_gross=3,
        liquidity_net=4,
        fee_growth_outside_0=1,
        fee_growth_outside_1=2,
        tick_cumulative_outside=6,
        seconds_per_liquidity_outside=5,
        seconds_outside=7,
    )
    pool._set_tick(2, tick_data)
    pool._clear_tick(2)
    tick = pool._get_tick(2)
    assert tick is None


def test_cross_tick_flips_growth_variable(initialize_empty_pool):
    pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
    tick_data = Tick(
        liquidity_gross=3,
        liquidity_net=4,
        fee_growth_outside_0=1,
        fee_growth_outside_1=2,
        tick_cumulative_outside=6,
        seconds_per_liquidity_outside=5,
        seconds_outside=7,
    )
    pool._set_tick(2, tick_data)
    pool._cross_tick(
        tick=2,
        fee_growth_global_0=7,
        fee_growth_global_1=9,
        seconds_per_liquidity_cumulative=8,
        tick_cumulative=15,
        time=10,
    )
    tick = pool._get_tick(2)

    assert tick.fee_growth_outside_0 == 6
    assert tick.fee_growth_outside_1 == 7
    assert tick.seconds_per_liquidity_outside == 3
    assert tick.tick_cumulative_outside == 9
    assert tick.seconds_outside == 3


def test_duplicate_cross_tick(initialize_empty_pool):
    pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
    tick_data = Tick(
        liquidity_gross=3,
        liquidity_net=4,
        fee_growth_outside_0=1,
        fee_growth_outside_1=2,
        tick_cumulative_outside=6,
        seconds_per_liquidity_outside=5,
        seconds_outside=7,
    )
    pool._set_tick(2, tick_data)
    pool._cross_tick(
        tick=2,
        fee_growth_global_0=7,
        fee_growth_global_1=9,
        seconds_per_liquidity_cumulative=8,
        tick_cumulative=15,
        time=10,
    )
    pool._cross_tick(
        tick=2,
        fee_growth_global_0=7,
        fee_growth_global_1=9,
        seconds_per_liquidity_cumulative=8,
        tick_cumulative=15,
        time=10,
    )
    tick = pool._get_tick(2)

    assert tick.fee_growth_outside_0 == 1
    assert tick.fee_growth_outside_1 == 2
    assert tick.seconds_per_liquidity_outside == 5
    assert tick.tick_cumulative_outside == 6
    assert tick.seconds_outside == 7


class TestGetSQRTRatioAtTick:
    MIN_TICK = -887272
    MAX_TICK = 887272

    def test_raises_for_low_ticks(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        with pytest.raises(TickMathRevert):
            pool.math.tick_math.get_sqrt_ratio_at_tick(
                self.MIN_TICK - 1, exact_rounding=True
            )

    def test_raises_for_high_ticks(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        with pytest.raises(TickMathRevert):
            pool.math.tick_math.get_sqrt_ratio_at_tick(
                self.MAX_TICK + 1, exact_rounding=True
            )

    def test_min_tick(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        assert (
            pool.math.tick_math.get_sqrt_ratio_at_tick(
                self.MIN_TICK, exact_rounding=True
            )
            == 4295128739
        )

    def test_min_tick_plus_1(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        assert (
            pool.math.tick_math.get_sqrt_ratio_at_tick(
                self.MIN_TICK + 1, exact_rounding=True
            )
            == 4295343490
        )

    def test_max_tick_minus_1(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        assert (
            pool.math.tick_math.get_sqrt_ratio_at_tick(
                self.MAX_TICK - 1, exact_rounding=True
            )
            == 1461373636630004318706518188784493106690254656249
        )

    def test_max_tick(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        assert (
            pool.math.tick_math.get_sqrt_ratio_at_tick(
                self.MAX_TICK, exact_rounding=True
            )
            == 1461446703485210103287273052203988822378723970342
        )

    def test_implementation(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        for tick in [
            50,
            100,
            250,
            500,
            1000,
            2500,
            3000,
            4000,
            5000,
            50000,
            150000,
            250000,
            500000,
            738203,
        ]:
            uni_lib_value = pool.math.tick_math.get_sqrt_ratio_at_tick(
                tick, exact_rounding=True
            )
            python_val = math.sqrt(1.0001**tick) * 2**96
            assert (
                abs(uni_lib_value - python_val) / uni_lib_value < 0.000001
            )  # 1/100th of a bip

    def test_min_sqrt_ratio(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        assert (
            pool.math.tick_math.get_sqrt_ratio_at_tick(
                self.MIN_TICK, exact_rounding=True
            )
            == pool.math.tick_math.MIN_SQRT_RATIO
        )

    def test_max_sqrt_ratio(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        assert (
            pool.math.tick_math.get_sqrt_ratio_at_tick(
                self.MAX_TICK, exact_rounding=True
            )
            == pool.math.tick_math.MAX_SQRT_RATIO
        )


class TestGetTickAtSQRTRation:
    MIN_RATIO = TickMathModule.MIN_SQRT_RATIO
    MAX_RATIO = TickMathModule.MAX_SQRT_RATIO

    def test_raises_for_too_low(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        with pytest.raises(TickMathRevert):
            pool.math.tick_math.get_tick_at_sqrt_ratio(
                self.MIN_RATIO - 1, exact_rounding=True
            )

    def test_raises_for_too_high(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        with pytest.raises(TickMathRevert):
            pool.math.tick_math.get_tick_at_sqrt_ratio(
                self.MAX_RATIO, exact_rounding=True
            )

    def test_ratio_of_min_tick(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        assert (
            pool.math.tick_math.get_tick_at_sqrt_ratio(
                self.MIN_RATIO, exact_rounding=True
            )
            == TickMathModule.MIN_TICK
        )

    def test_ratio_of_min_tick_plus_1(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        assert (
            pool.math.tick_math.get_tick_at_sqrt_ratio(4295343490, exact_rounding=True)
            == TickMathModule.MIN_TICK + 1
        )

    def test_ratio_of_max_tick_minus_1(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        assert (
            pool.math.tick_math.get_tick_at_sqrt_ratio(
                1461373636630004318706518188784493106690254656249, exact_rounding=True
            )
            == pool.math.tick_math.MAX_TICK - 1
        )

    def test_ratio_of_max_tick_closet_ratio(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        assert (
            pool.math.tick_math.get_tick_at_sqrt_ratio(
                self.MAX_RATIO - 1, exact_rounding=True
            )
            == pool.math.tick_math.MAX_TICK - 1
        )

    def test_implementation(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=TICK_MATH_FACTORY)
        for ratio in [
            self.MIN_RATIO,
            encode_sqrt_price(10**12, 1),
            encode_sqrt_price(10**6, 1),
            encode_sqrt_price(1, 64),
            encode_sqrt_price(1, 8),
            encode_sqrt_price(1, 2),
            encode_sqrt_price(1, 1),
            encode_sqrt_price(2, 1),
            encode_sqrt_price(8, 1),
            encode_sqrt_price(64, 1),
            encode_sqrt_price(1, 10**6),
            encode_sqrt_price(1, 10**12),
            self.MAX_RATIO - 1,
        ]:
            uni_lib_result = pool.math.tick_math.get_tick_at_sqrt_ratio(
                ratio, exact_rounding=True
            )
            python_result = math.log((ratio / 2**96) ** 2, 1.0001)
            assert abs(uni_lib_result - python_result) < 1.1

            tick = pool.math.tick_math.get_tick_at_sqrt_ratio(
                ratio, exact_rounding=True
            )
            tick_ratio = pool.math.tick_math.get_sqrt_ratio_at_tick(
                tick, exact_rounding=True
            )
            tick_plus_one_ratio = pool.math.tick_math.get_sqrt_ratio_at_tick(
                tick + 1, exact_rounding=True
            )

            assert tick_ratio <= ratio < tick_plus_one_ratio


class TestGetNextInitializedTick:
    zero_tick = Tick(
        liquidity_gross=0,
        liquidity_net=0,
        fee_growth_outside_0=0,
        fee_growth_outside_1=0,
        tick_cumulative_outside=0,
        seconds_per_liquidity_outside=0,
        seconds_outside=0,
    )
    pool: UniswapV3Pool

    @classmethod
    def setup_class(cls):
        cls.pool = TICK_MATH_FACTORY.initialize_empty_pool(
            pool_type="uniswap_v3", initialization_args={"initial_block": 10_000_000}
        )

        cls.pool._set_tick(-200, cls.zero_tick)
        cls.pool._set_tick(-55, cls.zero_tick)
        cls.pool._set_tick(-4, cls.zero_tick)
        cls.pool._set_tick(70, cls.zero_tick)
        cls.pool._set_tick(78, cls.zero_tick)
        cls.pool._set_tick(84, cls.zero_tick)
        cls.pool._set_tick(139, cls.zero_tick)
        cls.pool._set_tick(240, cls.zero_tick)
        cls.pool._set_tick(535, cls.zero_tick)

    def test_returns_right_tick_if_at_initialized_tick(self):
        tick = self.pool._get_next_initialized_tick_index(78, False)
        assert tick == 84

    def test_returns_right_tick_starting_at_negative(self):
        tick = self.pool._get_next_initialized_tick_index(-55, False)
        assert tick == -4

    def test_returns_neighboring_right_tick_positive(self):
        tick = self.pool._get_next_initialized_tick_index(77, False)
        assert tick == 78

    def test_returns_neighboring_right_tick_negative(self):
        tick = self.pool._get_next_initialized_tick_index(-56, False)
        assert tick == -55

    def test_returns_same_tick_if_initialized(self):
        tick = self.pool._get_next_initialized_tick_index(78, True)
        assert tick == 78

    def test_returns_tick_directly_to_left_if_not_initialized(self):
        tick = self.pool._get_next_initialized_tick_index(79, True)
        assert tick == 78

    def test_returns_min_tick_if_no_initialized_tick(self):
        tick = self.pool._get_next_initialized_tick_index(-205, True)
        assert tick == self.pool.math.tick_math.MIN_TICK

    def test_returns_max_tick_if_no_initialized_tick(self):
        tick = self.pool._get_next_initialized_tick_index(535, False)
        assert tick == self.pool.math.tick_math.MAX_TICK
