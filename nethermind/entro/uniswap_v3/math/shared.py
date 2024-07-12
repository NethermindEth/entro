import os
from dataclasses import dataclass
from decimal import Decimal
from typing import Type

from nethermind.entro.exceptions import UniswapV3Revert

SOLIDITY_SRC_DIR = os.path.dirname(__file__) + "/solidity_source/"

MAX_TICK = 887272
MIN_TICK = -MAX_TICK
MAX_SQRT_RATIO = 1461446703485210103287273052203988822378723970342
MIN_SQRT_RATIO = 4295128739
X96_RESOLUTION = 96
SQRT_X96 = 2**96
SQRT_RESOLUTION = 96
SQRT_Q96 = 0x1000000000000000000000000
Q128 = 0x100000000000000000000000000000000
UINT_128_MAX = 2**128 - 1
UINT_160_MAX = 2**160 - 1
UINT_256_MAX = 2**256 - 1

FEES_TO_TICK_SPACINGS = {
    100: 1,
    500: 10,
    3000: 60,
    10000: 200,
}

TICK_SPACINGS_TO_FEES = {v: k for k, v in FEES_TO_TICK_SPACINGS.items()}


@dataclass(slots=True)
class SwapComputation:
    """Model to store the results of a swap computation"""

    sqrt_price_next: int
    amount_in: int
    amount_out: int
    fee_amount: int


def load_contract_binary(file_name: str) -> bytes:
    """
    Loads a contract binary from a file in the solidity_source directory
    :param file_name: file name of the contract binary source
    :return: deployed contract bytecode
    """
    with open(SOLIDITY_SRC_DIR + file_name, "r") as read_file:
        contract_hex = read_file.readline()
        return bytes.fromhex(contract_hex)


def call_evm_contract(
    evm_instance,
    to_address: str,
    data: bytes,
    exception_class: Type[Exception] | None,
) -> list[int]:
    """
    Internal Method used during exact math mode.  Contracts are deployed to a Rust EVM implementation,
    and can be called to generate math results identical to the Solidity implementation.
    Is only available if exact_math=True is passed to the factory constructor, and the pyrevm package is installed.

    :param evm_instance: pyREVM Instance to call
    :param str to_address: deployment address of the contract
    :param bytes data: call data to pass to EVM
    :param exception_class: Exception to raise if EVM call fails.  Defaults to RuntimeError

    :return: Response bytes formatted as HexString
    """
    try:
        tx_result = evm_instance.call_raw(
            caller="0x0123456789012345678901234567890123456789",
            to=to_address,
            data=list(data),
        )
    except RuntimeError:
        raise exception_class if exception_class else RuntimeError  # pylint: disable=raise-missing-from
    return tx_result


def input_check(tick: int | None = None, sqrt_price: float | None = None):
    """
    Checks that tick and sqrt_price are within MIN and MAX values.
    Raises UniswapV3Revert if invalid values are detected.

    :param tick:
    :param sqrt_price:
    :return:
    """
    if tick:
        if tick > MAX_TICK or tick < MIN_TICK:
            raise UniswapV3Revert(f"Tick Index out of Bounds: {tick}")
    if sqrt_price:
        if sqrt_price < MIN_SQRT_RATIO or sqrt_price > MAX_SQRT_RATIO:
            raise UniswapV3Revert(f"Square Root Price Ration out of Bounds: {sqrt_price}")


def check_ticks(cls, tick_lower: int, tick_upper: int):  # pylint: disable=unused-argument
    """
    Checks that ticks are within MIN and MAX ticks.  Raises UniswapV3Revert if invalid ticks are detected.

    :param tick_lower:
    :param tick_upper:
    :return:
    """
    if tick_lower > tick_upper:
        raise UniswapV3Revert("tick_lower cannot be larger than tick_upper")
    if tick_lower < MIN_TICK:
        raise UniswapV3Revert("tick_lower must be greater than MIN_TICK")
    if tick_upper > MAX_TICK:
        raise UniswapV3Revert("tick_upper must be less than MAX_TICK")


def check_sqrt_price(cls, sqrt_price: int):  # pylint: disable=unused-argument
    """
    Checks that sqrt_price is within MIN and MAX sqrt_price.  Raises UniswapV3Revert if invalid sqrt_price is detected.

    :param sqrt_price:
    :return:
    """
    if not MIN_SQRT_RATIO < sqrt_price < MAX_SQRT_RATIO:
        raise UniswapV3Revert("sqrt_price must be between MIN_SQRT_RATIO and MAX_SQRT_RATIO")


def get_max_liquidity_per_tick(cls, tick_spacing: int) -> int:  # pylint: disable=unused-argument
    """
    Returns the maximum liquidity per tick.  This is calculated by dividing the UINT_128_MAX by the number of ticks
    that can exist in the range of ticks for a given tick spacing.

    :param tick_spacing:
    :return:
    """
    if tick_spacing == 10:
        return 1917569901783203986719870431555990
    if tick_spacing == 60:
        return 11505743598341114571880798222544994
    if tick_spacing == 200:
        return 38350317471085141830651933667504588

    max_tick = MAX_TICK - MAX_TICK % tick_spacing

    number_of_ticks = int((max_tick * 2) / tick_spacing) + 1
    return int(Decimal(UINT_128_MAX) / Decimal(number_of_ticks))


def overflow_check(number, max_value):
    """
    Checks that a number is less than a max value.  Raises UniswapV3Revert if the number is greater than the max value.

    :param number:
    :param max_value:
    :return:
    """
    if number >= max_value:
        raise UniswapV3Revert(f"{number} Overflowed Max Value of: {max_value}")

    return number
