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
from nethermind.idealis.utils import to_bytes

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
    tickLower: Mapped[int]
    tickUpper: Mapped[int]
    amount: Mapped[UInt256]
    amount0: Mapped[UInt256]
    amount1: Mapped[UInt256]

    __table_args__ = (
        PrimaryKeyConstraint("block_number", "event_index"),
        Index("uniswap.ix_v3_mint_sender", "sender"),
        Index("uniswap.ix_v3_mint_position", "owner", "tickLower", "tickUpper"),
        {"schema": "uniswap"},
    )


class UniV3CollectEvent(AbstractEvent):
    __tablename__ = "v3_collect_events"

    owner: Mapped[IndexedAddress]
    recipient: Mapped[IndexedAddress]
    tickLower: Mapped[int]
    tickUpper: Mapped[int]
    amount0: Mapped[UInt256]
    amount1: Mapped[UInt256]

    __table_args__ = (
        PrimaryKeyConstraint("block_number", "event_index"),
        Index("uniswap.ix_v3_collect_position", "owner", "tickLower", "tickUpper"),
        Index("uniswap.ix_v3_collect_recipient", "recipient"),
        {"schema": "uniswap"},
    )


class UniV3BurnEvent(AbstractEvent):
    __tablename__ = "v3_burn_events"

    owner: Mapped[IndexedAddress]
    tickLower: Mapped[int]
    tickUpper: Mapped[int]
    amount: Mapped[UInt256]
    amount0: Mapped[UInt256]
    amount1: Mapped[UInt256]

    __table_args__ = (
        PrimaryKeyConstraint("block_number", "event_index"),
        Index("uniswap.ix_v3_burn_position", "owner", "tickLower", "tickUpper"),
        {"schema": "uniswap"},
    )


class UniV3SwapEvent(AbstractEvent):
    __tablename__ = "v3_swap_events"

    sender: Mapped[IndexedAddress]
    recipient: Mapped[IndexedAddress]
    amount0: Mapped[UInt256]
    amount1: Mapped[UInt256]
    sqrtPrice: Mapped[UInt160]
    liquidity: Mapped[UInt128]
    tick: Mapped[int]

    __table_args__ = (
        PrimaryKeyConstraint("block_number", "event_index"),
        Index("uniswap.ix_v3_swap_sender", "sender"),
        Index("uniswap.ix_v3_swap_recipient", "recipient"),
        {"schema": "uniswap"},
    )


class UniV3FlashEvent(AbstractEvent):
    __tablename__ = "v3_flash_events"

    sender: Mapped[IndexedAddress]
    recipient: Mapped[IndexedAddress]
    amount0: Mapped[UInt256]
    amount1: Mapped[UInt256]
    paid0: Mapped[UInt256]
    paid1: Mapped[UInt256]

    __table_args__ = (
        PrimaryKeyConstraint("block_number", "event_index"),
        Index("uniswap.ix_v3_flash_sender", "sender"),
        Index("uniswap.ix_v3_flash_recipient", "recipient"),
        {"schema": "uniswap"},
    )


class UniV3PoolCreationEvent(AbstractEvent):
    __tablename__ = "v3_pool_creation_events"

    token0: Mapped[IndexedAddress]
    token1: Mapped[IndexedAddress]
    pool: Mapped[IndexedAddress]
    fee: Mapped[int]
    tickSpacing: Mapped[int]

    __table_args__ = (
        PrimaryKeyConstraint("block_number", "event_index"),
        Index("uniswap.ix_v3_pool_creation_token_0", "token0"),
        Index("uniswap.ix_v3_pool_creation_token_1", "token1"),
        Index("uniswap.ix_v3_pool_creation_pool", "pool"),
        {"schema": "uniswap"},
    )


UNI_EVENT_MODELS: dict[bytes, Type[AbstractEvent]] = {
    to_bytes("0x7a53080ba414158be7ec69b987b5fb7d07dee101fe85488f0853ae16239d0bde"): UniV3MintEvent,
    to_bytes("0x70935338e69775456a85ddef226c395fb668b63fa0115f5f20610b388e6ca9c0"): UniV3CollectEvent,
    to_bytes("0x0c396cd989a39f4459b5fa1aed6a9a8dcdbc45908acfd67e028cd568da98982c"): UniV3BurnEvent,
    to_bytes("0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"): UniV3SwapEvent,
    to_bytes("0xbdbdb71d7860376ba52b25a5028beea23581364a40522f6bcfb86bb1f2dca633"): UniV3FlashEvent,
    to_bytes("0x783cca1c0412dd0d695e784568c96da2e9c22ff989357a2e8b1d9b2b4e6b7118"): UniV3PoolCreationEvent,
}
