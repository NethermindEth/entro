import pytest

from nethermind.entro.exceptions import FullMathRevert
from nethermind.entro.uniswap_v3.math import UniswapV3Math

UniV3Math = UniswapV3Math.__new__(UniswapV3Math)
UniV3Math.initialize_exact_math()


class TestMulDiv:
    Q128 = 2**128
    UINT256_MAX = (2**256) - 1

    def test_raises_if_denomincator_is_0(
        self,
    ):
        with pytest.raises(FullMathRevert):
            UniV3Math.full_math.mul_div(
                self.Q128,
                5,
                0,
            )

    def test_raises_if_denominator_is_0_and_numerator_overflows(
        self,
    ):
        with pytest.raises(FullMathRevert):
            UniV3Math.full_math.mul_div(
                self.Q128,
                self.Q128,
                0,
            )

    def test_reverts_if_output_overflows_uint256(
        self,
    ):
        with pytest.raises(FullMathRevert):
            UniV3Math.full_math.mul_div(
                self.Q128,
                self.Q128,
                1,
            )

    def test_reverts_on_overflow_with_all_max_inputs(
        self,
    ):
        with pytest.raises(FullMathRevert):
            UniV3Math.full_math.mul_div(
                self.UINT256_MAX,
                self.UINT256_MAX,
                self.UINT256_MAX - 1,
            )

    def test_is_accurate_without_fantom_overflow(
        self,
    ):
        result = int(4375 * self.Q128 / 1000)
        assert (
            UniV3Math.full_math.mul_div(
                self.Q128,
                self.Q128 * 35,
                self.Q128 * 8,
            )
            == result
        )

    def test_is_accurate_with_phantom_overflow_and_repeating_decimal(
        self,
    ):
        assert (
            UniV3Math.full_math.mul_div(
                self.Q128,
                self.Q128 * 1000,
                self.Q128 * 3000,
            )
            == 113427455640312821154458202477256070485
        )


class TestMulDivRoundingUp:
    Q128 = 2**128
    UINT256_MAX = (2**256) - 1

    def test_raises_if_denomincator_is_0(
        self,
    ):
        with pytest.raises(FullMathRevert):
            UniV3Math.full_math.mul_div_rounding_up(
                self.Q128,
                5,
                0,
            )

    def test_raises_if_denominator_is_0_and_numerator_overflows(
        self,
    ):
        with pytest.raises(FullMathRevert):
            UniV3Math.full_math.mul_div_rounding_up(
                self.Q128,
                self.Q128,
                0,
            )

    def test_reverts_if_output_overflows_uint256(
        self,
    ):
        with pytest.raises(FullMathRevert):
            UniV3Math.full_math.mul_div_rounding_up(
                self.Q128,
                self.Q128,
                1,
            )

    def test_reverts_on_overflow_with_all_max_inputs(
        self,
    ):
        with pytest.raises(FullMathRevert):
            UniV3Math.full_math.mul_div_rounding_up(
                self.UINT256_MAX,
                self.UINT256_MAX,
                self.UINT256_MAX - 1,
            )

    def test_reverts_if_mul_div_overflows_after_rounding_up(
        self,
    ):
        with pytest.raises(FullMathRevert):
            UniV3Math.full_math.mul_div_rounding_up(
                535006138814359,
                432862656469423142931042426214547535783388063929571229938474969,
                2,
            )

    def test_reverts_if_mul_div_overflows_after_rounding_up_case_2(
        self,
    ):
        with pytest.raises(FullMathRevert):
            UniV3Math.full_math.mul_div_rounding_up(
                115792089237316195423570985008687907853269984659341747863450311749907997002549,
                115792089237316195423570985008687907853269984659341747863450311749907997002550,
                115792089237316195423570985008687907853269984653042931687443039491902864365164,
            )

    def test_all_max_inputs(
        self,
    ):
        assert (
            UniV3Math.full_math.mul_div_rounding_up(
                self.UINT256_MAX,
                self.UINT256_MAX,
                self.UINT256_MAX,
            )
            == self.UINT256_MAX
        )

    def test_is_accurate_without_fantom_overflow(
        self,
    ):
        assert (
            UniV3Math.full_math.mul_div_rounding_up(
                self.Q128,
                int(self.Q128 * 0.5),
                int(self.Q128 * 1.5),
            )
            == 113427455640312821154458202477256070486
        )

    def test_is_accurate_with_fantom_overflow(
        self,
    ):
        result = int(4375 * self.Q128 / 1000)
        assert (
            UniV3Math.full_math.mul_div_rounding_up(
                self.Q128,
                self.Q128 * 35,
                self.Q128 * 8,
            )
            == result
        )

    def test_is_accurate_with_phantom_overflow_and_repeating_decimal(
        self,
    ):
        assert (
            UniV3Math.full_math.mul_div_rounding_up(
                self.Q128,
                int(self.Q128 * 1000),
                int(self.Q128 * 3000),
            )
            == 113427455640312821154458202477256070486
        )
