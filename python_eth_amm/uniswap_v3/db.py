import datetime
from typing import Any, Dict, Type

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
from sqlalchemy.orm.decl_api import DeclarativeMeta
from web3.types import EventData

from python_eth_amm.events import EventBase

# pylint: skip-file

uniswap_v3_metadata = MetaData(schema="uniswap_v3")
UniswapV3Base: DeclarativeMeta = declarative_base(metadata=uniswap_v3_metadata)
UniV3EventBase: DeclarativeMeta = EventBase
UniV3EventBase.metadata = uniswap_v3_metadata


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


class UniV3MintEvent(UniV3EventBase):
    __tablename__ = "mint_events"

    sender = Column(VARCHAR(42), nullable=False)
    owner = Column(VARCHAR(42), nullable=False)
    tick_lower = Column(Integer)
    tick_upper = Column(Integer)
    amount = Column(Numeric(80, 0))
    amount_0 = Column(Numeric(80, 0))
    amount_1 = Column(Numeric(80, 0))


class UniV3CollectEvent(UniV3EventBase):
    __tablename__ = "collect_events"

    owner = Column(VARCHAR(42))
    recipient = Column(VARCHAR(42))
    tick_lower = Column(Integer)
    tick_upper = Column(Integer)
    amount_0 = Column(Numeric(80, 0))
    amount_1 = Column(Numeric(80, 0))


class UniV3BurnEvent(UniV3EventBase):
    __tablename__ = "burn_events"

    owner = Column(VARCHAR(42))
    tick_lower = Column(Integer)
    tick_upper = Column(Integer)
    amount = Column(Numeric(80, 0))
    amount_0 = Column(Numeric(80, 0))
    amount_1 = Column(Numeric(80, 0))


class UniV3SwapEvent(UniV3EventBase):
    __tablename__ = "swap_events"

    sender = Column(VARCHAR(42))
    recipient = Column(VARCHAR(42))
    amount_0 = Column(Numeric(80, 0))
    amount_1 = Column(Numeric(80, 0))
    sqrt_price = Column(Numeric(50, 0))
    liquidity = Column(Numeric(40, 0))
    tick = Column(Integer)


class UniV3FlashEvent(UniV3EventBase):
    __tablename__ = "flash_events"

    sender = Column(VARCHAR(42))
    recipient = Column(VARCHAR(42))
    amount_0 = Column(Numeric(80, 0))
    amount_1 = Column(Numeric(80, 0))
    paid_0 = Column(Numeric(80, 0))
    paid_1 = Column(Numeric(80, 0))


EVENT_MODELS: Dict[str, Type[EventBase]] = {
    "Mint": UniV3MintEvent,
    "Collect": UniV3CollectEvent,
    "Burn": UniV3BurnEvent,
    "Swap": UniV3SwapEvent,
    "Flash": UniV3FlashEvent,
}


def _parse_uniswap_events(data: EventData, event_name: str) -> Dict[str, Any]:
    event = {
        "block_number": data["blockNumber"],
        "log_index": data["logIndex"],
        "transaction_hash": data["transactionHash"].hex(),
        "contract_address": data["address"],
        "amount_0": data["args"]["amount0"],
        "amount_1": data["args"]["amount1"],
    }

    match event_name:
        case "Swap":
            event.update(
                {
                    "sender": data["args"]["sender"],
                    "recipient": data["args"]["recipient"],
                    "sqrt_price": data["args"]["sqrtPriceX96"],
                    "liquidity": data["args"]["liquidity"],
                    "tick": data["args"]["tick"],
                }
            )
        case "Flash":
            event.update(
                {
                    "sender": data["args"]["sender"],
                    "recipient": data["args"]["recipient"],
                    "paid_0": data["args"]["paid0"],
                    "paid_1": data["args"]["paid1"],
                }
            )
        case "Mint":
            event.update(
                {
                    "owner": data["args"]["owner"],
                    "tick_lower": data["args"]["tickLower"],
                    "tick_upper": data["args"]["tickUpper"],
                    "amount": data["args"]["amount"],
                    "sender": data["args"]["sender"],
                }
            )
        case "Burn":
            event.update(
                {
                    "owner": data["args"]["owner"],
                    "tick_lower": data["args"]["tickLower"],
                    "tick_upper": data["args"]["tickUpper"],
                    "amount": data["args"]["amount"],
                }
            )

        case "Collect":
            event.update(
                {
                    "owner": data["args"]["owner"],
                    "tick_lower": data["args"]["tickLower"],
                    "tick_upper": data["args"]["tickUpper"],
                    "recipient": data["args"]["recipient"],
                }
            )

        case _:
            raise ValueError(f"Cannot parse invalid event type: {event_name}")

    return event
