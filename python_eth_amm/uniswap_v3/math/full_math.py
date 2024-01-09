from math import ceil, floor

from eth_abi import encode
from eth_abi.exceptions import EncodingError

from python_eth_amm.exceptions import FullMathRevert

from .shared import UINT_256_MAX, call_evm_contract, load_contract_binary

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


class FullMathModule:
    """Math Module for computing (a * b / denominator) with uint256 behavior"""

    deploy_address = "0x3939303530383238313131383230333931353038"
    evm_instance = None
    exact_math: bool = False

    mul_div_signature = bytes.fromhex("aa9a0912")
    mul_div_round_up_signature = bytes.fromhex("0af8b27f")

    @classmethod
    def depoly_exact_math_mode(cls, evm_instance):
        """
        Deploys the FullMath contract to the EVM instance at `deploy_address`
        :param evm_instance: pyREVM EVM() instance
        """

        # pylint: disable=import-outside-toplevel,no-name-in-module,import-error
        from pyrevm import AccountInfo  # type: ignore[attr-defined]

        # pylint: enable=import-outside-toplevel,no-name-in-module,import-error

        cls.exact_math = True
        cls.evm_instance = evm_instance
        cls.evm_instance.insert_account_info(
            cls.deploy_address, AccountInfo(code=load_contract_binary("full_math.bin"))
        )

    @classmethod
    def mul_div(cls, numerator_1: int, numerator_2: int, denominator: int) -> int:
        """
        Computes the result of (numerator_1 * numerator_2) / denominator.
        Returns value as uint256, rounded down
        """
        if cls.exact_math:
            try:
                payload = cls.mul_div_signature + encode(
                    ["uint256", "uint256", "uint256"],
                    [numerator_1, numerator_2, denominator],
                )
            except EncodingError as exc:
                raise FullMathRevert from exc

            result = call_evm_contract(
                cls.evm_instance, cls.deploy_address, payload, FullMathRevert
            )

            return int.from_bytes(result, "big")

        if denominator == 0:
            raise FullMathRevert("Division By Zero")

        return_val = floor((numerator_1 * numerator_2) / denominator)
        if return_val > UINT_256_MAX:
            raise FullMathRevert(f"Value {return_val} overflows UINT256")
        return int(return_val)

    @classmethod
    def mul_div_rounding_up(
        cls, numerator_1: int, numerator_2: int, denominator: int
    ) -> int:
        """
        Computes the result of (numerator_1 * numerator_2) / denominator.
        Returns value as uint256 rounded up
        """
        if cls.exact_math:
            try:
                payload = cls.mul_div_round_up_signature + encode(
                    ["uint256", "uint256", "uint256"],
                    [numerator_1, numerator_2, denominator],
                )
            except EncodingError as exc:
                raise FullMathRevert from exc

            exact_result = call_evm_contract(
                cls.evm_instance, cls.deploy_address, payload, FullMathRevert
            )
            return int.from_bytes(exact_result, "big")

        if denominator == 0:
            raise FullMathRevert("Division By Zero")

        approx_result = ceil((numerator_1 * numerator_2) / denominator)

        if approx_result >= UINT_256_MAX:
            raise FullMathRevert("Mul Div Rounding Up Overflows when Rounding")

        return approx_result
