import logging
import traceback
from typing import Any

from eth_abi import decode as eth_abi_decode
from eth_abi.exceptions import InsufficientDataBytes, NonEmptyPaddingBytes
from web3.types import ABI, ABIEvent, ABIEventParams, ABIFunction, ABIFunctionParams

# Redefinitions from eth_utils with correct typing

root_logger = logging.getLogger("nethermind")
logger = root_logger.getChild("entro").getChild("decoding")


def abi_to_signature(abi: ABIFunction | ABIEvent) -> str:
    """
    Converts ABI to signature.

    >>> from nethermind.entro.decoding.utils import abi_to_signature, ABIFunction
    >>> function = ABIFunction(
    ...
    ...)
    >>> abi_to_signature(function)
    'transferFrom(address,uint256)'

    """
    collapsed = [collapse_if_tuple(abi_input) for abi_input in abi.get("inputs", [])]
    return f"{abi['name']}({','.join(collapsed)})"


def collapse_if_tuple(abi_params: ABIFunctionParams | ABIEventParams) -> str:
    """
    Converts a tuple from a dict to a parenthesized list of its types.

    >>> from eth_utils.abi import collapse_if_tuple
    >>> collapse_if_tuple(
    ...     {
    ...         'components': [
    ...             {'name': 'anAddress', 'type': 'address'},
    ...             {'name': 'anInt', 'type': 'uint256'},
    ...             {'name': 'someBytes', 'type': 'bytes'},
    ...         ],
    ...         'type': 'tuple',
    ...     }
    ... )
    '(address,uint256,bytes)'
    """

    typ = abi_params["type"]
    if not isinstance(typ, str):
        raise TypeError(f"The 'type' must be a string, but got {typ} of type {type(typ)}")

    if not typ.startswith("tuple"):
        return typ

    delimited = ",".join(collapse_if_tuple(c) for c in abi_params["components"])  # type: ignore
    # Whatever comes after "tuple" is the array dims.  The ABI spec states that
    # this will have the form "", "[]", or "[k]".
    array_dim = typ[5:]
    collapsed = f"({delimited}){array_dim}"

    return collapsed


def abi_signature_to_name(signature: str) -> str:
    """
    Removes types from ABI signature

    >>> from nethermind.entro.decoding.utils import abi_signature_to_name
    >>> abi_signature_to_name("transferFrom(address,uint256)")
    'transferFrom'
    >>> abi_signature_to_name("swap(address,address,uint256,uint256,int128)")
    'swap'
    """

    return signature[: signature.find("(")]


def filter_functions(contract_abi: ABI) -> list[ABIFunction]:
    """Filters out all non-function ABIs"""
    return [abi for abi in contract_abi if abi["type"] == "function"]


def filter_events(contract_abi: ABI) -> list[ABIEvent]:
    """Filters out all non-event ABIs"""
    return [abi for abi in contract_abi if abi["type"] == "event"]


def signature_to_name(function_sig: str) -> str:
    """
    Removes types from function signature

    :param function_sig:
    :return:
    """
    index = function_sig.find("(")
    if index != -1:
        return function_sig[:index]
    return function_sig


def decode_evm_abi_from_types(types: list[str], data: bytes | bytearray) -> tuple[Any, ...] | None:
    """
    Decodes ABI data from types and data bytes.  Properly Handles various decoding errors by logging and
    returning none.

    :param types:
    :param data:
    :return:
    """
    try:
        return eth_abi_decode(types, data)
    except InsufficientDataBytes:
        logger.debug(f"Insufficient data bytes while decoding {data.hex()} for types {types}")
        return None
    except NonEmptyPaddingBytes:
        logger.debug(f"Non-empty padding bytes while decoding {data.hex()} for types {types}")
        return None
    except OverflowError:
        logger.debug(f"Overflow error while decoding {data.hex()} for types {types}")
        return None
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error(
            f"Unknown error while decoding {data.hex()} for types {types}: "
            f"{traceback.format_exception(type(e), e, e.__traceback__)}"
        )
        return None
