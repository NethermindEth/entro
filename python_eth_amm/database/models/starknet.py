from typing import Any

import click
import sqlalchemy
from sqlalchemy import JSON, BigInteger, Engine, MetaData, PrimaryKeyConstraint, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .types import BlockNumberPK, Hash32, Hash32PK, IndexedAddress, IndexedBlockNumber


# pylint: disable=missing-class-docstring
class StarknetDataBase(DeclarativeBase):
    metadata = MetaData(schema="starknet_data")


class Block(StarknetDataBase):
    __tablename__ = "blocks"

    block_number: Mapped[BlockNumberPK]
    block_hash: Mapped[Hash32]
    timestamp: Mapped[int] = mapped_column(BigInteger, nullable=False)
    state_root: Mapped[Hash32]

    transaction_count: Mapped[int]
    message_count: Mapped[int]
    event_count: Mapped[int]
    l1_verification_txn_hash: Mapped[Hash32 | None]

    status: Mapped[str | None]


class DefaultEvent(StarknetDataBase):
    __tablename__ = "default_events"

    block_number: Mapped[IndexedBlockNumber]
    log_index: Mapped[int]
    transaction_index: Mapped[int]
    contract_address: Mapped[IndexedAddress]

    event_name: Mapped[str | None] = mapped_column(Text, index=True)
    abi_name: Mapped[str | None] = mapped_column(Text, index=True)
    decoded_event: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (PrimaryKeyConstraint("block_number", "log_index"),)


class Transaction(StarknetDataBase):
    __tablename__ = "transactions"

    hash: Mapped[Hash32PK]
    block_number: Mapped[IndexedBlockNumber]
    transaction_index: Mapped[int]
    timestamp: Mapped[int] = mapped_column(BigInteger)
    nonce: Mapped[int]
    max_fee: Mapped[int]
    type: Mapped[str]  # "DECLARE", "DEPLOY", "DEPLOY_ACCOUNT", "INVOKE", "L1_HANDLER"
    signature: Mapped[str]

    sender_address: Mapped[IndexedAddress]
    calldata: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    # Receipt Data
    actual_fee: Mapped[int | None]
    execution_resources: Mapped[dict[str, int] | None] = mapped_column(
        JSON, nullable=True
    )
    gas_used: Mapped[int | None]  # Compute from execution resources
    is_error: Mapped[bool]


def migrate_starknet_tables(db_engine: Engine):
    """
    Migrate the Starknet tables to the database.

    :param db_engine:
    :return:
    """
    conn = db_engine.connect()
    if not conn.dialect.has_schema(conn, "starknet_data"):
        click.echo("Creating schema starknet_data")
        conn.execute(sqlalchemy.schema.CreateSchema("starknet_data"))
        conn.commit()

    StarknetDataBase.metadata.create_all(bind=db_engine)
