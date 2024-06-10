from typing import Sequence

from eth_typing import ChecksumAddress
from eth_utils import to_checksum_address as tca
from sqlalchemy import String, select
from sqlalchemy import text as encode_sql_text
from sqlalchemy.orm import Session

from nethermind.entro.database.models.prices import SUPPORTED_POOL_CREATION_EVENTS
from nethermind.entro.database.models.internal import BackfilledRange
from nethermind.entro.database.models.uniswap import UniV3PoolCreationEvent
from nethermind.entro.types.backfill import BackfillDataType, SupportedNetwork
from nethermind.entro.types.prices import SupportedPricingPool, TokenMarketInfo


def fetch_spot_price_per_block_for_market(
    self,
    market_id: ChecksumAddress,
    from_block: int,
    to_block: int,
) -> list[tuple[int, float]]:
    """
    Fetches the spot price for a market at each block in the range

    :param self:
    :param market_id:
    :param from_block:
    :param to_block:
    :return:
    """
    result = self.db_session.execute(
        encode_sql_text(
            """
                WITH added_row_number as (
                    SELECT
                        block_number,
                        spot_price,
                        ROW_NUMBER() OVER(PARTITION BY block_number ORDER BY transaction_index DESC) AS row_number
                    FROM pricing_oracle.market_spot_prices
                    WHERE
                        block_number >= :from_block AND
                        block_number < :to_block AND
                        market_address = :market_id
                    ) 
                SELECT 
                    block_number,
                    spot_price
                FROM added_row_number WHERE row_number=1
                ORDER BY block_number;
            """
        ),
        {"from_block": from_block, "to_block": to_block, "market_id": market_id},
    )

    return result.fetchall()


def get_pool_creation_backfills(
    db_session: Session,
    network: SupportedNetwork,
) -> Sequence[BackfilledRange]:
    """
    Returns all of the backfills for pool creations
    :param db_session:
    :param network:
    :return:
    """
    contracts = list(SUPPORTED_POOL_CREATION_EVENTS.keys())
    event_names = [x["event_name"] for x in SUPPORTED_POOL_CREATION_EVENTS.values()]

    select_stmt = select(BackfilledRange).filter(
        BackfilledRange.data_type == BackfillDataType.events.value,
        BackfilledRange.network == network.value,
        BackfilledRange.filter_data["contract_address"].cast(String).in_(contracts),
        BackfilledRange.filter_data["event_name"].cast(String).in_(event_names),
    )

    return db_session.execute(select_stmt).scalars().all()


def get_supported_markets(
    db_session: Session,
) -> dict[tuple[ChecksumAddress, ChecksumAddress], list[TokenMarketInfo]]:
    """
    Returns all of the supported markets
    :param db_session:
    :return:
    """
    markets = []
    output_market_info: dict[tuple[ChecksumAddress, ChecksumAddress], list[TokenMarketInfo]] = {}
    v3_pools = db_session.execute(select(UniV3PoolCreationEvent)).scalars().all()

    for v3_pool in v3_pools:
        markets.append(
            TokenMarketInfo(
                market_address=v3_pool.pool,
                token_0=v3_pool.token_0,
                token_1=v3_pool.token_1,
                pool_class=SupportedPricingPool.uniswap_v3,
                initialization_block=v3_pool.block_number,
                metadata={"fee": v3_pool.fee, "tick_spacing": v3_pool.tick_spacing},
            )
        )

    for market in markets:
        if int(market.token_0, 16) < int(market.token_1, 16):
            token_key = (tca(market.token_0), tca(market.token_1))
        else:
            token_key = (tca(market.token_1), tca(market.token_0))

        try:
            output_market_info[token_key].append(market)
        except KeyError:
            output_market_info.update({token_key: [market]})

    return output_market_info
