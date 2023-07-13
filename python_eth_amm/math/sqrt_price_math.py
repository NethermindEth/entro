from typing import Tuple

from eth_abi import encode
from eth_abi.exceptions import EncodingError

from python_eth_amm.exceptions import SqrtPriceMathRevert

from .base import ExactMathModule, load_contract_binary


class SqrtPriceMathModule(ExactMathModule):
    """
    Math module for calculating sqrt prices & liquidity amounts
    """

    X96_RESOLUTION = 96
    MAX_SQRT_RATIO = 1461446703485210103287273052203988822378723970342
    MIN_SQRT_RATIO = 4295128739
    SQRT_X96 = 2**96

    deploy_address = "0x3456345634563456345634563456345634563456"

    get_amount_0_delta_signature = bytes.fromhex("c932699b")
    get_amount_1_delta_signature = bytes.fromhex("00c11862")
    get_next_sqrt_price_from_amount_0_rounding_up_signature = bytes.fromhex("157f652f")
    get_next_sqrt_price_from_amount_1_rounding_down_signature = bytes.fromhex(
        "fb4de288"
    )
    get_next_sqrt_price_from_input_signature = bytes.fromhex("aa58276a")
    get_next_sqrt_price_from_output_signature = bytes.fromhex("fedf2b5f")

    def __new__(cls, factory, *args, **kwargs):  # pylint: disable=unused-argument
        cls.factory = factory
        return cls

    @classmethod
    def deploy_params(cls) -> Tuple[str, bytes]:
        """
        Deploy params for sqrt price math contract.  Returns deploy address and bytecode
        :return:
        """
        return cls.deploy_address, load_contract_binary("sqrt_price_math.bin")

    @classmethod
    def sqrt_prices_in_bounds(cls, sqrt_price: int) -> bool:
        """
        Check if sqrt price is greater than min_sqrt_ratio and less than max_sqrt_ratio
        :param sqrt_price:
        :return:
        """
        if cls.MIN_SQRT_RATIO <= sqrt_price <= cls.MAX_SQRT_RATIO:
            return True
        return False

    @classmethod
    def get_amount_0_delta(
        cls, sqrt_ratio_a: int, sqrt_ratio_b: int, liquidity: int, exact_rounding: bool
    ) -> int:
        """
        TODO
        :param sqrt_ratio_a:
        :param sqrt_ratio_b:
        :param liquidity:
        :param exact_rounding:
        :return:
        """
        if exact_rounding:
            try:
                payload = cls.get_amount_0_delta_signature + encode(
                    ["uint160", "uint160", "int128"],
                    [sqrt_ratio_a, sqrt_ratio_b, liquidity],
                )
            except EncodingError as exc:
                raise SqrtPriceMathRevert from exc

            result = cls.factory.call_evm_contract(
                cls.deploy_address, payload, SqrtPriceMathRevert
            )
            return int(result, 16)

        if not cls.sqrt_prices_in_bounds(sqrt_ratio_a) or not cls.sqrt_prices_in_bounds(
            sqrt_ratio_b
        ):
            raise SqrtPriceMathRevert("Sqrt Price input out of bounds")

        if sqrt_ratio_a > sqrt_ratio_b:
            sqrt_upper, sqrt_lower = sqrt_ratio_a, sqrt_ratio_b
        else:
            sqrt_upper, sqrt_lower = sqrt_ratio_b, sqrt_ratio_a

        return int(
            (liquidity * (sqrt_upper - sqrt_lower))
            / (sqrt_upper * sqrt_lower / cls.SQRT_X96)
        )

    @classmethod
    def get_amount_1_delta(
        cls, sqrt_ratio_a: int, sqrt_ratio_b: int, liquidity: int, exact_rounding: bool
    ) -> int:
        """
        TODO
        :param sqrt_ratio_a:
        :param sqrt_ratio_b:
        :param liquidity:
        :param exact_rounding:
        :return:
        """
        if exact_rounding:
            try:
                payload = cls.get_amount_1_delta_signature + encode(
                    ["uint160", "uint160", "int128"],
                    [sqrt_ratio_a, sqrt_ratio_b, liquidity],
                )
            except EncodingError as exc:
                raise SqrtPriceMathRevert from exc

            result = cls.factory.call_evm_contract(
                cls.deploy_address, payload, SqrtPriceMathRevert
            )
            return int(result, 16)

        if not cls.sqrt_prices_in_bounds(sqrt_ratio_a) or not cls.sqrt_prices_in_bounds(
            sqrt_ratio_b
        ):
            raise SqrtPriceMathRevert("Sqrt Price input out of bounds")

        if sqrt_ratio_a > sqrt_ratio_b:
            sqrt_upper, sqrt_lower = sqrt_ratio_a, sqrt_ratio_b
        else:
            sqrt_upper, sqrt_lower = sqrt_ratio_b, sqrt_ratio_a

        return int(liquidity * (sqrt_upper - sqrt_lower) / cls.SQRT_X96)

    @classmethod
    def get_next_sqrt_price_from_amount_0_rounding_up(
        cls,
        sqrt_price: int,
        liquidity: int,
        amount: int,
        add: bool,
        exact_rounding: bool,
    ) -> int:
        """
        TODO
        :param sqrt_price:
        :param liquidity:
        :param amount:
        :param add:
        :param exact_rounding:
        :return:
        """
        if exact_rounding:
            try:
                payload = (
                    cls.get_next_sqrt_price_from_amount_0_rounding_up_signature
                    + encode(
                        ["uint160", "uint128", "uint256", "bool"],
                        [sqrt_price, liquidity, amount, add],
                    )
                )
            except EncodingError as exc:
                raise SqrtPriceMathRevert from exc

            result = cls.factory.call_evm_contract(
                cls.deploy_address, payload, SqrtPriceMathRevert
            )
            return int(result, 16)

        if not cls.sqrt_prices_in_bounds(sqrt_price):
            raise SqrtPriceMathRevert("Sqrt Price input out of bounds")

        sqrt_price_next = int(
            (liquidity * sqrt_price)
            / (liquidity + ((1 if add else -1) * (amount * sqrt_price)) / cls.SQRT_X96)
        )

        if not cls.sqrt_prices_in_bounds(sqrt_price_next):
            raise SqrtPriceMathRevert("Sqrt Price output out of bounds")

        return sqrt_price_next

    @classmethod
    def get_next_sqrt_price_from_amount_1_rounding_down(
        cls,
        sqrt_price: int,
        liquidity: int,
        amount: int,
        add: bool,
        exact_rounding: bool,
    ) -> int:
        """

        :param sqrt_price:
        :param liquidity:
        :param amount:
        :param add:
        :param exact_rounding:
        :return:
        """
        if exact_rounding:
            try:
                payload = (
                    cls.get_next_sqrt_price_from_amount_1_rounding_down_signature
                    + encode(
                        ["uint160", "uint128", "uint256", "bool"],
                        [sqrt_price, liquidity, amount, add],
                    )
                )
            except EncodingError as exc:
                raise SqrtPriceMathRevert from exc

            result = cls.factory.call_evm_contract(
                cls.deploy_address, payload, SqrtPriceMathRevert
            )
            return int(result, 16)

        if not cls.sqrt_prices_in_bounds(sqrt_price):
            raise SqrtPriceMathRevert("Sqrt Price input out of bounds")

        sqrt_price_next = int(
            sqrt_price + (1 if add else -1) * (amount * cls.SQRT_X96 / liquidity)
        )

        if not cls.sqrt_prices_in_bounds(sqrt_price_next):
            raise SqrtPriceMathRevert("Sqrt Price output out of bounds")

        return sqrt_price_next

    @classmethod
    def get_next_sqrt_price_from_input(
        cls,
        sqrt_price: int,
        liquidity: int,
        amount_in: int,
        zero_for_one: bool,
        exact_rounding: bool,
    ) -> int:
        """
        TODO
        :param sqrt_price:
        :param liquidity:
        :param amount_in:
        :param zero_for_one:
        :param exact_rounding:
        :return:
        """
        if exact_rounding:
            try:
                payload = cls.get_next_sqrt_price_from_input_signature + encode(
                    ["uint160", "uint128", "uint256", "bool"],
                    [sqrt_price, liquidity, amount_in, zero_for_one],
                )
            except EncodingError as exc:
                raise SqrtPriceMathRevert from exc

            result = cls.factory.call_evm_contract(
                cls.deploy_address, payload, SqrtPriceMathRevert
            )
            return int(result, 16)

        if not cls.sqrt_prices_in_bounds(sqrt_price):
            raise SqrtPriceMathRevert("Sqrt Price input out of bounds")

        if zero_for_one:
            return cls.get_next_sqrt_price_from_amount_0_rounding_up(
                sqrt_price, liquidity, amount_in, True, False
            )
        return cls.get_next_sqrt_price_from_amount_1_rounding_down(
            sqrt_price, liquidity, amount_in, True, False
        )

    @classmethod
    def get_next_sqrt_price_from_output(
        cls,
        sqrt_price: int,
        liquidity: int,
        amount_in: int,
        zero_for_one: bool,
        exact_rounding: bool,
    ) -> int:
        """
        TODO
        :param sqrt_price:
        :param liquidity:
        :param amount_in:
        :param zero_for_one:
        :param exact_rounding:
        :return:
        """
        if exact_rounding:
            try:
                payload = cls.get_next_sqrt_price_from_output_signature + encode(
                    ["uint160", "uint128", "uint256", "bool"],
                    [sqrt_price, liquidity, amount_in, zero_for_one],
                )
            except EncodingError as exc:
                raise SqrtPriceMathRevert from exc

            result = cls.factory.call_evm_contract(
                cls.deploy_address, payload, SqrtPriceMathRevert
            )
            return int(result, 16)

        if not cls.sqrt_prices_in_bounds(sqrt_price):
            raise SqrtPriceMathRevert("Sqrt Price input out of bounds")

        if zero_for_one:
            return cls.get_next_sqrt_price_from_amount_1_rounding_down(
                sqrt_price, liquidity, amount_in, False, False
            )

        return cls.get_next_sqrt_price_from_amount_0_rounding_up(
            sqrt_price, liquidity, amount_in, False, False
        )
