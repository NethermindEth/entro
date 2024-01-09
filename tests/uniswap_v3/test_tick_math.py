import math

import pytest

from python_eth_amm.exceptions import TickMathRevert, UniswapV3Revert
from python_eth_amm.types.uniswap_v3 import Tick
from python_eth_amm.uniswap_v3 import UniswapV3Pool
from python_eth_amm.uniswap_v3.math import UniswapV3Math
from python_eth_amm.uniswap_v3.math.shared import (
    MAX_SQRT_RATIO,
    MAX_TICK,
    MIN_SQRT_RATIO,
    MIN_TICK,
)

from ..utils import uint_max
from .utils import encode_sqrt_price

UniV3Math = UniswapV3Math.__new__(UniswapV3Math)
UniV3Math.initialize_exact_math()


class TestTickSpacingToMaxLiquidityPerTick:
    def test_returns_correct_value_for_low_fee(
        self,
    ):
        assert (
            UniV3Math.get_max_liquidity_per_tick(10)
            == 1917569901783203986719870431555990
        )

    def test_returns_correct_value_for_medium_fee(
        self,
    ):
        assert (
            UniV3Math.get_max_liquidity_per_tick(60)
            == 11505743598341114571880798222544994
        )

    def test_returns_correct_value_for_high_fee(
        self,
    ):
        assert (
            UniV3Math.get_max_liquidity_per_tick(200)
            == 38350317471085141830651933667504588
        )

    def test_returns_correct_value_for_full_range(
        self,
    ):
        assert (
            UniV3Math.get_max_liquidity_per_tick(887272)
            == 113427455640312821154458202477256070485
        )

    def test_returns_correct_value_for_2032(
        self,
    ):
        assert (
            UniV3Math.get_max_liquidity_per_tick(2302)
            == 441351967472034323558203122479595605
        )


class TestGetFeeGrowthInside:
    def test_returns_all_for_two_uninitialized_ticks_if_tick_is_inside(
        self,
    ):
        pool = UniswapV3Pool()
        growth_inside_0, growth_inside_1 = pool._get_fee_growth_inside(-2, 2, 0, 15, 15)
        assert growth_inside_0 == 15
        assert growth_inside_1 == 15

    def test_returns_zero_for_two_uninitialized_ticks_if_tick_is_above(
        self,
    ):
        pool = UniswapV3Pool()
        growth_inside_0, growth_inside_1 = pool._get_fee_growth_inside(-2, 2, 4, 15, 15)
        assert growth_inside_0 == 0
        assert growth_inside_1 == 0

    def test_returns_zero_for_two_uninitialized_ticks_if_tick_is_below(
        self,
    ):
        pool = UniswapV3Pool()
        growth_inside_0, growth_inside_1 = pool._get_fee_growth_inside(
            -2, 2, -4, 15, 15
        )
        assert growth_inside_0 == 0
        assert growth_inside_1 == 0

    def test_subtracts_upper_tick_if_below(
        self,
    ):
        pool = UniswapV3Pool()
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

    def test_subtracts_lower_tick_if_above(
        self,
    ):
        pool = UniswapV3Pool()
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

    def test_subtracts_lower_tick_if_inside(
        self,
    ):
        pool = UniswapV3Pool()
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

    def test_overflow_with_inside_tick(
        self,
    ):
        pool = UniswapV3Pool()
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

    def test_flips_from_zero_to_nonzero(
        self,
    ):
        pool = UniswapV3Pool()
        assert (
            pool._update_tick(
                liquidity_delta=1, upper=False, max_liquidity=3, **self.ZERO_PARAMS
            )
            == True
        )

    def test_does_not_flip_from_nonzero_to_greater_nonzero(
        self,
    ):
        pool = UniswapV3Pool()
        pool._update_tick(
            liquidity_delta=1, upper=False, max_liquidity=3, **self.ZERO_PARAMS
        )
        assert (
            pool._update_tick(
                liquidity_delta=1, upper=False, max_liquidity=3, **self.ZERO_PARAMS
            )
            == False
        )

    def test_flips_from_non_zero_to_zero(
        self,
    ):
        pool = UniswapV3Pool()
        pool._update_tick(
            liquidity_delta=1, upper=False, max_liquidity=3, **self.ZERO_PARAMS
        )
        assert (
            pool._update_tick(
                liquidity_delta=-1, upper=False, max_liquidity=3, **self.ZERO_PARAMS
            )
            == True
        )

    def test_does_not_flip_from_non_zero_to_negative(
        self,
    ):
        pool = UniswapV3Pool()
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
        self,
    ):
        pool = UniswapV3Pool()
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

    def test_nets_the_liquidity_based_on_upper_flag(
        self,
    ):
        pool = UniswapV3Pool()
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

    def test_reverts_on_overflow_liqidity_gross(
        self,
    ):
        pool = UniswapV3Pool()
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
        self,
    ):
        pool = UniswapV3Pool()
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
        self,
    ):
        pool = UniswapV3Pool()
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
        self,
    ):
        pool = UniswapV3Pool()
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


def test_clear_tick_deletes_all_tick_data():
    pool = UniswapV3Pool()
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


def test_cross_tick_flips_growth_variable():
    pool = UniswapV3Pool()
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


def test_duplicate_cross_tick():
    pool = UniswapV3Pool()
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

    def test_raises_for_low_ticks(
        self,
    ):
        with pytest.raises(TickMathRevert):
            UniV3Math.tick_math.get_sqrt_ratio_at_tick(
                self.MIN_TICK - 1,
            )

    def test_raises_for_high_ticks(
        self,
    ):
        with pytest.raises(TickMathRevert):
            UniV3Math.tick_math.get_sqrt_ratio_at_tick(
                self.MAX_TICK + 1,
            )

    def test_min_tick(
        self,
    ):
        assert (
            UniV3Math.tick_math.get_sqrt_ratio_at_tick(
                self.MIN_TICK,
            )
            == 4295128739
        )

    def test_min_tick_plus_1(
        self,
    ):
        assert (
            UniV3Math.tick_math.get_sqrt_ratio_at_tick(
                self.MIN_TICK + 1,
            )
            == 4295343490
        )

    def test_max_tick_minus_1(
        self,
    ):
        assert (
            UniV3Math.tick_math.get_sqrt_ratio_at_tick(
                self.MAX_TICK - 1,
            )
            == 1461373636630004318706518188784493106690254656249
        )

    def test_max_tick(
        self,
    ):
        assert (
            UniV3Math.tick_math.get_sqrt_ratio_at_tick(
                self.MAX_TICK,
            )
            == 1461446703485210103287273052203988822378723970342
        )

    def test_implementation(
        self,
    ):
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
            uni_lib_value = UniV3Math.tick_math.get_sqrt_ratio_at_tick(
                tick,
            )
            python_val = math.sqrt(1.0001**tick) * 2**96
            assert (
                abs(uni_lib_value - python_val) / uni_lib_value < 0.000001
            )  # 1/100th of a bip

    def test_min_sqrt_ratio(
        self,
    ):
        assert (
            UniV3Math.tick_math.get_sqrt_ratio_at_tick(
                self.MIN_TICK,
            )
            == MIN_SQRT_RATIO
        )

    def test_max_sqrt_ratio(
        self,
    ):
        assert (
            UniV3Math.tick_math.get_sqrt_ratio_at_tick(
                self.MAX_TICK,
            )
            == MAX_SQRT_RATIO
        )


class TestGetTickAtSQRTRation:
    def test_raises_for_too_low(
        self,
    ):
        with pytest.raises(TickMathRevert):
            UniV3Math.tick_math.get_tick_at_sqrt_ratio(
                MIN_SQRT_RATIO - 1,
            )

    def test_raises_for_too_high(
        self,
    ):
        with pytest.raises(TickMathRevert):
            UniV3Math.tick_math.get_tick_at_sqrt_ratio(
                MAX_SQRT_RATIO,
            )

    def test_ratio_of_min_tick(
        self,
    ):
        assert (
            UniV3Math.tick_math.get_tick_at_sqrt_ratio(
                MIN_SQRT_RATIO,
            )
            == MIN_TICK
        )

    def test_ratio_of_min_tick_plus_1(
        self,
    ):
        assert (
            UniV3Math.tick_math.get_tick_at_sqrt_ratio(
                4295343490,
            )
            == MIN_TICK + 1
        )

    def test_ratio_of_max_tick_minus_1(
        self,
    ):
        assert (
            UniV3Math.tick_math.get_tick_at_sqrt_ratio(
                1461373636630004318706518188784493106690254656249,
            )
            == MAX_TICK - 1
        )

    def test_ratio_of_max_tick_closet_ratio(
        self,
    ):
        assert (
            UniV3Math.tick_math.get_tick_at_sqrt_ratio(
                MAX_SQRT_RATIO - 1,
            )
            == MAX_TICK - 1
        )

    def test_implementation(
        self,
    ):
        for ratio in [
            MIN_SQRT_RATIO,
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
            MAX_SQRT_RATIO - 1,
        ]:
            uni_lib_result = UniV3Math.tick_math.get_tick_at_sqrt_ratio(
                ratio,
            )
            python_result = math.log((ratio / 2**96) ** 2, 1.0001)
            assert abs(uni_lib_result - python_result) < 1.1

            tick = UniV3Math.tick_math.get_tick_at_sqrt_ratio(
                ratio,
            )
            tick_ratio = UniV3Math.tick_math.get_sqrt_ratio_at_tick(
                tick,
            )
            tick_plus_one_ratio = UniV3Math.tick_math.get_sqrt_ratio_at_tick(
                tick + 1,
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
        cls.pool = UniswapV3Pool(initial_block=10_000_000)

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
        assert tick == MIN_TICK

    def test_returns_max_tick_if_no_initialized_tick(self):
        tick = self.pool._get_next_initialized_tick_index(535, False)
        assert tick == MAX_TICK
