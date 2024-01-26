from typing import Any

from sqlalchemy import JSON, BigInteger, Numeric, PrimaryKeyConstraint, Text
from sqlalchemy.dialects.postgresql import BYTEA
from sqlalchemy.orm import Mapped, mapped_column

from .base import (
    AbstractBlock,
    AbstractEvent,
    AbstractTransaction,
    Address,
    CalldataBytes,
    Hash32,
    IndexedAddress,
    IndexedNullableAddress,
)

# pylint: disable=missing-class-docstring


class POSBlock(AbstractBlock):
    __tablename__ = "pos_blocks"

    parent_hash: Mapped[Hash32]
    miner: Mapped[Address]
    difficulty: Mapped[int] = mapped_column(Numeric(32, 0), nullable=True)
    gas_limit: Mapped[int] = mapped_column(BigInteger, nullable=False)

    extra_data: Mapped[str] = mapped_column(
        Text().with_variant(BYTEA, "postgresql"), nullable=False
    )

    __table_args__ = {"schema": "polygon_data"}


class POSDefaultEvent(AbstractEvent):
    __tablename__ = "pos_default_events"

    event_name: Mapped[str | None] = mapped_column(Text, index=True)
    abi_name: Mapped[str | None] = mapped_column(Text, index=True)
    decoded_event: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("block_number", "log_index"),
        {"schema": "polygon_data"},
    )


class POSTransaction(AbstractTransaction):
    __tablename__ = "pos_transactions"

    nonce: Mapped[int]
    from_address: Mapped[IndexedAddress]
    to_address: Mapped[IndexedNullableAddress | None]
    input: Mapped[CalldataBytes | None]

    value: Mapped[int] = mapped_column(Numeric(24, 0), nullable=False)

    gas_available: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    gas_price: Mapped[int] = mapped_column(Numeric(16, 0), nullable=False)
    gas_used: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    decoded_signature: Mapped[str | None]
    decoded_input: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    __table_args__ = {"schema": "polygon_data"}


class ZKEVMBlock(AbstractBlock):
    __tablename__ = "zk_evm_blocks"

    parent_hash: Mapped[Hash32]
    miner: Mapped[Address]
    difficulty: Mapped[int] = mapped_column(Numeric(32, 0), nullable=True)
    gas_limit: Mapped[int] = mapped_column(BigInteger, nullable=False)

    extra_data: Mapped[str] = mapped_column(
        Text().with_variant(BYTEA, "postgresql"), nullable=False
    )

    __table_args__ = {"schema": "polygon_data"}


class ZKEVMTransaction(AbstractTransaction):
    __tablename__ = "zk_evm_transactions"

    nonce: Mapped[int]
    from_address: Mapped[IndexedAddress]
    to_address: Mapped[IndexedNullableAddress | None]
    input: Mapped[CalldataBytes | None]

    value: Mapped[int] = mapped_column(Numeric(24, 0))

    gas_available: Mapped[int | None] = mapped_column(BigInteger)
    gas_price: Mapped[int] = mapped_column(Numeric(16, 0))
    gas_used: Mapped[int | None] = mapped_column(BigInteger)

    decoded_signature: Mapped[str | None]
    decoded_input: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    __table_args__ = {"schema": "polygon_data"}


class ZKEVMDefaultEvent(AbstractEvent):
    __tablename__ = "zk_evm_default_events"

    event_name: Mapped[str | None] = mapped_column(Text, index=True)
    abi_name: Mapped[str | None] = mapped_column(Text, index=True)
    decoded_event: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("block_number", "log_index"),
        {"schema": "polygon_data"},
    )
