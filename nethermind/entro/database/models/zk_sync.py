from typing import Any

from sqlalchemy import JSON, BigInteger, Numeric, PrimaryKeyConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column

from nethermind.entro.database.models.base import (
    AbstractBlock,
    AbstractERC20Transfer,
    AbstractEvent,
    AbstractTransaction,
    Address,
    CalldataBytes,
    Hash32,
    IndexedAddress,
    IndexedNullableAddress,
)

# pylint: disable=missing-class-docstring


class EraBlock(AbstractBlock):
    __tablename__ = "era_blocks"

    parent_hash: Mapped[Hash32]
    miner: Mapped[Address]
    difficulty: Mapped[int] = mapped_column(Numeric(32, 0), nullable=True)
    gas_limit: Mapped[int] = mapped_column(BigInteger, nullable=False)

    extra_data: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = {"schema": "zk_sync_data"}


class EraDefaultEvent(AbstractEvent):
    __tablename__ = "era_default_events"

    event_name: Mapped[str | None] = mapped_column(Text, index=True)
    abi_name: Mapped[str | None] = mapped_column(Text, index=True)
    decoded_event: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("block_number", "event_index"),
        {"schema": "zk_sync_data"},
    )


class EraTransaction(AbstractTransaction):
    __tablename__ = "era_transactions"

    nonce: Mapped[int]
    from_address: Mapped[IndexedAddress]
    to_address: Mapped[IndexedNullableAddress | None]
    input: Mapped[CalldataBytes | None]

    value: Mapped[int] = mapped_column(Numeric(24, 0), nullable=False)

    gas_available: Mapped[int | None] = mapped_column(BigInteger)
    gas_price: Mapped[int] = mapped_column(Numeric(16, 0))

    decoded_signature: Mapped[str | None]
    decoded_input: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    error: Mapped[str | None]

    __table_args__ = {"schema": "zk_sync_data"}


class EraERC20Transfer(AbstractERC20Transfer):
    __tablename__ = "era_erc20_transfers"

    __table_args__ = (PrimaryKeyConstraint("transaction_hash", "event_index"), {"schema": "zk_sync_data"})