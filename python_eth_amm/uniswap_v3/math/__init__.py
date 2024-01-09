import logging
from decimal import Decimal, getcontext
from math import ceil, floor

from python_eth_amm.exceptions import FullMathRevert, UniswapV3Revert

from .full_math import FullMathModule
from .shared import (
    FEES_TO_TICK_SPACINGS,
    MAX_SQRT_RATIO,
    MAX_TICK,
    MIN_SQRT_RATIO,
    MIN_TICK,
    Q128,
    SQRT_Q96,
    SQRT_RESOLUTION,
    TICK_SPACINGS_TO_FEES,
    UINT_128_MAX,
    UINT_160_MAX,
    UINT_256_MAX,
    SwapComputation,
    check_sqrt_price,
    check_ticks,
    get_max_liquidity_per_tick,
    overflow_check,
)
from .sqrt_price_math import SqrtPriceMathModule
from .tick_math import TickMathModule

package_logger = logging.getLogger("python_eth_amm")
v3_logger = package_logger.getChild("uniswap_v3")
logger = v3_logger.getChild("math")


class UniswapV3Math:
    """
    Class for interacting with the UniswapV3 Math Contracts
    """

    MAX_SQRT_RATIO = MAX_SQRT_RATIO
    MIN_SQRT_RATIO = MIN_SQRT_RATIO

    MAX_TICK = MAX_TICK
    MIN_TICK = MIN_TICK

    UINT_128_MAX = UINT_128_MAX
    Q128 = Q128

    # Math Modules

    full_math = FullMathModule
    sqrt_price_math = SqrtPriceMathModule
    tick_math = TickMathModule

    # Swap Math Methods

    get_max_liquidity_per_tick = classmethod(get_max_liquidity_per_tick)

    # Safety Methods
    check_ticks = classmethod(check_ticks)
    check_sqrt_price = classmethod(check_sqrt_price)

    # -----------------------------------------------------------------------
    _evm_state = None
    exact_math: bool = False

    @classmethod
    def initialize_exact_math(cls):
        """
        Enables exact math mode for all pools.  Exact math mode is slower, but more closely matches the on-chain
        behavior of Uniswap V3 pools.  Exact math mode is disabled by default.
        """

        # pylint: disable=import-outside-toplevel,no-name-in-module,import-error
        from pyrevm import EVM  # type: ignore[attr-defined]

        # pylint: enable=import-outside-toplevel,no-name-in-module,import-error

        cls.exact_math = True
        getcontext().prec = 78
        cls._evm_state = EVM()

        cls.full_math.depoly_exact_math_mode(cls._evm_state)
        cls.sqrt_price_math.depoly_exact_math_mode(cls._evm_state)
        cls.tick_math.depoly_exact_math_mode(cls._evm_state)

    # -----------------------------------------------------------------------
    # Input, Overflow, and Underflow Checks
    # -----------------------------------------------------------------------

    @classmethod
    def get_fee_and_spacing(cls, init_kwargs: dict) -> tuple[int, int]:
        """
        Returns the fee and tick spacing for a given pool.  If no fee or tick spacing is provided, the default values
        of 3000 and 60 are returned.

        :param init_kwargs:
        :return:
        """
        provided_fee = init_kwargs.get("fee")
        provided_spacing = init_kwargs.get("tick_spacing")

        if provided_fee is None and provided_spacing is None:
            return 3000, 60

        if (
            provided_fee is None
            and provided_spacing is not None
            and TICK_SPACINGS_TO_FEES.get(provided_spacing) is not None
        ):
            return TICK_SPACINGS_TO_FEES[provided_spacing], provided_spacing

        if (
            provided_fee is not None
            and provided_spacing is None
            and FEES_TO_TICK_SPACINGS.get(provided_fee) is not None
        ):
            return provided_fee, FEES_TO_TICK_SPACINGS[provided_fee]

        if provided_fee is not None and provided_spacing is not None:
            logger.warning(
                f"Tick spacing & Fee were both specified, but do not match typical values"
                f"\tFee: {provided_fee}, Tick Spacing: {provided_spacing}"
            )
            return provided_fee, provided_spacing

        raise UniswapV3Revert(
            "Nonstandard tick spacing or fee provided. Please provide a standard value, "
            "or both tick_spacing and fee when using nonstandard values"
        )

    @classmethod
    def get_next_sqrt_price_from_amount_0_rounding_up(
        cls,
        sqrt_price: int,
        liquidity: int,
        amount: int,
        add: bool,
    ) -> int:
        """
        Returns the next sqrt price given an amount of token 0

        :param sqrt_price:
        :param liquidity:
        :param amount:
        :param add:
        :return:
        """
        if amount == 0:
            return sqrt_price

        numerator_1 = liquidity << SQRT_RESOLUTION

        if add:
            if amount * sqrt_price <= UINT_256_MAX:
                denominator = numerator_1 + (amount * sqrt_price)
                if denominator >= numerator_1:
                    try:
                        return cls.full_math.mul_div_rounding_up(
                            numerator_1,
                            sqrt_price,
                            denominator,
                        )
                    except FullMathRevert as exc:
                        raise UniswapV3Revert from exc

            # uint160(UnsafeMath.divRoundingUp(numerator1, (numerator1 / sqrtPX96).add(amount)))
            return ceil(numerator_1 / ((numerator_1 / sqrt_price) + amount))
        if amount * sqrt_price >= UINT_256_MAX or numerator_1 <= amount * sqrt_price:
            raise UniswapV3Revert
        try:
            return_value = cls.full_math.mul_div_rounding_up(
                numerator_1,
                sqrt_price,
                numerator_1 - (amount * sqrt_price),
            )
        except FullMathRevert as exc:
            raise UniswapV3Revert from exc

        if return_value >= UINT_160_MAX:
            raise UniswapV3Revert
        return return_value

    @classmethod
    def get_next_sqrt_price_from_amount_1_rounding_down(
        cls,
        sqrt_price: int,
        liquidity: int,
        amount: int,
        add: bool,
    ):
        """
        Returns the next sqrt price given an amount of token 1

        :param sqrt_price:
        :param liquidity:
        :param amount:
        :param add:
        :return:
        """
        if add:
            try:
                quotient = cls.full_math.mul_div(
                    amount,
                    SQRT_Q96,
                    liquidity,
                )
            except FullMathRevert as exc:
                raise UniswapV3Revert from exc

            if sqrt_price + quotient >= UINT_160_MAX:
                raise UniswapV3Revert("UINT_160_MAX Overflow")
            return sqrt_price + quotient

        try:
            quotient = cls.full_math.mul_div_rounding_up(
                amount,
                SQRT_Q96,
                liquidity,
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
    ):
        """
        Returns the next sqrt price given an input amount of token 0 or token 1

        :param sqrt_price:
        :param liquidity:
        :param amount_in:
        :param zero_for_one:
        :return:
        """
        if sqrt_price <= 0 or liquidity <= 0:
            raise UniswapV3Revert("sqrt_price and liquidity must be greater than 0")

        return (
            cls.get_next_sqrt_price_from_amount_0_rounding_up(
                sqrt_price,
                liquidity,
                amount_in,
                True,
            )
            if zero_for_one
            else cls.get_next_sqrt_price_from_amount_1_rounding_down(
                sqrt_price,
                liquidity,
                amount_in,
                True,
            )
        )

    @classmethod
    def get_next_sqrt_price_from_output(
        cls,
        sqrt_price: int,
        liquidity: int,
        amount_out: int,
        zero_for_one: bool,
    ):
        """
        Returns the next sqrt price given an output amount of token 0 or token 1

        :param sqrt_price:
        :param liquidity:
        :param amount_out:
        :param zero_for_one:
        :return:
        """
        if sqrt_price <= 0 or liquidity <= 0:
            raise UniswapV3Revert("sqrt_price and liquidity must be greater than 0")

        return (
            cls.get_next_sqrt_price_from_amount_1_rounding_down(
                sqrt_price,
                liquidity,
                amount_out,
                False,
            )
            if zero_for_one
            else cls.get_next_sqrt_price_from_amount_0_rounding_up(
                sqrt_price,
                liquidity,
                amount_out,
                False,
            )
        )

    @classmethod
    def _get_amount_0_delta(
        cls,
        sqrt_price_a: int,
        sqrt_price_b: int,
        liquidity: int,
        round_up: bool,
    ):
        if sqrt_price_a > sqrt_price_b:
            sqrt_price_a, sqrt_price_b = sqrt_price_b, sqrt_price_a
        numerator_1, numerator_2 = (
            liquidity << SQRT_RESOLUTION,
            sqrt_price_b - sqrt_price_a,
        )
        if sqrt_price_a <= 0:
            raise UniswapV3Revert("sqrt_price_a must be greater than 0")
        un_rounded_value = Decimal(
            str(
                cls.full_math.mul_div_rounding_up(
                    numerator_1,
                    numerator_2,
                    sqrt_price_b,
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
    ) -> int:
        if sqrt_price_a > sqrt_price_b:
            sqrt_price_a, sqrt_price_b = sqrt_price_b, sqrt_price_a

        return (
            cls.full_math.mul_div_rounding_up(
                liquidity,
                sqrt_price_b - sqrt_price_a,
                SQRT_Q96,
            )
            if round_up
            else cls.full_math.mul_div(
                liquidity,
                sqrt_price_b - sqrt_price_a,
                SQRT_Q96,
            )
        )

    @classmethod
    def get_amount_0_delta(
        cls,
        sqrt_price_a: int,
        sqrt_price_b: int,
        liquidity: int,
    ) -> int:
        """
        Returns the amount of token 0 required to move from sqrt_price_a to sqrt_price_b

        :param sqrt_price_a:
        :param sqrt_price_b:
        :param liquidity:
        :return:
        """
        if liquidity < 0:
            return -1 * overflow_check(
                cls._get_amount_0_delta(
                    sqrt_price_a,
                    sqrt_price_b,
                    abs(liquidity),
                    False,
                ),
                UINT_256_MAX,
            )
        return overflow_check(
            cls._get_amount_0_delta(
                sqrt_price_a,
                sqrt_price_b,
                abs(liquidity),
                True,
            ),
            UINT_256_MAX,
        )

    @classmethod
    def get_amount_1_delta(
        cls,
        sqrt_price_a: int,
        sqrt_price_b: int,
        liquidity: int,
    ) -> int:
        """
        Returns the amount of token 1 required to move from sqrt_price_a to sqrt_price_b

        :param sqrt_price_a:
        :param sqrt_price_b:
        :param liquidity:
        :return:
        """
        if liquidity < 0:
            return -1 * overflow_check(
                cls._get_amount_1_delta(
                    sqrt_price_a,
                    sqrt_price_b,
                    abs(liquidity),
                    False,
                ),
                UINT_256_MAX,
            )
        return overflow_check(
            cls._get_amount_1_delta(
                sqrt_price_a,
                sqrt_price_b,
                abs(liquidity),
                True,
            ),
            UINT_256_MAX,
        )

    @classmethod
    def compute_swap_step(
        cls,
        sqrt_price_current: int,
        sqrt_price_target: int,
        liquidity: int,
        amount_remaining: int,
        fee_pips: int,
    ) -> SwapComputation:
        """
        Computes the next step in a swap.  Returns the next sqrt price, amount in, amount out, and fee amount.

        :param sqrt_price_current:
        :param sqrt_price_target:
        :param liquidity:
        :param amount_remaining:
        :param fee_pips:
        :return:
        """
        # pylint: disable=too-many-branches
        zero_for_one, exact_input = (
            sqrt_price_current >= sqrt_price_target,
            amount_remaining >= 0,
        )
        if exact_input:
            amount_remaining_less_fee = cls.full_math.mul_div(
                amount_remaining,
                1_000_000 - fee_pips,
                1_000_000,
            )
            if zero_for_one:
                amount_in = cls._get_amount_0_delta(
                    sqrt_price_target,
                    sqrt_price_current,
                    liquidity,
                    True,
                )
            else:
                amount_in = cls._get_amount_1_delta(
                    sqrt_price_current,
                    sqrt_price_target,
                    liquidity,
                    True,
                )

            if amount_remaining_less_fee >= amount_in:
                sqrt_price_next = sqrt_price_target
            else:
                sqrt_price_next = cls.get_next_sqrt_price_from_input(
                    sqrt_price_current,
                    liquidity,
                    amount_remaining_less_fee,
                    zero_for_one,
                )

        else:
            amount_out = (
                cls._get_amount_1_delta(
                    sqrt_price_target,
                    sqrt_price_current,
                    liquidity,
                    False,
                )
                if zero_for_one
                else cls._get_amount_0_delta(
                    sqrt_price_current,
                    sqrt_price_target,
                    liquidity,
                    False,
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
                )

        max_price_reached = sqrt_price_target == sqrt_price_next

        if zero_for_one:
            if max_price_reached and exact_input:
                pass
            else:
                amount_in = cls._get_amount_0_delta(
                    sqrt_price_next,
                    sqrt_price_current,
                    liquidity,
                    True,
                )

            if max_price_reached and not exact_input:
                pass
            else:
                amount_out = cls._get_amount_1_delta(
                    sqrt_price_next,
                    sqrt_price_current,
                    liquidity,
                    False,
                )

        else:
            if max_price_reached and exact_input:
                pass
            else:
                amount_in = cls._get_amount_1_delta(
                    sqrt_price_current,
                    sqrt_price_next,
                    liquidity,
                    True,
                )

            if max_price_reached and not exact_input:
                pass
            else:
                amount_out = cls._get_amount_0_delta(
                    sqrt_price_current,
                    sqrt_price_next,
                    liquidity,
                    False,
                )

        if not exact_input and amount_out > abs(amount_remaining):
            amount_out = abs(amount_remaining)

        if exact_input and sqrt_price_next != sqrt_price_target:
            fee_amount = amount_remaining - amount_in
        else:
            fee_amount = cls.full_math.mul_div_rounding_up(
                amount_in,
                fee_pips,
                1_000_000 - fee_pips,
            )

        return SwapComputation(
            sqrt_price_next=sqrt_price_next,
            amount_in=amount_in,
            amount_out=amount_out,
            fee_amount=fee_amount,
        )
