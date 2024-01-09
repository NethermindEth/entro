from typing import Any

import click
import sqlalchemy
from sqlalchemy import (
    JSON,
    BigInteger,
    Engine,
    MetaData,
    Numeric,
    PrimaryKeyConstraint,
    Text,
)
from sqlalchemy.dialects.postgresql import BYTEA
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .types import (
    Address,
    BlockNumberPK,
    CalldataBytes,
    Hash32,
    Hash32PK,
    IndexedAddress,
    IndexedBlockNumber,
    IndexedNullableAddress,
)


# pylint: disable=missing-class-docstring
class PolygonDataBase(DeclarativeBase):
    metadata = MetaData(schema="polygon_data")


class POSBlock(PolygonDataBase):
    __tablename__ = "pos_blocks"

    block_number: Mapped[BlockNumberPK]
    hash: Mapped[Hash32]
    parent_hash: Mapped[Hash32]
    timestamp: Mapped[int] = mapped_column(BigInteger)
    miner: Mapped[Address]
    difficulty: Mapped[int] = mapped_column(Numeric(32, 0), nullable=True)
    gas_limit: Mapped[int] = mapped_column(BigInteger, nullable=False)
    gas_used: Mapped[int] = mapped_column(BigInteger, nullable=False)
    extra_data: Mapped[str] = mapped_column(
        Text().with_variant(BYTEA, "postgresql"), nullable=False
    )

    transaction_count: Mapped[int]


class POSDefaultEvent(PolygonDataBase):
    __tablename__ = "pos_default_events"

    block_number: Mapped[IndexedBlockNumber]
    log_index: Mapped[int]
    transaction_index: Mapped[int]
    contract_address: Mapped[IndexedAddress]

    event_name: Mapped[str | None] = mapped_column(Text, index=True)
    abi_name: Mapped[str | None] = mapped_column(Text, index=True)
    decoded_event: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (PrimaryKeyConstraint("block_number", "log_index"),)


class POSTransaction(PolygonDataBase):
    __tablename__ = "pos_transactions"

    hash: Mapped[Hash32PK]
    block_number: Mapped[IndexedBlockNumber]
    transaction_index: Mapped[int]
    timestamp: Mapped[int] = mapped_column(BigInteger)
    nonce: Mapped[int]
    from_address: Mapped[IndexedAddress]
    to_address: Mapped[IndexedNullableAddress | None]
    input: Mapped[CalldataBytes | None]

    value: Mapped[int] = mapped_column(Numeric(24, 0), nullable=False)
    is_error: Mapped[bool | None]

    gas_available: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    gas_price: Mapped[int] = mapped_column(Numeric(16, 0), nullable=False)
    gas_used: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    decoded_signature: Mapped[str | None]
    decoded_input: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class ZKEVMBlock(PolygonDataBase):
    __tablename__ = "zk_evm_blocks"

    block_number: Mapped[BlockNumberPK]
    hash: Mapped[Hash32]
    parent_hash: Mapped[Hash32]
    timestamp: Mapped[int] = mapped_column(BigInteger)
    miner: Mapped[Address]
    difficulty: Mapped[int] = mapped_column(Numeric(32, 0), nullable=True)
    gas_limit: Mapped[int] = mapped_column(BigInteger, nullable=False)
    gas_used: Mapped[int] = mapped_column(BigInteger, nullable=False)
    extra_data: Mapped[str] = mapped_column(
        Text().with_variant(BYTEA, "postgresql"), nullable=False
    )

    transaction_count: Mapped[int]


class ZKEVMTransaction(PolygonDataBase):
    __tablename__ = "zk_evm_transactions"

    hash: Mapped[Hash32PK]
    block_number: Mapped[IndexedBlockNumber]
    transaction_index: Mapped[int]
    timestamp: Mapped[int] = mapped_column(BigInteger)
    nonce: Mapped[int]
    from_address: Mapped[IndexedAddress]
    to_address: Mapped[IndexedNullableAddress | None]
    input: Mapped[CalldataBytes | None]

    value: Mapped[int] = mapped_column(Numeric(24, 0))
    is_error: Mapped[bool | None]

    gas_available: Mapped[int | None] = mapped_column(BigInteger)
    gas_price: Mapped[int] = mapped_column(Numeric(16, 0))
    gas_used: Mapped[int | None] = mapped_column(BigInteger)

    decoded_signature: Mapped[str | None]
    decoded_input: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class ZKEVMDefaultEvent(PolygonDataBase):
    __tablename__ = "zk_evm_default_events"

    block_number: Mapped[IndexedBlockNumber]
    log_index: Mapped[int]
    transaction_index: Mapped[int]
    contract_address: Mapped[IndexedAddress]

    event_name: Mapped[str | None] = mapped_column(Text, index=True)
    abi_name: Mapped[str | None] = mapped_column(Text, index=True)
    decoded_event: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (PrimaryKeyConstraint("block_number", "log_index"),)


def migrate_polygon_tables(db_engine: Engine):
    """
    Migrates the polygon tables to the database.

    :param db_engine:
    :return:
    """
    conn = db_engine.connect()
    if not conn.dialect.has_schema(conn, "polygon_data"):
        click.echo("Creating schema polygon_data")
        conn.execute(sqlalchemy.schema.CreateSchema("polygon_data"))
        conn.commit()

    PolygonDataBase.metadata.create_all(bind=db_engine)
