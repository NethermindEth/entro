import pytest

from python_eth_amm.exceptions import SqrtPriceMathRevert
from python_eth_amm.uniswap_v3.math import UniswapV3Math


def is_within_bounds(a, b, tolerance: float = 0.000001):
    if a == 0 and b == 0:
        return True
    else:
        return abs(a - b) / a < tolerance


sqrt_prices = [
    250541448375047931186413801569,
    87150978765690771352898345369,
    2787593149816327892691964784081045188247552,
]

sqrt_prices_2 = [
    633825300114114700748351602688,
    79623317895830914510639640423,
    79228162514264337593543950336000,
]
ticks = [-60_000, 0, 60_000]

liquidity_values = [
    10**12,
    10**18,
    10**24,
]
amounts = [int(0.5 * 10**12), int(0.25 * 10**18), int(0.75 * 10**24)]


UniMath = UniswapV3Math.__new__(UniswapV3Math)
ExactUniMath = UniswapV3Math.__new__(UniswapV3Math)
ExactUniMath.initialize_exact_math()


class TestSqrtPriceMath:
    @pytest.mark.parametrize("sqrt_a", sqrt_prices)
    @pytest.mark.parametrize("sqrt_b", sqrt_prices_2)
    @pytest.mark.parametrize("liquidity", liquidity_values)
    def test_get_amount_deltas(self, sqrt_a, sqrt_b, liquidity):
        get_amount_0_exact = ExactUniMath.sqrt_price_math.get_amount_0_delta(
            sqrt_a,
            sqrt_b,
            liquidity,
        )
        get_amount_1_exact = ExactUniMath.sqrt_price_math.get_amount_1_delta(
            sqrt_a,
            sqrt_b,
            liquidity,
        )
        get_amount_0_approx = UniMath.sqrt_price_math.get_amount_0_delta(
            sqrt_a, sqrt_b, liquidity
        )
        get_amount_1_approx = UniMath.sqrt_price_math.get_amount_1_delta(
            sqrt_a, sqrt_b, liquidity
        )

        assert is_within_bounds(get_amount_0_exact, get_amount_0_approx)
        assert is_within_bounds(get_amount_1_exact, get_amount_1_approx)

    @pytest.mark.parametrize("sqrt_price", sqrt_prices)
    @pytest.mark.parametrize("liquidity", liquidity_values)
    @pytest.mark.parametrize("amount", amounts)
    @pytest.mark.parametrize("zero_for_one", [True, False])
    def test_get_next_sqrt_price(
        self, initialize_empty_pool, sqrt_price, liquidity, amount, zero_for_one
    ):
        try:
            sqrt_price_from_input_exact = (
                ExactUniMath.sqrt_price_math.get_next_sqrt_price_from_input(
                    sqrt_price,
                    liquidity,
                    amount,
                    zero_for_one,
                )
            )
            sqrt_price_from_output_exact = (
                ExactUniMath.sqrt_price_math.get_next_sqrt_price_from_output(
                    sqrt_price,
                    liquidity,
                    amount,
                    zero_for_one,
                )
            )
        except SqrtPriceMathRevert:
            return True

        sqrt_price_from_input_approx = (
            UniMath.sqrt_price_math.get_next_sqrt_price_from_input(
                sqrt_price, liquidity, amount, zero_for_one
            )
        )
        sqrt_price_from_output_approx = (
            UniMath.sqrt_price_math.get_next_sqrt_price_from_output(
                sqrt_price, liquidity, amount, zero_for_one
            )
        )

        assert is_within_bounds(
            sqrt_price_from_input_exact, sqrt_price_from_input_approx
        )
        assert is_within_bounds(
            sqrt_price_from_output_exact, sqrt_price_from_output_approx
        )


class TestTickMath:
    @pytest.mark.parametrize("sqrt_ratio", sqrt_prices + sqrt_prices_2)
    def test_get_tick_at_sqrt_ratio(self, sqrt_ratio):
        tick_at_ratio_exact = ExactUniMath.tick_math.get_tick_at_sqrt_ratio(sqrt_ratio)
        tick_at_ratio_approx = UniMath.tick_math.get_tick_at_sqrt_ratio(sqrt_ratio)

        assert tick_at_ratio_approx == tick_at_ratio_exact

    @pytest.mark.parametrize("tick", ticks)
    def test_get_sqrt_ratio_at_tick(self, tick):
        sqrt_ratio_at_tick_exact = ExactUniMath.tick_math.get_sqrt_ratio_at_tick(tick)
        sqrt_ratio_at_tick_approx = UniMath.tick_math.get_sqrt_ratio_at_tick(tick)

        assert is_within_bounds(sqrt_ratio_at_tick_exact, sqrt_ratio_at_tick_approx)
