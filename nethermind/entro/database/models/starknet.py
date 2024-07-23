from typing import Any

from sqlalchemy import JSON, BigInteger, Integer, Numeric, PrimaryKeyConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column

from nethermind.entro.database.models.base import (
    AbstractBlock,
    AbstractERC20Transfer,
    AbstractEvent,
    AbstractTransaction,
    BlockNumberPK,
    Hash32,
    IndexedAddress,
)
from nethermind.idealis.types.starknet.enums import BlockDataAvailabilityMode

# pylint: disable=missing-class-docstring


class Block(AbstractBlock):
    __tablename__ = "blocks"

    block_number: Mapped[BlockNumberPK]
    timestamp: Mapped[int] = mapped_column(BigInteger, nullable=False)

    block_hash: Mapped[Hash32]
    parent_hash: Mapped[Hash32]
    new_root: Mapped[Hash32]
    sequencer_address: Mapped[Hash32]

    l1_gas_price_wei: Mapped[int] = mapped_column(Numeric, nullable=False)
    l1_gas_price_fri: Mapped[int] = mapped_column(Numeric, nullable=False)
    l1_data_gas_price_wei: Mapped[int | None] = mapped_column(Numeric, nullable=True)
    l1_data_gas_price_fri: Mapped[int | None] = mapped_column(Numeric, nullable=True)
    l1_da_mode: Mapped[BlockDataAvailabilityMode]

    starknet_version: Mapped[str]
    transaction_count: Mapped[int]
    total_fee: Mapped[int] = mapped_column(Numeric, nullable=False)

    __table_args__ = {"schema": "starknet_data"}


class DefaultEvent(AbstractEvent):
    __tablename__ = "default_events"

    event_name: Mapped[str | None] = mapped_column(Text, index=True)
    abi_name: Mapped[str | None] = mapped_column(Text, index=True)
    decoded_event: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("block_number", "log_index"),
        {"schema": "starknet_data"},
    )


class Transaction(AbstractTransaction):
    __tablename__ = "transactions"

    nonce: Mapped[int]
    max_fee: Mapped[int]
    type: Mapped[str]  # "DECLARE", "DEPLOY", "DEPLOY_ACCOUNT", "INVOKE", "L1_HANDLER"
    signature: Mapped[str]

    sender_address: Mapped[IndexedAddress]
    calldata: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    # Receipt Data
    actual_fee: Mapped[int | None]
    execution_resources: Mapped[dict[str, int] | None] = mapped_column(JSON, nullable=True)
    gas_used: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = {"schema": "starknet_data"}


class ERC20Transfer(AbstractERC20Transfer):
    __tablename__ = "erc20_transfers"

    __table_args__ = (PrimaryKeyConstraint("transaction_hash", "log_index"), {"schema": "starknet_data"})
