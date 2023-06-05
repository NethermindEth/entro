import logging
import os

import pytest

from python_eth_amm import PoolFactory
from python_eth_amm.exceptions import FullMathRevert

from ..utils import TEST_LOGGER

FULL_MATH_FACTORY = PoolFactory(
    exact_math=True,
    logger=TEST_LOGGER,
    sqlalchemy_uri=os.environ["SQLALCHEMY_DB_URI"],
)


class TestMulDiv:
    Q128 = 2**128
    UINT256_MAX = (2**256) - 1

    def test_raises_if_denomincator_is_0(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=FULL_MATH_FACTORY)
        with pytest.raises(FullMathRevert):
            pool.math.full_math.mul_div(self.Q128, 5, 0, exact_rounding=True)

    def test_raises_if_denominator_is_0_and_numerator_overflows(
        self, initialize_empty_pool
    ):
        pool = initialize_empty_pool(pool_factory=FULL_MATH_FACTORY)
        with pytest.raises(FullMathRevert):
            pool.math.full_math.mul_div(self.Q128, self.Q128, 0, exact_rounding=True)

    def test_reverts_if_output_overflows_uint256(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=FULL_MATH_FACTORY)
        with pytest.raises(FullMathRevert):
            pool.math.full_math.mul_div(self.Q128, self.Q128, 1, exact_rounding=True)

    def test_reverts_on_overflow_with_all_max_inputs(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=FULL_MATH_FACTORY)
        with pytest.raises(FullMathRevert):
            pool.math.full_math.mul_div(
                self.UINT256_MAX,
                self.UINT256_MAX,
                self.UINT256_MAX - 1,
                exact_rounding=True,
            )

    def test_is_accurate_without_fantom_overflow(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=FULL_MATH_FACTORY)
        result = int(4375 * self.Q128 / 1000)
        assert (
            pool.math.full_math.mul_div(
                self.Q128, self.Q128 * 35, self.Q128 * 8, exact_rounding=True
            )
            == result
        )

    def test_is_accurate_with_phantom_overflow_and_repeating_decimal(
        self, initialize_empty_pool
    ):
        pool = initialize_empty_pool(pool_factory=FULL_MATH_FACTORY)
        assert (
            pool.math.full_math.mul_div(
                self.Q128, self.Q128 * 1000, self.Q128 * 3000, exact_rounding=True
            )
            == 113427455640312821154458202477256070485
        )


class TestMulDivRoundingUp:
    Q128 = 2**128
    UINT256_MAX = (2**256) - 1

    def test_raises_if_denomincator_is_0(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=FULL_MATH_FACTORY)
        with pytest.raises(FullMathRevert):
            pool.math.full_math.mul_div_rounding_up(
                self.Q128, 5, 0, exact_rounding=True
            )

    def test_raises_if_denominator_is_0_and_numerator_overflows(
        self, initialize_empty_pool
    ):
        pool = initialize_empty_pool(pool_factory=FULL_MATH_FACTORY)
        with pytest.raises(FullMathRevert):
            pool.math.full_math.mul_div_rounding_up(
                self.Q128, self.Q128, 0, exact_rounding=True
            )

    def test_reverts_if_output_overflows_uint256(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=FULL_MATH_FACTORY)
        with pytest.raises(FullMathRevert):
            pool.math.full_math.mul_div_rounding_up(
                self.Q128, self.Q128, 1, exact_rounding=True
            )

    def test_reverts_on_overflow_with_all_max_inputs(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=FULL_MATH_FACTORY)
        with pytest.raises(FullMathRevert):
            pool.math.full_math.mul_div_rounding_up(
                self.UINT256_MAX,
                self.UINT256_MAX,
                self.UINT256_MAX - 1,
                exact_rounding=True,
            )

    def test_reverts_if_mul_div_overflows_after_rounding_up(
        self, initialize_empty_pool
    ):
        pool = initialize_empty_pool(pool_factory=FULL_MATH_FACTORY)
        with pytest.raises(FullMathRevert):
            pool.math.full_math.mul_div_rounding_up(
                535006138814359,
                432862656469423142931042426214547535783388063929571229938474969,
                2,
                exact_rounding=True,
            )

    def test_reverts_if_mul_div_overflows_after_rounding_up_case_2(
        self, initialize_empty_pool
    ):
        pool = initialize_empty_pool(pool_factory=FULL_MATH_FACTORY)
        with pytest.raises(FullMathRevert):
            pool.math.full_math.mul_div_rounding_up(
                115792089237316195423570985008687907853269984659341747863450311749907997002549,
                115792089237316195423570985008687907853269984659341747863450311749907997002550,
                115792089237316195423570985008687907853269984653042931687443039491902864365164,
                exact_rounding=True,
            )

    def test_all_max_inputs(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=FULL_MATH_FACTORY)
        assert (
            pool.math.full_math.mul_div_rounding_up(
                self.UINT256_MAX,
                self.UINT256_MAX,
                self.UINT256_MAX,
                exact_rounding=True,
            )
            == self.UINT256_MAX
        )

    def test_is_accurate_without_fantom_overflow(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=FULL_MATH_FACTORY)
        assert (
            pool.math.full_math.mul_div_rounding_up(
                self.Q128,
                int(self.Q128 * 0.5),
                int(self.Q128 * 1.5),
                exact_rounding=True,
            )
            == 113427455640312821154458202477256070486
        )

    def test_is_accurate_with_fantom_overflow(self, initialize_empty_pool):
        pool = initialize_empty_pool(pool_factory=FULL_MATH_FACTORY)
        result = int(4375 * self.Q128 / 1000)
        assert (
            pool.math.full_math.mul_div_rounding_up(
                self.Q128, self.Q128 * 35, self.Q128 * 8, exact_rounding=True
            )
            == result
        )

    def test_is_accurate_with_phantom_overflow_and_repeating_decimal(
        self, initialize_empty_pool
    ):
        pool = initialize_empty_pool(pool_factory=FULL_MATH_FACTORY)
        assert (
            pool.math.full_math.mul_div_rounding_up(
                self.Q128,
                int(self.Q128 * 1000),
                int(self.Q128 * 3000),
                exact_rounding=True,
            )
            == 113427455640312821154458202477256070486
        )
