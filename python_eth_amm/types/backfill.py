from enum import Enum

# Disabling stupid naming check that wants enums to use UPPER_CASE
# pylint: disable=C0103


class EnumHandler(Enum):
    """Base class for enums that can be converted to CLI friendly choices"""

    def to_choices(self):
        """Converts enum values to CLI friendly choices"""
        return [e.value.replace("_", "-") for e in self.__members__.values()]

    @classmethod
    def from_choices(cls, cli_input: str) -> "EnumHandler":
        """Converts CLI input to enum value"""
        match_str = cli_input.lower().replace("-", "_")
        return cls(match_str)


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


class DataSources(Enum):
    """Enum storing supported backfill data sources"""

    json_rpc = "json_rpc"
    etherscan = "etherscan"
    # the_graph = "the_graph"


class SupportedNetwork(Enum):
    """supported networks that can be backfilled"""

    starknet = "starknet"
    ethereum = "ethereum"
    zk_sync_lite = "zk_sync_lite"
    zk_sync_era = "zk_sync_era"
    polygon_zk_evm = "polygon_zk_evm"
