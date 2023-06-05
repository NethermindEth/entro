from decimal import Decimal
from logging import Logger
from math import ceil, floor

from pydantic import BaseModel

from python_eth_amm.exceptions import FullMathRevert, UniswapV3Revert

from . import FullMathModule, SqrtPriceMathModule, TickMathModule
from .base import TranslatedMathModule


class SwapComputation(BaseModel):
    """Model to store the results of a swap computation"""

    sqrt_price_next: int
    amount_in: int
    amount_out: int
    fee_amount: int


# pylint: disable=missing-function-docstring

# TODO: Document Math Module


def overflow_check(number, max_value):
    if number >= max_value:
        raise UniswapV3Revert(f"{number} Overflowed Max Value of: {max_value}")

    return number


def input_check(tick: int = None, sqrt_price: float = None):
    if tick:
        if tick > TickMathModule.MAX_TICK or tick < TickMathModule.MIN_TICK:
            raise UniswapV3Revert(f"Tick Index out of Bounds: {tick}")
    if sqrt_price:
        if (
            sqrt_price < SqrtPriceMathModule.MIN_SQRT_RATIO
            or sqrt_price > SqrtPriceMathModule.MAX_SQRT_RATIO
        ):
            raise UniswapV3Revert(
                f"Square Root Price Ration out of Bounds: {sqrt_price}"
            )


class UniswapV3SwapMath(TranslatedMathModule):
    """
    Math Module to compute Sqrt Price Deltas and Swap Amounts for Uniswap V3 Pools
    """

    logger: Logger
    full_math: FullMathModule
    tick_math: TickMathModule

    SQRT_RESOLUTION = 96
    SQRT_Q96 = 0x1000000000000000000000000
    Q128 = 0x100000000000000000000000000000000
    UINT_128_MAX = 2**128 - 1
    UINT_160_MAX = 2**160 - 1
    UINT_256_MAX = 2**256 - 1

    def __new__(cls, factory):
        cls.factory = factory
        cls.full_math = factory._get_math_module("FullMathModule")
        cls.tick_math = factory._get_math_module("TickMathModule")
        cls.logger = factory.logger
        return cls

    @classmethod
    def check_ticks(cls, tick_lower: int, tick_upper: int):
        if tick_lower > tick_upper:
            raise UniswapV3Revert("tick_lower cannot be larger than tick_upper")
        if tick_lower < TickMathModule.MIN_TICK:
            raise UniswapV3Revert("tick_lower must be greater than MIN_TICK")
        if tick_upper > TickMathModule.MAX_TICK:
            raise UniswapV3Revert("tick_upper must be less than MAX_TICK")

    @classmethod
    def get_max_liquidity_per_tick(cls, tick_spacing: int) -> int:
        max_tick = TickMathModule.MAX_TICK - TickMathModule.MAX_TICK % tick_spacing

        number_of_ticks = int((max_tick * 2) / tick_spacing) + 1
        return int(Decimal(cls.UINT_128_MAX) / Decimal(number_of_ticks))

    @classmethod
    def get_next_sqrt_price_from_amount_0_rounding_up(
        cls,
        sqrt_price: int,
        liquidity: int,
        amount: int,
        add: bool,
        exact_rounding: bool,
    ) -> int:
        if amount == 0:
            return sqrt_price

        numerator_1 = liquidity << cls.SQRT_RESOLUTION

        if add:
            if amount * sqrt_price <= cls.UINT_256_MAX:
                denominator = numerator_1 + (amount * sqrt_price)
                if denominator >= numerator_1:
                    try:
                        return cls.full_math.mul_div_rounding_up(
                            numerator_1, sqrt_price, denominator, exact_rounding
                        )
                    except FullMathRevert as exc:
                        raise UniswapV3Revert from exc

            # uint160(UnsafeMath.divRoundingUp(numerator1, (numerator1 / sqrtPX96).add(amount)))
            return ceil(numerator_1 / ((numerator_1 / sqrt_price) + amount))
        if (
            amount * sqrt_price >= cls.UINT_256_MAX
            or numerator_1 <= amount * sqrt_price
        ):
            raise UniswapV3Revert
        try:
            return_value = cls.full_math.mul_div_rounding_up(
                numerator_1,
                sqrt_price,
                numerator_1 - (amount * sqrt_price),
                exact_rounding,
            )
        except FullMathRevert as exc:
            raise UniswapV3Revert from exc

        if return_value >= cls.UINT_160_MAX:
            raise UniswapV3Revert
        return return_value

    @classmethod
    def get_next_sqrt_price_from_amount_1_rounding_down(
        cls,
        sqrt_price: int,
        liquidity: int,
        amount: int,
        add: bool,
        exact_rounding: bool,
    ):
        if add:
            try:
                quotient = cls.full_math.mul_div(
                    amount, cls.SQRT_Q96, liquidity, exact_rounding
                )
            except FullMathRevert as exc:
                raise UniswapV3Revert from exc

            if sqrt_price + quotient >= cls.UINT_160_MAX:
                raise UniswapV3Revert("UINT_160_MAX Overflow")
            return sqrt_price + quotient

        try:
            quotient = cls.full_math.mul_div_rounding_up(
                amount, cls.SQRT_Q96, liquidity, exact_rounding
            )
        except FullMathRevert as exc:
            raise UniswapV3Revert from exc

        if sqrt_price <= quotient:
            raise UniswapV3Revert("Sqrt Price cannot be less than quotient")
        return sqrt_price - quotient

    @classmethod
    def get_next_sqrt_price_from_input(
        cls,
        sqrt_price: int,
        liquidity: int,
        amount_in: int,
        zero_for_one: bool,
        exact_rounding: bool = False,
    ):
        if sqrt_price <= 0 or liquidity <= 0:
            raise UniswapV3Revert("sqrt_price and liquidity must be greater than 0")

        return (
            cls.get_next_sqrt_price_from_amount_0_rounding_up(
                sqrt_price, liquidity, amount_in, True, exact_rounding
            )
            if zero_for_one
            else cls.get_next_sqrt_price_from_amount_1_rounding_down(
                sqrt_price, liquidity, amount_in, True, exact_rounding
            )
        )

    @classmethod
    def get_next_sqrt_price_from_output(
        cls,
        sqrt_price: int,
        liquidity: int,
        amount_out: int,
        zero_for_one: bool,
        exact_rounding: bool = False,
    ):
        if sqrt_price <= 0 or liquidity <= 0:
            raise UniswapV3Revert("sqrt_price and liquidity must be greater than 0")

        return (
            cls.get_next_sqrt_price_from_amount_1_rounding_down(
                sqrt_price, liquidity, amount_out, False, exact_rounding
            )
            if zero_for_one
            else cls.get_next_sqrt_price_from_amount_0_rounding_up(
                sqrt_price, liquidity, amount_out, False, exact_rounding
            )
        )

    @classmethod
    def _get_amount_0_delta(
        cls,
        sqrt_price_a: int,
        sqrt_price_b: int,
        liquidity: int,
        round_up: bool,
        exact_rounding: bool,
    ):
        if sqrt_price_a > sqrt_price_b:
            sqrt_price_a, sqrt_price_b = sqrt_price_b, sqrt_price_a
        numerator_1, numerator_2 = (
            liquidity << cls.SQRT_RESOLUTION,
            sqrt_price_b - sqrt_price_a,
        )
        if sqrt_price_a <= 0:
            raise UniswapV3Revert("sqrt_price_a must be greater than 0")
        un_rounded_value = Decimal(
            str(
                cls.full_math.mul_div_rounding_up(
                    numerator_1, numerator_2, sqrt_price_b, exact_rounding
                )
            )
        ) / Decimal(str(sqrt_price_a))

        return ceil(un_rounded_value) if round_up else floor(un_rounded_value)

    @classmethod
    def _get_amount_1_delta(
        cls,
        sqrt_price_a: int,
        sqrt_price_b: int,
        liquidity: int,
        round_up: bool,
        exact_rounding: bool,
    ) -> int:
        if sqrt_price_a > sqrt_price_b:
            sqrt_price_a, sqrt_price_b = sqrt_price_b, sqrt_price_a

        return (
            cls.full_math.mul_div_rounding_up(
                liquidity, sqrt_price_b - sqrt_price_a, cls.SQRT_Q96, exact_rounding
            )
            if round_up
            else cls.full_math.mul_div(
                liquidity, sqrt_price_b - sqrt_price_a, cls.SQRT_Q96, exact_rounding
            )
        )

    @classmethod
    def get_amount_0_delta(
        cls,
        sqrt_price_a: int,
        sqrt_price_b: int,
        liquidity: int,
        exact_rounding: bool = False,
    ) -> int:
        if liquidity < 0:
            return -1 * overflow_check(
                cls._get_amount_0_delta(
                    sqrt_price_a, sqrt_price_b, abs(liquidity), False, exact_rounding
                ),
                cls.UINT_256_MAX,
            )
        return overflow_check(
            cls._get_amount_0_delta(
                sqrt_price_a, sqrt_price_b, abs(liquidity), True, exact_rounding
            ),
            cls.UINT_256_MAX,
        )

    @classmethod
    def get_amount_1_delta(
        cls,
        sqrt_price_a: int,
        sqrt_price_b: int,
        liquidity: int,
        exact_rounding: bool = False,
    ) -> int:
        if liquidity < 0:
            return -1 * overflow_check(
                cls._get_amount_1_delta(
                    sqrt_price_a, sqrt_price_b, abs(liquidity), False, exact_rounding
                ),
                cls.UINT_256_MAX,
            )
        return overflow_check(
            cls._get_amount_1_delta(
                sqrt_price_a, sqrt_price_b, abs(liquidity), True, exact_rounding
            ),
            cls.UINT_256_MAX,
        )

    @classmethod
    def compute_swap_step(
        cls,
        sqrt_price_current: int,
        sqrt_price_target: int,
        liquidity: int,
        amount_remaining: int,
        fee_pips: int,
        exact_rounding: bool = False,
    ) -> SwapComputation:
        # pylint: disable=too-many-branches
        zero_for_one, exact_input = (
            sqrt_price_current >= sqrt_price_target,
            amount_remaining >= 0,
        )
        if exact_input:
            amount_remaining_less_fee = cls.full_math.mul_div(
                amount_remaining, 1_000_000 - fee_pips, 1_000_000, exact_rounding
            )
            if zero_for_one:
                amount_in = cls._get_amount_0_delta(
                    sqrt_price_target,
                    sqrt_price_current,
                    liquidity,
                    True,
                    exact_rounding,
                )
            else:
                amount_in = cls._get_amount_1_delta(
                    sqrt_price_current,
                    sqrt_price_target,
                    liquidity,
                    True,
                    exact_rounding,
                )

            if amount_remaining_less_fee >= amount_in:
                sqrt_price_next = sqrt_price_target
            else:
                sqrt_price_next = cls.get_next_sqrt_price_from_input(
                    sqrt_price_current,
                    liquidity,
                    amount_remaining_less_fee,
                    zero_for_one,
                    exact_rounding,
                )

        else:
            amount_out = (
                cls._get_amount_1_delta(
                    sqrt_price_target,
                    sqrt_price_current,
                    liquidity,
                    False,
                    exact_rounding,
                )
                if zero_for_one
                else cls._get_amount_0_delta(
                    sqrt_price_current,
                    sqrt_price_target,
                    liquidity,
                    False,
                    exact_rounding,
                )
            )

            if abs(amount_remaining) >= amount_out:
                sqrt_price_next = sqrt_price_target
            else:
                sqrt_price_next = cls.get_next_sqrt_price_from_output(
                    sqrt_price_current,
                    liquidity,
                    abs(amount_remaining),
                    zero_for_one,
                    exact_rounding,
                )

        max = sqrt_price_target == sqrt_price_next

        if zero_for_one:
            if max and exact_input:
                pass
            else:
                amount_in = cls._get_amount_0_delta(
                    sqrt_price_next, sqrt_price_current, liquidity, True, exact_rounding
                )

            if max and not exact_input:
                pass
            else:
                amount_out = cls._get_amount_1_delta(
                    sqrt_price_next,
                    sqrt_price_current,
                    liquidity,
                    False,
                    exact_rounding,
                )

        else:
            if max and exact_input:
                pass
            else:
                amount_in = cls._get_amount_1_delta(
                    sqrt_price_current, sqrt_price_next, liquidity, True, exact_rounding
                )

            if max and not exact_input:
                pass
            else:
                amount_out = cls._get_amount_0_delta(
                    sqrt_price_current,
                    sqrt_price_next,
                    liquidity,
                    False,
                    exact_rounding,
                )

        if not exact_input and amount_out > abs(amount_remaining):
            amount_out = abs(amount_remaining)

        if exact_input and sqrt_price_next != sqrt_price_target:
            fee_amount = amount_remaining - amount_in
        else:
            fee_amount = cls.full_math.mul_div_rounding_up(
                amount_in, fee_pips, 1_000_000 - fee_pips, exact_rounding
            )

        return SwapComputation(
            sqrt_price_next=sqrt_price_next,
            amount_in=amount_in,
            amount_out=amount_out,
            fee_amount=fee_amount,
        )
