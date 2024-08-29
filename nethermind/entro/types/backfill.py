import datetime
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, ClassVar, Protocol, TypeVar

# Disabling stupid naming check that wants enums to use UPPER_CASE
# pylint: disable=invalid-name


class ExporterDataType(Enum):
    """Data Type Key for Exporters"""

    blocks = "blocks"
    transactions = "transactions"
    events = "events"
    traces = "traces"
    transfers = "transfers"


def dataclass_as_dict(dataclass_instance: "Dataclass") -> dict[str, Any]:
    """Helper function with clearer name & MyPy typing"""
    return asdict(dataclass_instance)


class DataclassProtocol(Protocol):
    """Allows type-checkers to enforce dataclass type checks"""

    __dataclass_fields__: ClassVar[dict]


Dataclass = TypeVar("Dataclass", bound=DataclassProtocol)


class ImporterCallable(Protocol):
    """Verify callable Fn passed matches the signature defined in __call__"""

    def __call__(self, from_block: int, to_block: int, **kwargs) -> dict[ExporterDataType, list[Dataclass]]:
        # Return {'blocks': [BlockDataclass, ...], 'transactions': [TransactionDataclass, ...]}
        ...


class BlockProtocol(Protocol):
    """Protocol verifying Block Dataclasses have set of common fields"""

    block_number: int
    timestamp: int


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
    etherscan_api_key = "etherscan_api_key"


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


@dataclass(slots=True)
class BlockTimestamp:
    """More efficient way of storing block timestamps than a dict"""

    block_number: int
    timestamp: datetime.datetime
