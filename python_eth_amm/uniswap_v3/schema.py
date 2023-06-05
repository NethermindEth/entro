import datetime

from sqlalchemy import (
    VARCHAR,
    Boolean,
    Column,
    DateTime,
    Integer,
    MetaData,
    Numeric,
    PrimaryKeyConstraint,
)
from sqlalchemy.ext.declarative import declarative_base

# pylint: skip-file

uniswap_v3_metadata = MetaData(schema="uniswap_v3")
UniswapV3Base = declarative_base(metadata=uniswap_v3_metadata)


class UniV3SwapLogs(UniswapV3Base):
    __tablename__ = "swap_logs"
    swap_id = Column(VARCHAR(32), primary_key=True)
    pool_id = Column(VARCHAR(42), nullable=False)
    write_timestamp = Column(DateTime, nullable=False, default=datetime.datetime.now())
    token_in_symbol = Column(VARCHAR(8), nullable=False)
    token_in_amount = Column(Numeric, nullable=False)
    token_out_symbol = Column(VARCHAR(8), nullable=False)
    token_out_amount = Column(Numeric, nullable=False)
    pool_start_price = Column(Numeric, nullable=False)  # uint160
    pool_end_price = Column(Numeric, nullable=False)
    fill_price_token_0 = Column(Numeric, nullable=False)
    fill_price_token_1 = Column(Numeric, nullable=False)
    fee_token = Column(VARCHAR(8), nullable=False)
    fee_amount = Column(Numeric, nullable=False)


class UniV3PositionLogs(UniswapV3Base):
    __tablename__ = "position_logs"
    pool_id = Column(VARCHAR(42), nullable=False)
    block_number = Column(Integer, nullable=False)
    lp_address = Column(VARCHAR(42), nullable=False)
    tick_lower = Column(Integer, nullable=False)
    tick_upper = Column(Integer, nullable=False)
    currently_active = Column(Boolean, nullable=False)
    token_0_value = Column(Numeric, nullable=False)  # raw uint256 token amounts
    token_1_value = Column(Numeric, nullable=False)
    token_0_value_usd = Column(
        Numeric, nullable=True
    )  # Generated from the current spot price of the pool
    token_1_value_usd = Column(Numeric, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint(
            "pool_id", "block_number", "lp_address", "tick_lower", "tick_upper"
        ),
    )


class UniswapV3Events(UniswapV3Base):
    __abstract__ = True
    block_number = Column(Integer, nullable=False)
    log_index = Column(Integer, nullable=False)
    transaction_hash = Column(VARCHAR(66), nullable=False)
    contract_address = Column(VARCHAR(42), nullable=False)

    __table_args__ = (PrimaryKeyConstraint("block_number", "log_index"),)


class UniswapV3MintEventsModel(UniswapV3Events):
    __tablename__ = "mint_events"

    sender = Column(VARCHAR(42), nullable=False)
    owner = Column(VARCHAR(42), nullable=False)
    tick_lower = Column(Integer)
    tick_upper = Column(Integer)
    amount = Column(Numeric(80, 0))
    amount_0 = Column(Numeric(80, 0))
    amount_1 = Column(Numeric(80, 0))


class UniswapV3CollectEventsModel(UniswapV3Events):
    __tablename__ = "collect_events"

    owner = Column(VARCHAR(42))
    recipient = Column(VARCHAR(42))
    tick_lower = Column(Integer)
    tick_upper = Column(Integer)
    amount_0 = Column(Numeric(80, 0))
    amount_1 = Column(Numeric(80, 0))


class UniswapV3BurnEventsModel(UniswapV3Events):
    __tablename__ = "burn_events"

    owner = Column(VARCHAR(42))
    tick_lower = Column(Integer)
    tick_upper = Column(Integer)
    amount = Column(Numeric(80, 0))
    amount_0 = Column(Numeric(80, 0))
    amount_1 = Column(Numeric(80, 0))


class UniswapV3SwapEventsModel(UniswapV3Events):
    __tablename__ = "swap_events"

    sender = Column(VARCHAR(42))
    recipient = Column(VARCHAR(42))
    amount_0 = Column(Numeric(80, 0))
    amount_1 = Column(Numeric(80, 0))
    sqrt_price = Column(Numeric(50, 0))
    liquidity = Column(Numeric(40, 0))
    tick = Column(Integer)


class UniswapV3FlashEventsModel(UniswapV3Events):
    __tablename__ = "flash_events"

    sender = Column(VARCHAR(42))
    recipient = Column(VARCHAR(42))
    amount_0 = Column(Numeric(80, 0))
    amount_1 = Column(Numeric(80, 0))
    paid_0 = Column(Numeric(80, 0))
    paid_1 = Column(Numeric(80, 0))
