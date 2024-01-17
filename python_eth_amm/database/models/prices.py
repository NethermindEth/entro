from sqlalchemy import PrimaryKeyConstraint, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column

from python_eth_amm.addresses import UNISWAP_V3_FACTORY

from .base import Base, IndexedAddress, IndexedBlockNumber
from .uniswap import UniV3PoolCreationEvent


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


MARKET_SPOT_PRICES_PER_BLOCK_QUERY = """
WITH added_row_number as (
    SELECT
        block_number,
        spot_price,
        ROW_NUMBER() OVER(PARTITION BY block_number ORDER BY transaction_index DESC) AS row_number
    FROM pricing_oracle.market_spot_prices
    WHERE
        block_number >= :from_block AND
        block_number < :to_block AND
        market_address = :market_id
    ) 
SELECT 
    block_number,
    spot_price
FROM added_row_number WHERE row_number=1
ORDER BY block_number;
"""

SUPPORTED_POOL_CREATION_EVENTS = {
    UNISWAP_V3_FACTORY: {
        "event_name": "PoolCreated",
        "event_model": UniV3PoolCreationEvent,
        "abi_name": "UniswapV3Factory",
    },
}
