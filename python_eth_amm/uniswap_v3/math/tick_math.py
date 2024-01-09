import math
from math import sqrt

from eth_abi import decode, encode
from eth_abi.exceptions import EncodingError

from python_eth_amm.exceptions import TickMathRevert

from .shared import (
    MAX_SQRT_RATIO,
    MAX_TICK,
    MIN_SQRT_RATIO,
    MIN_TICK,
    call_evm_contract,
    load_contract_binary,
)

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


class TickMathModule:
    """
    Module for computing sqrt prices & ticks for Uniswap V3 Pools
    """

    deploy_address = "0x8282828282828282828282828282828282828282"
    evm_instance = None
    exact_math: bool = False

    get_tick_at_ratio_signature = bytes.fromhex("4f76c058")
    get_ratio_at_tick_signature = bytes.fromhex("986cfba3")

    @classmethod
    def depoly_exact_math_mode(cls, evm_instance):
        """
        Deploys the TickMath contract to the EVM instance at `deploy_address`

        :param evm_instance: pyREVM EVM() instance
        """
        # pylint: disable=import-outside-toplevel,no-name-in-module,import-error
        from pyrevm import AccountInfo  # type: ignore[attr-defined]

        # pylint: enable=import-outside-toplevel,no-name-in-module,import-error

        cls.exact_math = True
        cls.evm_instance = evm_instance
        cls.evm_instance.insert_account_info(
            cls.deploy_address, AccountInfo(code=load_contract_binary("tick_math.bin"))
        )

    @classmethod
    def get_sqrt_ratio_at_tick(cls, tick: int) -> int:
        """
        Returns the sqrt ratio as a Q64.96 fixed point number corresponding to the given tick.
        Computes the following formula: sqrt(1.0001^tick) * 2^96
        :param int tick: Tick to get sqrt ratio at.
        :return: sqrt_ratio encoded as a Q64.96 fixed point number
        """
        if cls.exact_math:
            try:
                payload = cls.get_ratio_at_tick_signature + encode(["int24"], [tick])

            except EncodingError as error:
                raise TickMathRevert from error

            result = call_evm_contract(
                cls.evm_instance, cls.deploy_address, payload, TickMathRevert
            )

            return int.from_bytes(result, "big")

        if tick > MAX_TICK or tick < MIN_TICK:
            raise TickMathRevert("Tick outside of min/max bounds.  Tick: {tick}")
        return int(sqrt(1.0001**tick) * 2**96)

    @classmethod
    def get_tick_at_sqrt_ratio(cls, sqrt_ratio: int) -> int:
        """

        :param sqrt_ratio: Sqrt(token_0/token_1) price encoded as Q64.96 fixed point number

        :return: tick corresponding to the given sqrt ratio
        """
        if cls.exact_math:
            try:
                payload = cls.get_tick_at_ratio_signature + encode(
                    ["uint160"], [sqrt_ratio]
                )

            except EncodingError as error:
                raise TickMathRevert from error

            result = call_evm_contract(
                cls.evm_instance, cls.deploy_address, payload, TickMathRevert
            )

            # pylint: disable=unsubscriptable-object
            return decode(["int24"], bytes(result))[0]

        if sqrt_ratio > MAX_SQRT_RATIO or sqrt_ratio < MIN_SQRT_RATIO:
            raise TickMathRevert(
                "Sqrt ratio outside of min/max bounds.  Sqrt ratio: {sqrt_ratio}"
            )
        return int(2 * math.log(sqrt_ratio / 2**96, 1.0001))
