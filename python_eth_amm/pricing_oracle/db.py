from typing import Any, Dict

from sqlalchemy import Column, Integer, MetaData, Numeric, PrimaryKeyConstraint, String
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm.decl_api import DeclarativeMeta
from web3.types import EventData

from python_eth_amm.events import EventBase

oracle_metadata = MetaData(schema="pricing_oracle")
OracleBase: DeclarativeMeta = declarative_base(metadata=oracle_metadata)

OracleEventBase = EventBase
OracleEventBase.metadata = oracle_metadata


LAST_EVENT_PER_BLOCK_QUERY = """
WITH added_row_number as (
    SELECT
        block_number,
        sqrt_price,
        ROW_NUMBER() OVER(PARTITION BY block_number ORDER BY log_index DESC) AS row_number
    FROM uniswap_v3.swap_events
    WHERE
        block_number >= :from_block AND
        block_number < :to_block AND
        contract_address = :pool_id
    ) 
SELECT 
    block_number,
    sqrt_price
FROM added_row_number WHERE row_number=1
ORDER BY block_number;
"""

# pylint: disable=missing-class-docstring


class BlockTimestamps(OracleBase):
    __tablename__ = "block_timestamps"

    block_number = Column(Integer, primary_key=True)
    timestamp = Column(Integer, nullable=False)


class TokenPrices(OracleBase):
    __tablename__ = "token_prices"

    token_id = Column(String, nullable=False)
    block_number = Column(Integer, nullable=False)
    spot_price = Column(Numeric, nullable=False)

    __table_args__ = (PrimaryKeyConstraint("token_id", "block_number"),)


class BackfilledPools(OracleBase):
    __tablename__ = "backfilled_pools"

    pool_id = Column(String, primary_key=True)
    backfill_start = Column(Integer, nullable=False)
    backfill_end = Column(Integer, nullable=False)


class UniV3PoolCreations(OracleEventBase):
    __tablename__ = "uni_v3_pool_creations"

    token_0 = Column(String, nullable=False)
    token_1 = Column(String, nullable=False)
    pool_address = Column(String, nullable=False)
    fee = Column(Integer, nullable=False)


def _parse_pool_creation(data: EventData, _) -> Dict[str, Any]:
    return {
        "block_number": data["blockNumber"],
        "log_index": data["logIndex"],
        "transaction_hash": data["transactionHash"].hex(),
        "contract_address": data["address"],
        "token_0": data["args"]["token0"],
        "token_1": data["args"]["token1"],
        "pool_address": data["args"]["pool"],
        "fee": data["args"]["fee"],
    }
