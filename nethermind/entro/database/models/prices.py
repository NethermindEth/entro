from typing import Type, TypedDict

from sqlalchemy import PrimaryKeyConstraint, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column

from nethermind.entro.addresses import UNISWAP_V3_FACTORY
from nethermind.entro.database.models.base import (
    AbstractEvent,
    Base,
    IndexedAddress,
    IndexedBlockNumber,
)
from nethermind.entro.database.models.uniswap import UniV3PoolCreationEvent


class MarketSpotPrice(Base):
    """
    Table for storing spot prices for each market at each block.

    Priced & Reference Token Info stored in BackfilledRange filter json.
    """

    __tablename__ = "market_spot_prices"

    market_address: Mapped[IndexedAddress]

    block_number: Mapped[IndexedBlockNumber]
    transaction_index: Mapped[int] = mapped_column(SmallInteger)

    spot_price: Mapped[float]

    __table_args__ = (
        PrimaryKeyConstraint("market_address", "block_number", "transaction_index"),
        {"schema": "price_data"},
    )


class TokenPrice(Base):
    """
    Table for storing spot prices for each token at each block.

    """

    __tablename__ = "token_prices"

    token_id: Mapped[IndexedAddress]
    block_number: Mapped[IndexedBlockNumber]

    eth_price: Mapped[float]
    usd_price: Mapped[float]

    __table_args__ = (
        PrimaryKeyConstraint("token_id", "block_number"),
        {"schema": "price_data"},
    )


class PoolData(TypedDict):
    """Dataclass for storing data about pool creation events"""

    event_name: str
    event_model: Type[AbstractEvent]
    abi_name: str
    start_block: int


SUPPORTED_POOL_CREATION_EVENTS = {
    UNISWAP_V3_FACTORY: PoolData(
        event_name="PoolCreated",
        event_model=UniV3PoolCreationEvent,
        abi_name="UniswapV3Factory",
        start_block=12369621,
    ),
    # UNISWAP_V2_FACTORY: {
    #     "event_name": "PairCreated",
    #     "event_model": UniV2PairCreationEvent,
    #     "abi_name": "UniswapV2Factory",
    #     "start_block": 10000835
    # }
}
