import logging
import os

import pytest

from python_eth_amm import PoolFactory
from python_eth_amm.exceptions import UniswapV3Revert

from ..utils import expand_to_decimals, uint_max
from .utils import encode_sqrt_price

SQRT_PRICE_MATH_FACTORY = PoolFactory(
    exact_math=True,
    logger=logging.Logger("test"),
    sqlalchemy_uri=os.environ["SQLALCHEMY_DB_URI"],
)


class TestGetNextSQRTPriceInput:
    def test_raises_if_price_is_zero(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
        with pytest.raises(UniswapV3Revert):
            pool.math.get_next_sqrt_price_from_input(
                0, 0, expand_to_decimals(1), False, exact_rounding=True
            )

    def test_raises_if_liquidity_is_zero(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
        with pytest.raises(UniswapV3Revert):
            pool.math.get_next_sqrt_price_from_input(
                1, 0, expand_to_decimals(1), False, exact_rounding=True
            )

    def test_raises_if_amount_overflows_price(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
        with pytest.raises(UniswapV3Revert):
            pool.math.get_next_sqrt_price_from_input(
                uint_max(160), 1024, 1024, False, exact_rounding=True
            )

    def test_input_can_not_underflow_price(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
        assert (
            pool.math.get_next_sqrt_price_from_input(
                1, 1, 2**255, True, exact_rounding=True
            )
            == 1
        )

    def test_returns_input_price_if_amount_in_is_zero_and_zero_for_one_is_false(
        self, initialize_empty_pool
    ):
        pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
        price = encode_sqrt_price(1, 1)
        assert (
            pool.math.get_next_sqrt_price_from_input(
                price, expand_to_decimals(1, 17), 0, False, exact_rounding=True
            )
            == price
        )

    def test_returns_input_price_if_amount_in_is_zero_and_zero_for_one_is_true(
        self, initialize_empty_pool
    ):
        pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
        price = encode_sqrt_price(1, 1)
        assert (
            pool.math.get_next_sqrt_price_from_input(
                price, expand_to_decimals(1, 17), 0, True, exact_rounding=True
            )
            == price
        )

    def test_returns_minimum_price_for_max_inputs(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
        sqrt_price = uint_max(160)
        liquidity = uint_max(128)
        max_amount_no_overflow = uint_max(256) - liquidity / (2**96 * sqrt_price)
        assert (
            pool.math.get_next_sqrt_price_from_input(
                sqrt_price, liquidity, max_amount_no_overflow, True, exact_rounding=True
            )
            == 1
        )

    def test_inputting_specific_token_amount_token_1(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
        sqrt_price = pool.math.get_next_sqrt_price_from_input(
            encode_sqrt_price(1, 1),
            expand_to_decimals(1, 18),
            expand_to_decimals(1, 17),
            False,
            exact_rounding=True,
        )
        assert sqrt_price == 87150978765690771352898345369

    def test_inputting_specific_token_amount_token_0(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
        sqrt_price = pool.math.get_next_sqrt_price_from_input(
            encode_sqrt_price(1, 1),
            expand_to_decimals(1, 18),
            expand_to_decimals(1, 17),
            True,
            exact_rounding=True,
        )
        assert sqrt_price == 72025602285694852357767227579

    def test_amount_in_greater_than_sqrt_price_max(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
        sqrt_price = pool.math.get_next_sqrt_price_from_input(
            encode_sqrt_price(1, 1),
            expand_to_decimals(10, 18),
            2**100,
            True,
            exact_rounding=True,
        )
        assert sqrt_price == 624999999995069620

    def test_returns_1_with_enough_amount_in(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
        assert (
            pool.math.get_next_sqrt_price_from_input(
                encode_sqrt_price(1, 1), 1, uint_max(128), True, exact_rounding=True
            )
            == 1
        )


class TestGetNextSQRTPriceOutput:
    def test_raises_when_price_is_zero(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
        with pytest.raises(UniswapV3Revert):
            pool.math.get_next_sqrt_price_from_output(
                0, 0, expand_to_decimals(1, 17), False, exact_rounding=True
            )

    def test_raises_when_liquidity_is_zero(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
        with pytest.raises(UniswapV3Revert):
            pool.math.get_next_sqrt_price_from_output(
                1, 0, expand_to_decimals(1, 17), False, exact_rounding=True
            )

    def test_raises_if_amount_out_equals_token0_virtual_reserves(
        self, initialize_empty_pool
    ):
        pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
        with pytest.raises(UniswapV3Revert):
            price = 20282409603651670423947251286016
            pool.math.get_next_sqrt_price_from_output(
                price, 1024, 4, False, exact_rounding=True
            )

    def test_raises_if_amount_out_greater_than_token0_virtual_reserves(
        self, initialize_empty_pool
    ):
        pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
        with pytest.raises(UniswapV3Revert):
            price = 20282409603651670423947251286016
            pool.math.get_next_sqrt_price_from_output(
                price, 1024, 5, False, exact_rounding=True
            )

    def test_raises_if_amount_out_equals_token1_virtual_reserves(
        self, initialize_empty_pool
    ):
        pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
        with pytest.raises(UniswapV3Revert):
            price = 20282409603651670423947251286016
            pool.math.get_next_sqrt_price_from_output(
                price, 1024, 262145, True, exact_rounding=True
            )

    def test_raises_if_amount_out_greater_than_token1_virtual_reserves(
        self, initialize_empty_pool
    ):
        pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
        with pytest.raises(UniswapV3Revert):
            price = 20282409603651670423947251286016
            pool.math.get_next_sqrt_price_from_output(
                price, 1024, 262144, True, exact_rounding=True
            )

    def test_succeeds_if_amount_out_is_less_than_token_1_virtual_reserves(
        self, initialize_empty_pool
    ):
        pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
        price = 20282409603651670423947251286016
        next_price = pool.math.get_next_sqrt_price_from_output(
            price, 1024, 262143, True, exact_rounding=True
        )
        assert next_price == 77371252455336267181195264

    @pytest.mark.skip("Edge cases will be handled at later date")
    def test_echnidna_edge_case(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
        with pytest.raises(UniswapV3Revert):
            price = 20282409603651670423947251286016
            pool.math.get_next_sqrt_price_from_output(
                price, 1024, 4, True, exact_rounding=True
            )

    def test_returns_if_amount_in_is_zero_and_zero_for_one_is_true(
        self, initialize_empty_pool
    ):
        pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
        price = encode_sqrt_price(1, 1)
        assert (
            pool.math.get_next_sqrt_price_from_output(
                price, expand_to_decimals(1, 17), 0, True, exact_rounding=True
            )
            == price
        )

    def test_returns_if_amount_in_is_zero_and_zero_for_one_is_false(
        self, initialize_empty_pool
    ):
        pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
        price = encode_sqrt_price(1, 1)
        assert (
            pool.math.get_next_sqrt_price_from_output(
                price, expand_to_decimals(1, 17), 0, False, exact_rounding=True
            )
            == price
        )

    def test_inputting_specific_token_amount_token_1(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
        sqrt_price = pool.math.get_next_sqrt_price_from_output(
            encode_sqrt_price(1, 1),
            expand_to_decimals(1, 18),
            expand_to_decimals(1, 17),
            False,
            exact_rounding=True,
        )
        assert sqrt_price == 88031291682515930659493278152

    def test_inputting_specific_token_amount_token_0(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
        sqrt_price = pool.math.get_next_sqrt_price_from_output(
            encode_sqrt_price(1, 1),
            expand_to_decimals(1, 18),
            expand_to_decimals(1, 17),
            True,
            exact_rounding=True,
        )
        assert sqrt_price == 71305346262837903834189555302

    def test_raises_if_amount_out_is_impossible_in_zero_for_one_direction(
        self, initialize_empty_pool
    ):
        pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
        with pytest.raises(UniswapV3Revert):
            pool.math.get_next_sqrt_price_from_output(
                encode_sqrt_price(1, 1), 1, uint_max(256), True, exact_rounding=True
            )

    def test_raises_if_amount_out_is_impossible_in_one_for_zero_direction(
        self, initialize_empty_pool
    ):
        pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
        with pytest.raises(UniswapV3Revert):
            pool.math.get_next_sqrt_price_from_output(
                encode_sqrt_price(1, 1), 1, uint_max(256), False, exact_rounding=True
            )


class TestGetAmount0Delta:
    def test_returns_zero_if_liquidty_is_zero(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
        assert (
            pool.math._get_amount_0_delta(
                encode_sqrt_price(1, 1),
                encode_sqrt_price(2, 1),
                0,
                True,
                exact_rounding=True,
            )
            == 0
        )

    def test_returns_zero_if_prices_equal(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
        assert (
            pool.math._get_amount_0_delta(
                encode_sqrt_price(1, 1),
                encode_sqrt_price(1, 1),
                0,
                True,
                exact_rounding=True,
            )
            == 0
        )

    def test_returns_correct_amount_1(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
        assert (
            pool.math._get_amount_0_delta(
                encode_sqrt_price(1, 1),
                encode_sqrt_price(121, 100),
                expand_to_decimals(1, 18),
                True,
                exact_rounding=True,
            )
            == 90909090909090910
        )

        assert (
            pool.math._get_amount_0_delta(
                encode_sqrt_price(1, 1),
                encode_sqrt_price(121, 100),
                expand_to_decimals(1, 18),
                False,
                exact_rounding=True,
            )
            == 90909090909090909
        )

    def test_overflowing_prices(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
        amount_0_up = pool.math._get_amount_0_delta(
            encode_sqrt_price(2**90, 1),
            encode_sqrt_price(2**96, 1),
            expand_to_decimals(1, 18),
            True,
            exact_rounding=True,
        )
        amount_0_down = pool.math._get_amount_0_delta(
            encode_sqrt_price(2**90, 1),
            encode_sqrt_price(2**96, 1),
            expand_to_decimals(1, 18),
            False,
            exact_rounding=True,
        )

        assert amount_0_up == amount_0_down + 1


class TestGetAmount1Delta:
    def test_returns_zero_if_liquidty_is_zero(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
        assert (
            pool.math._get_amount_1_delta(
                encode_sqrt_price(1, 1),
                encode_sqrt_price(2, 1),
                0,
                True,
                exact_rounding=True,
            )
            == 0
        )

    def test_returns_zero_if_prices_equal(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
        assert (
            pool.math._get_amount_1_delta(
                encode_sqrt_price(1, 1),
                encode_sqrt_price(1, 1),
                0,
                True,
                exact_rounding=True,
            )
            == 0
        )

    def test_returns_correct_amount_1(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
        assert (
            pool.math._get_amount_1_delta(
                encode_sqrt_price(1, 1),
                encode_sqrt_price(121, 100),
                expand_to_decimals(1, 18),
                True,
                exact_rounding=True,
            )
            == 100000000000000000
        )

        assert (
            pool.math._get_amount_1_delta(
                encode_sqrt_price(1, 1),
                encode_sqrt_price(121, 100),
                expand_to_decimals(1, 18),
                False,
                exact_rounding=True,
            )
            == 100000000000000000 - 1
        )


def test_swap_computation(initialize_empty_pool):
    pool = initialize_empty_pool(pool_factory=SQRT_PRICE_MATH_FACTORY)
    sqrt_price = 1025574284609383690408304870162715216695788925244
    liquidity = 50015962439936049619261659728067971248
    sqrt_q = pool.math.get_next_sqrt_price_from_input(
        sqrt_price, liquidity, 406, True, exact_rounding=True
    )
    assert sqrt_q == 1025574284609383582644711336373707553698163132913
    assert (
        pool.math._get_amount_0_delta(
            sqrt_q, sqrt_price, liquidity, True, exact_rounding=True
        )
        == 406
    )
