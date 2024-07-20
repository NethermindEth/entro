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


def camel_to_snake(name: str) -> str:
    """
    Converts camel case to snake case
    :param name: name to convert
    :return: snake case name
    """
    out_string = ""
    last_char = name[0]
    for char in name[1:]:
        if char.isupper():
            if last_char.islower() or last_char.isnumeric():
                out_string += last_char + "_"
            else:
                out_string += last_char.lower()
        elif char.isnumeric():
            if last_char.isalpha():
                out_string += last_char.lower() + "_"
            else:
                out_string += last_char.lower()
        else:
            out_string += last_char.lower()
        last_char = char

    out_string += last_char.lower()
    return out_string


def pprint_list(write_array: list[str], term_width: int) -> list[str]:
    """
    Prints an array of strings to the console, wrapping lines with a max width of term_width

    :param write_array:
    :param term_width:
    :return:
    """
    current_line, output = "", []
    for write_val in write_array:
        if len(current_line) + len(write_val) + 1 > term_width:
            output.append(current_line)
            current_line = ""
        current_line += f"'{write_val}', "
    output.append(current_line)
    return output
