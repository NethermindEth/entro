import datetime
from typing import Type

import click
import sqlalchemy
from sqlalchemy import DateTime, Engine, MetaData, PrimaryKeyConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .types import (
    Hash32PK,
    IndexedAddress,
    IndexedBlockNumber,
    UInt128,
    UInt160,
    UInt256,
)


# pylint: disable=missing-class-docstring
class UniswapBase(DeclarativeBase):
    metadata = MetaData(schema="uniswap")


class UniV3SimSwapLogs(UniswapBase):
    __tablename__ = "v3_simulator_swap_logs"
    swap_id: Mapped[Hash32PK]
    pool_id: Mapped[IndexedAddress]
    write_timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now()
    )

    token_in_symbol: Mapped[str]
    token_in_amount: Mapped[UInt256]
    token_out_symbol: Mapped[str]
    token_out_amount: Mapped[UInt256]
    pool_start_price: Mapped[UInt160]
    pool_end_price: Mapped[UInt160]
    fill_price_token_0: Mapped[float]
    fill_price_token_1: Mapped[float]
    fee_token: Mapped[str]
    fee_amount: Mapped[UInt128]


class UniV3SimPositionLogs(UniswapBase):
    __tablename__ = "v3_simulator_position_logs"

    pool_id: Mapped[IndexedAddress]
    block_number: Mapped[IndexedBlockNumber]
    lp_address: Mapped[IndexedAddress]
    tick_lower: Mapped[int]
    tick_upper: Mapped[int]
    currently_active: Mapped[bool]
    token_0_value: Mapped[UInt256]
    token_1_value: Mapped[UInt256]
    token_0_value_usd: Mapped[float | None]
    token_1_value_usd: Mapped[float | None]

    __table_args__ = (
        PrimaryKeyConstraint(
            "pool_id", "block_number", "lp_address", "tick_lower", "tick_upper"
        ),
    )


class UniV3MintEvent(UniswapBase):
    __tablename__ = "v3_mint_events"

    block_number: Mapped[IndexedBlockNumber]
    log_index: Mapped[int]
    transaction_index: Mapped[int]
    contract_address: Mapped[IndexedAddress]

    sender: Mapped[IndexedAddress]
    owner: Mapped[IndexedAddress]
    tick_lower: Mapped[int]
    tick_upper: Mapped[int]
    amount: Mapped[UInt256]
    amount_0: Mapped[UInt256]
    amount_1: Mapped[UInt256]

    __table_args__ = (PrimaryKeyConstraint("block_number", "log_index"),)


class UniV3CollectEvent(UniswapBase):
    __tablename__ = "v3_collect_events"

    block_number: Mapped[IndexedBlockNumber]
    log_index: Mapped[int]
    transaction_index: Mapped[int]
    contract_address: Mapped[IndexedAddress]

    owner: Mapped[IndexedAddress]
    recipient: Mapped[IndexedAddress]
    tick_lower: Mapped[int]
    tick_upper: Mapped[int]
    amount_0: Mapped[UInt256]
    amount_1: Mapped[UInt256]

    __table_args__ = (PrimaryKeyConstraint("block_number", "log_index"),)


class UniV3BurnEvent(UniswapBase):
    __tablename__ = "v3_burn_events"

    block_number: Mapped[IndexedBlockNumber]
    log_index: Mapped[int]
    transaction_index: Mapped[int]
    contract_address: Mapped[IndexedAddress]

    owner: Mapped[IndexedAddress]
    tick_lower: Mapped[int]
    tick_upper: Mapped[int]
    amount: Mapped[UInt256]
    amount_0: Mapped[UInt256]
    amount_1: Mapped[UInt256]

    __table_args__ = (PrimaryKeyConstraint("block_number", "log_index"),)


class UniV3SwapEvent(UniswapBase):
    __tablename__ = "v3_swap_events"

    block_number: Mapped[IndexedBlockNumber]
    log_index: Mapped[int]
    transaction_index: Mapped[int]
    contract_address: Mapped[IndexedAddress]

    sender: Mapped[IndexedAddress]
    recipient: Mapped[IndexedAddress]
    amount_0: Mapped[UInt256]
    amount_1: Mapped[UInt256]
    sqrt_price: Mapped[UInt160]
    liquidity: Mapped[UInt128]
    tick: Mapped[int]

    __table_args__ = (PrimaryKeyConstraint("block_number", "log_index"),)


class UniV3FlashEvent(UniswapBase):
    __tablename__ = "v3_flash_events"

    block_number: Mapped[IndexedBlockNumber]
    log_index: Mapped[int]
    transaction_index: Mapped[int]
    contract_address: Mapped[IndexedAddress]

    sender: Mapped[IndexedAddress]
    recipient: Mapped[IndexedAddress]
    amount_0: Mapped[UInt256]
    amount_1: Mapped[UInt256]
    paid_0: Mapped[UInt256]
    paid_1: Mapped[UInt256]

    __table_args__ = (PrimaryKeyConstraint("block_number", "log_index"),)


class UniV3PoolCreationEvent(UniswapBase):
    __tablename__ = "v3_pool_creation_events"

    block_number: Mapped[IndexedBlockNumber]
    log_index: Mapped[int]
    transaction_index: Mapped[int]
    contract_address: Mapped[IndexedAddress]

    token_0: Mapped[IndexedAddress]
    token_1: Mapped[IndexedAddress]
    pool_address: Mapped[IndexedAddress]
    fee: Mapped[int]

    __table_args__ = (PrimaryKeyConstraint("block_number", "log_index"),)


UNI_EVENT_MODELS: dict[str, Type[UniswapBase]] = {
    "Mint(address,address,int24,int24,uint128,uint256,uint256)": UniV3MintEvent,
    "Collect(address,address,int24,int24,uint128,uint128)": UniV3CollectEvent,
    "Burn(address,int24,int24,uint128,uint256,uint256)": UniV3BurnEvent,
    "Swap(address,address,int256,int256,uint160,uint128,int24)": UniV3SwapEvent,
    "Flash(address,address,uint256,uint256,uint256,uint256)": UniV3FlashEvent,
}


def migrate_uniswap_tables(db_engine: Engine):
    """
    Creates the uniswap schema and tables in the database provided

    :param db_engine:
    :return:
    """
    conn = db_engine.connect()
    if not conn.dialect.has_schema(conn, "uniswap"):
        click.echo("Creating schema uniswap")
        conn.execute(sqlalchemy.schema.CreateSchema("uniswap"))
        conn.commit()

    UniswapBase.metadata.create_all(bind=db_engine)
