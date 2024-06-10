import datetime
from typing import Type

from sqlalchemy import DateTime, Index, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column

from nethermind.entro.database.models.base import (
    AbstractEvent,
    Base,
    Hash32PK,
    IndexedAddress,
    IndexedBlockNumber,
    UInt128,
    UInt160,
    UInt256,
)

# pylint: disable=missing-class-docstring


class UniV3SimSwapLogs(Base):
    __tablename__ = "v3_simulator_swap_logs"
    swap_id: Mapped[Hash32PK]
    pool_id: Mapped[IndexedAddress]
    write_timestamp: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now())

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

    __table_args__ = {"schema": "uniswap"}


class UniV3SimPositionLogs(Base):
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
        PrimaryKeyConstraint("pool_id", "block_number", "lp_address", "tick_lower", "tick_upper"),
        {"schema": "uniswap"},
    )


class UniV3MintEvent(AbstractEvent):
    __tablename__ = "v3_mint_events"

    sender: Mapped[IndexedAddress]
    owner: Mapped[IndexedAddress]
    tick_lower: Mapped[int]
    tick_upper: Mapped[int]
    amount: Mapped[UInt256]
    amount_0: Mapped[UInt256]
    amount_1: Mapped[UInt256]

    __table_args__ = (
        PrimaryKeyConstraint("block_number", "log_index"),
        Index("uniswap.ix_v3_mint_sender", "sender"),
        Index("uniswap.ix_v3_mint_position", "owner", "tick_lower", "tick_upper"),
        {"schema": "uniswap"},
    )


class UniV3CollectEvent(AbstractEvent):
    __tablename__ = "v3_collect_events"

    owner: Mapped[IndexedAddress]
    recipient: Mapped[IndexedAddress]
    tick_lower: Mapped[int]
    tick_upper: Mapped[int]
    amount_0: Mapped[UInt256]
    amount_1: Mapped[UInt256]

    __table_args__ = (
        PrimaryKeyConstraint("block_number", "log_index"),
        Index("uniswap.ix_v3_collect_position", "owner", "tick_lower", "tick_upper"),
        Index("uniswap.ix_v3_collect_recipient", "recipient"),
        {"schema": "uniswap"},
    )


class UniV3BurnEvent(AbstractEvent):
    __tablename__ = "v3_burn_events"

    owner: Mapped[IndexedAddress]
    tick_lower: Mapped[int]
    tick_upper: Mapped[int]
    amount: Mapped[UInt256]
    amount_0: Mapped[UInt256]
    amount_1: Mapped[UInt256]

    __table_args__ = (
        PrimaryKeyConstraint("block_number", "log_index"),
        Index("uniswap.ix_v3_burn_position", "owner", "tick_lower", "tick_upper"),
        {"schema": "uniswap"},
    )


class UniV3SwapEvent(AbstractEvent):
    __tablename__ = "v3_swap_events"

    sender: Mapped[IndexedAddress]
    recipient: Mapped[IndexedAddress]
    amount_0: Mapped[UInt256]
    amount_1: Mapped[UInt256]
    sqrt_price: Mapped[UInt160]
    liquidity: Mapped[UInt128]
    tick: Mapped[int]

    __table_args__ = (
        PrimaryKeyConstraint("block_number", "log_index"),
        Index("uniswap.ix_v3_swap_sender", "sender"),
        Index("uniswap.ix_v3_swap_recipient", "recipient"),
        {"schema": "uniswap"},
    )


class UniV3FlashEvent(AbstractEvent):
    __tablename__ = "v3_flash_events"

    sender: Mapped[IndexedAddress]
    recipient: Mapped[IndexedAddress]
    amount_0: Mapped[UInt256]
    amount_1: Mapped[UInt256]
    paid_0: Mapped[UInt256]
    paid_1: Mapped[UInt256]

    __table_args__ = (
        PrimaryKeyConstraint("block_number", "log_index"),
        Index("uniswap.ix_v3_flash_sender", "sender"),
        Index("uniswap.ix_v3_flash_recipient", "recipient"),
        {"schema": "uniswap"},
    )


class UniV3PoolCreationEvent(AbstractEvent):
    __tablename__ = "v3_pool_creation_events"

    token_0: Mapped[IndexedAddress]
    token_1: Mapped[IndexedAddress]
    pool: Mapped[IndexedAddress]
    fee: Mapped[int]
    tick_spacing: Mapped[int]

    __table_args__ = (
        PrimaryKeyConstraint("block_number", "log_index"),
        Index("uniswap.ix_v3_pool_creation_token_0", "token_0"),
        Index("uniswap.ix_v3_pool_creation_token_1", "token_1"),
        Index("uniswap.ix_v3_pool_creation_pool", "pool"),
        {"schema": "uniswap"},
    )


UNI_EVENT_MODELS: dict[str, Type[AbstractEvent]] = {
    "Mint(address,address,int24,int24,uint128,uint256,uint256)": UniV3MintEvent,
    "Collect(address,address,int24,int24,uint128,uint128)": UniV3CollectEvent,
    "Burn(address,int24,int24,uint128,uint256,uint256)": UniV3BurnEvent,
    "Swap(address,address,int256,int256,uint160,uint128,int24)": UniV3SwapEvent,
    "Flash(address,address,uint256,uint256,uint256,uint256)": UniV3FlashEvent,
    "PoolCreated(address,address,uint24,int24,address)": UniV3PoolCreationEvent,
}
