import json
from pathlib import Path
from typing import Any, Dict, Optional, Union

from eth_typing import ChecksumAddress
from eth_utils import is_checksum_address, to_checksum_address
from pydantic import BaseModel
from web3 import Web3


class ERC20Token(BaseModel):
    """
    Class for representing ERC20 Tokens.  Can be initialized from on-chain token, and will query
    token constants from contract.

    Can be used to convert raw token amounts into human-readable amounts.
    """

    name: str
    """
        UTF-8 Name of the token from Token Contract
    """

    symbol: str
    """
        Token Symbol from Contract
    """

    decimals: int
    """
        Number of decimals from Token Contract
    """

    address: ChecksumAddress
    """
        Checksum Address of the Token Contract
    """

    contract: Any
    """
        Returns :class:`~web3.eth.Contract if token was initialized from on-chain token`
    """

    @classmethod
    def from_chain(
        cls,
        w3: Web3,  # pylint: disable=invalid-name
        token_address: Union[ChecksumAddress, str],
    ) -> "ERC20Token":
        """
        Initialize ERC20Token from on-chain token address.  Fetches token name, symbol, and decimals from contract.
        If token_address is invalid, raises ___

        :param w3:
            :class:`~web3.Web3` RPC connection to EVM node
        :param token_address:
            hex address of ERC20 token contract
        :return: :class:`~python_eth_amm.base.token.ERC20Token`
        """
        if not is_checksum_address(token_address):
            token_address = to_checksum_address(token_address)

        token_contract = w3.eth.contract(token_address, abi=cls.get_abi())
        return ERC20Token(
            name=token_contract.functions.name().call(),
            symbol=token_contract.functions.symbol().call(),
            decimals=token_contract.functions.decimals().call(),
            address=token_address,
            contract=token_contract,
        )

    @classmethod
    def from_dict(
        cls, w3: Web3, token_params: Dict[str, Any]  # pylint: disable=invalid-name
    ) -> "ERC20Token":
        """
        Initialize ERC20Token from dictionary.  Dictionary must contain keys: name, symbol, decimals, and address.

        :param w3:
            :class:`~web3.Web3` RPC connection to EVM node for performing token queries
        :param dict token_params:
            Dictionary containing token parameters
        :return: :class:`~python_eth_amm.base.token.ERC20Token`
        """
        token_address = to_checksum_address(token_params["address"])
        token_contract = w3.eth.contract(token_address, abi=cls.get_abi())

        return ERC20Token(
            name=token_params["name"],
            symbol=token_params["symbol"],
            decimals=token_params["decimals"],
            address=token_address,
            contract=token_contract,
        )

    @classmethod
    def get_abi(cls, json_string: Optional[bool] = False) -> Union[Dict[str, Any], str]:
        """
        Returns ABI for ERC20 Token Contract.

        :param bool json_string:
            If true, returns ABI as a JSON string.  Otherwise, returns ABI as a dictionary.

            Default: False
        :return:
        """
        with open(
            Path(__file__).parent.joinpath("ERC20ABI.json"), "r", encoding="utf-8"
        ) as json_file:
            abi = json.load(json_file)
        if json_string:
            return json.dumps(abi)
        return abi

    def convert_decimals(self, raw_token_amount: int) -> float:
        """
        Divides raw token amounts by token decimals.

        :param int raw_token_amount:
            Raw token amount
        :return:
            Token amount adjusted by decimals
        """
        return raw_token_amount / 10**self.decimals

    def human_readable(self, raw_token_amount: int) -> str:
        """
        Converts raw token amount to human-readable string containing the correct decimals and the token symbol.

        :param raw_token_amount:
            raw token amount
        :return:
            Human-readable string containing token amount and symbol
        """

        return f"{self.convert_decimals(raw_token_amount)} {self.symbol}"


NULL_TOKEN = ERC20Token(
    name="Empty Test Token",
    symbol="NULL",
    decimals=18,
    address="0x0000000000000000000000000000000000000000",
    contract=None,
)
