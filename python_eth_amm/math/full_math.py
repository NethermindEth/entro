from math import ceil, floor
from typing import Tuple

from eth_abi import encode
from eth_abi.exceptions import EncodingError

from python_eth_amm.exceptions import FullMathRevert

from .base import ExactMathModule, load_contract_binary

UINT_256_MAX = (2**256) - 1

FULL_MATH_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "a", "type": "uint256"},
            {"internalType": "uint256", "name": "b", "type": "uint256"},
            {"internalType": "uint256", "name": "denominator", "type": "uint256"},
        ],
        "name": "mulDiv",
        "outputs": [{"internalType": "uint256", "name": "result", "type": "uint256"}],
        "stateMutability": "pure",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "a", "type": "uint256"},
            {"internalType": "uint256", "name": "b", "type": "uint256"},
            {"internalType": "uint256", "name": "denominator", "type": "uint256"},
        ],
        "name": "mulDivRoundingUp",
        "outputs": [{"internalType": "uint256", "name": "result", "type": "uint256"}],
        "stateMutability": "pure",
        "type": "function",
    },
]


class FullMathModule(ExactMathModule):
    """Math Module for computing (a * b / denominator) with uint256 behavior"""

    deploy_address = "0x3939303530383238313131383230333931353038"
    mul_div_signature = bytes.fromhex("aa9a0912")
    mul_div_round_up_signature = bytes.fromhex("0af8b27f")

    def __new__(cls, factory):
        cls.factory = factory
        return cls

    @classmethod
    def deploy_params(cls) -> Tuple[str, bytes]:
        return cls.deploy_address, load_contract_binary("full_math.bin")

    @classmethod
    def mul_div(
        cls, numerator_1: int, numerator_2: int, denominator: int, exact_rounding: bool
    ) -> int:
        """
        Computes the result of (numerator_1 * numerator_2) / denominator.
        Returns value as uint256, rounded down
        """
        if exact_rounding:
            try:
                payload = cls.mul_div_signature + encode(
                    ["uint256", "uint256", "uint256"],
                    [numerator_1, numerator_2, denominator],
                )
            except EncodingError as exc:
                raise FullMathRevert from exc

            result = cls.factory.call_evm_contract(
                cls.deploy_address, payload, FullMathRevert
            )
            return int(result, 16)

        if denominator == 0:
            raise FullMathRevert("Division By Zero")

        return_val = floor((numerator_1 * numerator_2) / denominator)
        if return_val > UINT_256_MAX:
            raise FullMathRevert(f"Value {return_val} overflows UINT256")
        return int(return_val)

    @classmethod
    def mul_div_rounding_up(
        cls, numerator_1: int, numerator_2: int, denominator: int, exact_rounding: bool
    ) -> int:
        """
        Computes the result of (numerator_1 * numerator_2) / denominator.
        Returns value as uint256 rounded up
        """
        if exact_rounding:
            try:
                payload = cls.mul_div_round_up_signature + encode(
                    ["uint256", "uint256", "uint256"],
                    [numerator_1, numerator_2, denominator],
                )
            except EncodingError as exc:
                raise FullMathRevert from exc

            result = cls.factory.call_evm_contract(
                cls.deploy_address, payload, FullMathRevert
            )
            return int(result, 16)

        if denominator == 0:
            raise FullMathRevert("Division By Zero")

        result = ceil((numerator_1 * numerator_2) / denominator)

        if result >= UINT_256_MAX:
            raise FullMathRevert("Mul Div Rounding Up Overflows when Rounding")

        return result
