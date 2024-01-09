import json
import random
from typing import Any, Literal

from eth_typing import ChecksumAddress
from eth_utils import to_checksum_address
from hexbytes import HexBytes


def to_hex(data: str | bytes | HexBytes) -> str:
    """Converts binary data to 0x prefixed hex string"""
    if isinstance(data, str):
        return data if data.startswith("0x") else "0x" + data
    if isinstance(data, bytes):
        return "0x" + data.hex()
    if isinstance(data, HexBytes):
        return data.hex()
    raise TypeError(f"Invalid type for to_hex:  {type(data)}")


def json_encode_dictionary(data: dict[str, Any]):
    """
    Encodes a dictionary to json, recursively converting bytes to hex

    :param data:
    :return:
    """
    hex_dict = hex_encode_objects(data)
    return json.dumps(hex_dict)


def hex_encode_objects(data):
    """
    Recursively converts bytes to hex

    :param data:
    :return:
    """
    if isinstance(data, dict):
        return {key: hex_encode_objects(value) for key, value in data.items()}
    if isinstance(data, list):
        return [hex_encode_objects(item) for item in data]
    if isinstance(data, (bytes, HexBytes)):
        return to_hex(data)
    return data


def to_bytes(data: str | HexBytes | bytes) -> bytes:
    """
    Converts hex string to bytes

    :param data:
    :return:
    """
    if isinstance(data, str):
        return bytes.fromhex(data.replace("0x", ""))
    if isinstance(data, (HexBytes, bytes)):
        return data
    raise TypeError(f"Invalid type for to_bytes: {type(data)}")


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


def maybe_hex_to_int(value: str | bytes | HexBytes | int) -> int:
    """
    Converts 0x prefixed hex strings to int, converts bytes to ints with big endian encoding, and returns
    ints as is

    :param value:
    :return:
    """
    if isinstance(value, str):
        return int(value, 16)
    if isinstance(value, bytes):
        return int.from_bytes(value, "big")
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
