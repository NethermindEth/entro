import random
from typing import Literal

from eth_typing import ChecksumAddress
from eth_utils import to_checksum_address


def random_address() -> ChecksumAddress:
    """
    Generate a random 20 byte ChecksumAddress
    :return: ChecksumAddress
    """
    return to_checksum_address(random.randbytes(20).hex())


def uint_over_under_flow(value: int, precision: Literal[128, 160, 256]) -> int:
    """
    Handle uint over/underflow.  If value exceeds the max size of the uint, the value will overflow
    and start back at 0.  If value is less than 0, the value will underflow and start back at the max
    :param value: Number to check
    :param precision: bits of precision
    :return: within range uint
    """
    if value < 0:
        return value + (2**precision)
    if value >= 2**precision:
        return value - (2**precision)
    return value
