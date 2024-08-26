from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

from eth_typing import ChecksumAddress

# pylint: disable=invalid-name


class SupportedPricingPool(Enum):
    """Enum storing supported pricing pools"""

    uniswap_v3 = "uniswap_v3"


@dataclass
class TokenMarketInfo:
    """
    Stores the information about a token market.  This includes the token address, the reference token address,
    and the pool address.  This is used to generate the list of all available markets for querying prices
    """

    market_address: ChecksumAddress
    token_0: ChecksumAddress
    token_1: ChecksumAddress
    initialization_block: int

    pool_class: SupportedPricingPool
    metadata: dict[str, Any]


class AbstractTokenMarket:
    """
    Abstract class for token markets.  Provides standardized interface for computing quotes
    across different pricing pools
    """

    @abstractmethod
    def decode_price_from_event(self, event: dict[str, Any], reference_token: ChecksumAddress) -> float:
        """
        Decodes the price from an event

        :param event:
        :param reference_token:

        :return:
        """
        raise NotImplementedError
