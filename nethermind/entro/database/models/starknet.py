from typing import Any

from sqlalchemy import JSON, Integer, PrimaryKeyConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column

from nethermind.entro.database.models.base import (
    AbstractBlock,
    AbstractEvent,
    AbstractTransaction,
    Hash32,
    IndexedAddress,
)

# pylint: disable=missing-class-docstring


class Block(AbstractBlock):
    __tablename__ = "blocks"

    state_root: Mapped[Hash32]

    status: Mapped[str | None]

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
