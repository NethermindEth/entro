import os
from abc import abstractmethod
from typing import Any, Tuple

SOLIDITY_SRC_DIR = os.path.dirname(__file__) + "/solidity_source/"

"""
Base Classes for Math Modules
"""


def load_contract_binary(file_name: str) -> bytes:
    """
    Loads a contract binary from a file in the solidity_source directory
    :param file_name: file name of the contract binary source
    :return: deployed contract bytecode
    """
    with open(SOLIDITY_SRC_DIR + file_name, "r") as read_file:
        contract_hex = read_file.readline()
        return bytes.fromhex(contract_hex)


class ExactMathModule:
    """
    Abstract class for representing exact math modules that can be deployed to the EVM.
    """

    factory: Any
    deploy_address: str

    @classmethod
    @abstractmethod
    def deploy_params(cls) -> Tuple[str, bytes]:
        """Returns the contract address and bytecode for the exact math module"""


class TranslatedMathModule:
    """
    Abstract class for representing math modules that are implemented in Python without EVM bindings
    """

    factory: Any
