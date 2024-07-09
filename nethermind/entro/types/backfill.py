from enum import Enum
from typing import Any, Protocol, TypeVar

# Disabling stupid naming check that wants enums to use UPPER_CASE
# pylint: disable=invalid-name


# This allows type-checkers to enforce dataclass type checks
class DataclassType(Protocol):
    __dataclass_fields__: dict[str, Any]


Dataclass = TypeVar("Dataclass", bound=DataclassType)


# Importer Callable checks that the callable Fn passed matches the signature defined in __call__
class ImporterCallable(Protocol):
    def __call__(self, from_block: int, to_block: int, **kwargs) -> dict[str, list[Dataclass]]:
        # Return {'blocks': [BlockDataclass, ...], 'transactions': [TransactionDataclass, ...]}
        ...


class BackfillDataType(Enum):
    """
    Different Types of Blockchain Data that can be Backfilled
    """

    full_blocks = "full_blocks"
    blocks = "blocks"
    transactions = "transactions"
    transfers = "transfers"
    spot_prices = "spot_prices"
    prices = "prices"
    events = "events"
    traces = "traces"

    def pretty(self):
        """Returns a pretty version of the data type"""
        match self:
            case BackfillDataType.full_blocks:
                return "Full Blocks"
            case BackfillDataType.spot_prices:
                return "Spot-Prices"
            case _:
                return self.value.capitalize()


class DataSources(Enum):
    """Enum storing supported backfill data sources"""

    json_rpc = "json_rpc"
    etherscan = "etherscan"


class SupportedNetwork(Enum):
    """supported networks that can be backfilled"""

    starknet = "starknet"
    ethereum = "ethereum"
    zk_sync_era = "zk_sync_era"

    def pretty(self):
        """Returns a pretty version of the network name"""
        match self:
            case SupportedNetwork.starknet:
                return "StarkNet"
            case SupportedNetwork.zk_sync_era:
                return "zkSync Era"
            case _:
                return self.value.capitalize()
