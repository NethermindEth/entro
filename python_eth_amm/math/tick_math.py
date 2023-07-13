import math
from math import sqrt
from typing import Tuple

from eth_abi import decode, encode
from eth_abi.exceptions import EncodingError

from python_eth_amm.exceptions import TickMathRevert

from .base import ExactMathModule, load_contract_binary

TICK_MATH_ABI = [
    {
        "inputs": [{"internalType": "int24", "name": "tick", "type": "int24"}],
        "name": "getSqrtRatioAtTick",
        "outputs": [
            {"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"}
        ],
        "stateMutability": "pure",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"}
        ],
        "name": "getTickAtSqrtRatio",
        "outputs": [{"internalType": "int24", "name": "tick", "type": "int24"}],
        "stateMutability": "pure",
        "type": "function",
    },
]


class TickMathModule(ExactMathModule):
    """
    Module for computing sqrt prices & ticks for Uniswap V3 Pools
    """

    deploy_address = "0x8282828282828282828282828282828282828282"
    get_tick_at_ratio_signature = bytes.fromhex("4f76c058")
    get_ratio_at_tick_signature = bytes.fromhex("986cfba3")
    MAX_TICK = 887272
    MIN_TICK = -MAX_TICK
    MAX_SQRT_RATIO = 1461446703485210103287273052203988822378723970342
    MIN_SQRT_RATIO = 4295128739

    def __new__(cls, factory):
        cls.factory = factory
        return cls

    @classmethod
    def deploy_params(cls) -> Tuple[str, bytes]:
        return cls.deploy_address, load_contract_binary("tick_math.bin")

    @classmethod
    def get_sqrt_ratio_at_tick(cls, tick: int, exact_rounding: bool = False) -> int:
        """
        Returns the sqrt ratio as a Q64.96 fixed point number corresponding to the given tick.
        Computes the following formula: sqrt(1.0001^tick) * 2^96
        :param int tick: Tick to get sqrt ratio at.
        :param bool exact_rounding: whether to use exact math.  Defaults to False
        :return: sqrt_ratio encoded as a Q64.96 fixed point number
        """
        if exact_rounding:
            try:
                payload = cls.get_ratio_at_tick_signature + encode(["int24"], [tick])

            except EncodingError as error:
                raise TickMathRevert from error

            result = cls.factory.call_evm_contract(
                cls.deploy_address, payload, TickMathRevert
            )
            return int(result, 16)

        if tick > cls.MAX_TICK or tick < cls.MIN_TICK:
            raise TickMathRevert("Tick outside of min/max bounds.  Tick: {tick}")
        return int(sqrt(1.0001**tick) * 2**96)

    @classmethod
    def get_tick_at_sqrt_ratio(
        cls, sqrt_ratio: int, exact_rounding: bool = False
    ) -> int:
        """

        :param sqrt_ratio: Sqrt(token_0/token_1) price encoded as Q64.96 fixed point number
        :param exact_rounding: whether to use exact math.  Defaults to False
        :return: tick corresponding to the given sqrt ratio
        """
        if exact_rounding:
            try:
                payload = cls.get_tick_at_ratio_signature + encode(
                    ["uint160"], [sqrt_ratio]
                )

            except EncodingError as error:
                raise TickMathRevert from error

            result = cls.factory.call_evm_contract(
                cls.deploy_address, payload, TickMathRevert
            )

            # pylint: disable=unsubscriptable-object
            return decode(["int24"], bytes.fromhex(result))[0]

        if sqrt_ratio > cls.MAX_SQRT_RATIO or sqrt_ratio < cls.MIN_SQRT_RATIO:
            raise TickMathRevert(
                "Sqrt ratio outside of min/max bounds.  Sqrt ratio: {sqrt_ratio}"
            )
        return int(2 * math.log(sqrt_ratio / 2**96, 1.0001))
