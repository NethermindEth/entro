from typing import Any

from sqlalchemy import JSON, BigInteger, Numeric, PrimaryKeyConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column

from nethermind.entro.database.models.base import (
    AbstractBlock,
    AbstractERC20Transfer,
    AbstractEvent,
    AbstractTrace,
    AbstractTransaction,
    Address,
    CalldataBytes,
    Hash32,
    IndexedAddress,
    IndexedBlockNumber,
    IndexedNullableAddress,
)

# pylint: disable=missing-class-docstring


class Block(AbstractBlock):
    __tablename__ = "blocks"

    parent_hash: Mapped[Hash32]
    state_root: Mapped[Hash32]
    miner: Mapped[Address]
    extra_data: Mapped[CalldataBytes]  # Variable length bytes
    nonce: Mapped[CalldataBytes]  # Variable length bytes

    difficulty: Mapped[int] = mapped_column(Numeric(32, 0), nullable=True)
    total_difficulty: Mapped[int] = mapped_column(Numeric(32, 0), nullable=True)
    size: Mapped[int]

    base_fee_per_gas: Mapped[int] = mapped_column(Numeric(16, 0), nullable=False)
    gas_limit: Mapped[int] = mapped_column(BigInteger, nullable=False)
    gas_used: Mapped[int] = mapped_column(BigInteger, nullable=False)

    __table_args__ = {"schema": "ethereum_data"}


class DefaultEvent(AbstractEvent):
    __tablename__ = "default_events"

    topics: Mapped[list[str]] = mapped_column(JSON)
    data: Mapped[CalldataBytes | None] = mapped_column(Text, nullable=True)

    event_name: Mapped[str | None] = mapped_column(Text, index=True)
    decoded_params: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("block_number", "event_index"),
        {"schema": "ethereum_data"},
    )


class Transaction(AbstractTransaction):
    __tablename__ = "transactions"

    nonce: Mapped[int]
    type: Mapped[int | None]

    value: Mapped[int] = mapped_column(Numeric(24, 0))
    gas_price: Mapped[int | None] = mapped_column(Numeric(16, 0), nullable=True)
    gas_supplied: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    gas_used: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    max_priority_fee: Mapped[int | None] = mapped_column(Numeric(16, 0), nullable=True)
    max_fee: Mapped[int | None] = mapped_column(Numeric(16, 0), nullable=True)

    to_address: Mapped[IndexedNullableAddress]
    from_address: Mapped[IndexedNullableAddress]

    input: Mapped[CalldataBytes | None]
    decoded_input: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    function_name: Mapped[str | None] = mapped_column(Text, index=True)

    __table_args__ = {"schema": "ethereum_data"}


class Trace(AbstractTrace):
    __tablename__ = "traces"

    transaction_hash: Mapped[Hash32]
    block_number: Mapped[IndexedBlockNumber]
    # Trace addresses are converted to Text strings ie, [0,1,2,3,4]
    trace_address: Mapped[list[int]] = mapped_column(Text)

    from_address: Mapped[IndexedAddress]
    to_address: Mapped[IndexedNullableAddress | None]

    input: Mapped[CalldataBytes | None]
    output: Mapped[CalldataBytes | None]

    gas_used: Mapped[int] = mapped_column(BigInteger, nullable=False)
    decoded_function: Mapped[str | None] = mapped_column(Text, index=True)
    decoded_input: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    decoded_output: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    __table_args__ = (
        PrimaryKeyConstraint("transaction_hash", "trace_address"),
        {"schema": "ethereum_data"},
    )


class ERC20Transfer(AbstractERC20Transfer):
    __tablename__ = "erc20_transfers"

    __table_args__ = (PrimaryKeyConstraint("transaction_hash", "event_index"), {"schema": "ethereum_data"})
