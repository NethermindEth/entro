from typing import Any

from sqlalchemy import JSON, BigInteger, Numeric, PrimaryKeyConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column

from nethermind.entro.database.models.base import (
    AbstractBlock,
    AbstractERC20Transfer,
    AbstractEvent,
    AbstractTransaction,
    BlockNumberPK,
    Hash32,
    Hash32PK,
    IndexedBlockNumber,
)
from nethermind.idealis.types.starknet import DecodedOperation
from nethermind.idealis.types.starknet.enums import (
    BlockDataAvailabilityMode,
    StarknetFeeUnit,
    StarknetTxType,
    TransactionStatus,
)

# pylint: disable=missing-class-docstring


class Block(AbstractBlock):
    __tablename__ = "blocks"

    block_number: Mapped[BlockNumberPK]
    timestamp: Mapped[int] = mapped_column(BigInteger, nullable=False)

    block_hash: Mapped[Hash32]
    parent_hash: Mapped[Hash32]
    state_root: Mapped[Hash32]
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

    keys: Mapped[list[str]] = mapped_column(JSON)
    data: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    class_hash: Mapped[str | None] = mapped_column(Text, nullable=True)

    event_name: Mapped[str | None] = mapped_column(Text, index=True)
    decoded_params: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("block_number", "transaction_index", "event_index"),
        {"schema": "starknet_data"},
    )


class Transaction(AbstractTransaction):
    __tablename__ = "transactions"

    transaction_hash: Mapped[Hash32PK]
    block_number: Mapped[IndexedBlockNumber]
    transaction_index: Mapped[int]

    type: Mapped[StarknetTxType]
    nonce: Mapped[int]
    signature: Mapped[list[str]] = mapped_column(JSON)
    version: Mapped[int]
    timestamp: Mapped[int]
    status: Mapped[TransactionStatus]

    max_fee: Mapped[int] = mapped_column(Numeric)
    actual_fee: Mapped[int] = mapped_column(Numeric)
    fee_unit: Mapped[StarknetFeeUnit]
    execution_resources: Mapped[dict[str, Any]] = mapped_column(JSON)
    gas_used: Mapped[int] = mapped_column(BigInteger)

    tip: Mapped[int] = mapped_column(Numeric)  # Not In Use
    resource_bounds: Mapped[dict[str, int] | None] = mapped_column(JSON, nullable=True)
    paymaster_data: Mapped[list[str]] = mapped_column(JSON)
    account_deployment_data: Mapped[list[str]] = mapped_column(JSON)

    contract_address: Mapped[str | None] = mapped_column(Text, index=True, nullable=True)
    selector: Mapped[str]
    calldata: Mapped[list[str]] = mapped_column(JSON)
    class_hash: Mapped[str | None]  # Deploy Account & Declare V2

    user_operations: Mapped[list[DecodedOperation]] = mapped_column(JSON)
    revert_error: Mapped[str | None]

    __table_args__ = {"schema": "starknet_data"}


class ERC20Transfer(AbstractERC20Transfer):
    __tablename__ = "erc20_transfers"

    __table_args__ = (PrimaryKeyConstraint("transaction_hash", "event_index"), {"schema": "starknet_data"})
