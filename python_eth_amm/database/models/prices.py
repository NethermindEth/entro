import click
import sqlalchemy
from sqlalchemy import Engine, MetaData, PrimaryKeyConstraint, SmallInteger
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from python_eth_amm.addresses import UNISWAP_V3_FACTORY

from .types import IndexedAddress, IndexedBlockNumber
from .uniswap import UniV3PoolCreationEvent


class PriceDataBase(DeclarativeBase):
    """Base class for pricing tables"""

    metadata = MetaData(schema="price_data")


class MarketSpotPrice(PriceDataBase):
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
    )


class TokenPrice(PriceDataBase):
    """
    Table for storing spot prices for each token at each block.

    """

    __tablename__ = "token_prices"

    token_id: Mapped[IndexedAddress]
    block_number: Mapped[IndexedBlockNumber]

    eth_price: Mapped[float]
    usd_price: Mapped[float]

    __table_args__ = (PrimaryKeyConstraint("token_id", "block_number"),)


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


def migrate_price_tables(db_engine: Engine):
    """
    Create the price_data schema and all tables within it.

    :param db_engine:
    :return:
    """
    conn = db_engine.connect()
    if not conn.dialect.has_schema(conn, "price_data"):
        click.echo("Creating schema price_data")
        conn.execute(sqlalchemy.schema.CreateSchema("price_data"))
        conn.commit()

    PriceDataBase.metadata.create_all(bind=db_engine)
