import datetime
from typing import List, Optional, Tuple, Union

import sqlalchemy
from eth_typing import ChecksumAddress
from eth_utils import to_checksum_address
from pandas import DataFrame

from python_eth_amm.events import backfill_events
from python_eth_amm.exceptions import PriceBackfillError
from python_eth_amm.uniswap_v3 import UniswapV3Pool

from .db import (
    LAST_EVENT_PER_BLOCK_QUERY,
    BackfilledPools,
    BlockTimestamps,
    TokenPrices,
    UniV3PoolCreations,
    _parse_pool_creation,
)

# pylint-disable: invalid-name

WETH_ADDRESS = to_checksum_address("0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2")
USDC_ADDRESS = to_checksum_address("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48")

POOL_CREATED_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": True,
                "internalType": "address",
                "name": "token0",
                "type": "address",
            },
            {
                "indexed": True,
                "internalType": "address",
                "name": "token1",
                "type": "address",
            },
            {
                "indexed": True,
                "internalType": "uint24",
                "name": "fee",
                "type": "uint24",
            },
            {
                "indexed": False,
                "internalType": "int24",
                "name": "tickSpacing",
                "type": "int24",
            },
            {
                "indexed": False,
                "internalType": "address",
                "name": "pool",
                "type": "address",
            },
        ],
        "name": "PoolCreated",
        "type": "event",
    },
]


class PricingOracle:
    _weth_prices: Optional[DataFrame] = None

    def __init__(
        self,
        pool_factory,
        timestamp_resolution: int,
    ):
        self.factory = pool_factory
        self.w3 = pool_factory.w3
        self.db_session = pool_factory.create_db_session()
        self.logger = pool_factory.logger
        self.timestamp_resolution = timestamp_resolution

        self._initialize_timestamp_converter()
        self._migrate_up()
        self._generate_pool_list()

    def _initialize_timestamp_converter(self):
        last_db_block = (
            self.db_session.query(BlockTimestamps)
            .order_by(BlockTimestamps.block_number.desc())
            .first()
        )

        timestamps = []
        for block in range(
            last_db_block.block_number + self.timestamp_resolution
            if last_db_block
            else 0,
            self.w3.eth.block_number,
            self.timestamp_resolution,
        ):
            timestamp = self.w3.eth.get_block(block if block != 0 else 1).timestamp
            timestamps.append(
                BlockTimestamps(
                    block_number=block,
                    timestamp=datetime.datetime.fromtimestamp(
                        timestamp, tz=datetime.timezone.utc
                    ),
                )
            )

        self.db_session.bulk_save_objects(timestamps)
        self.db_session.commit()

        self._timestamps = {}
        for row in self.db_session.query(BlockTimestamps).all():
            self._timestamps.update({row.block_number: row.timestamp})

    def _generate_pool_list(self):
        backfill_events(
            contract=self.w3.eth.contract(
                to_checksum_address("0x1F98431c8aD98523631AE4a59f267346ea31F984"),
                abi=POOL_CREATED_ABI,
            ),
            event_name="PoolCreated",
            db_session=self.db_session,
            db_model=UniV3PoolCreations,
            model_parsing_func=_parse_pool_creation,
            from_block=12369621,
            to_block=self.w3.eth.block_number,
            logger=self.logger,
            chunk_size=500_000,
        )
        self._v3_pools = DataFrame.from_records(
            [row.__dict__ for row in self.db_session.query(UniV3PoolCreations).all()]
        )
        self._v3_pools.drop(
            columns=["_sa_instance_state", "transaction_hash", "log_index"],
            inplace=True,
        )

    def _migrate_up(self):
        # pylint: disable=import-outside-toplevel
        from python_eth_amm.pricing_oracle.db import OracleBase, OracleEventBase

        db_engine = self.db_session.get_bind()

        conn = db_engine.connect()
        if not conn.dialect.has_schema(conn, "pricing_oracle"):
            conn.execute(sqlalchemy.schema.CreateSchema("pricing_oracle"))
            conn.commit()

        OracleBase.metadata.create_all(bind=db_engine)
        OracleEventBase.metadata.create_all(bind=db_engine)

    def _compute_backfill_ranges(
        self,
        pool_id: ChecksumAddress,
        from_block: Union[int, None],
        to_block: Union[int, None],
    ) -> List[Tuple[int, int]]:
        """
        Compute the backfill ranges for a given pool_id and block range.
        :param pool_id: 
            Pool ID to backfill
        :param from_block: 
            Inclusive Start block for backfill
        :param to_block: 
            Exclusive End block for backfill
        :return: 
            Tuple of backfill_start, backfill_end.  If backfill_end is None, then the backfill is not required and
            and can safely be skipped
        """
        old_backfill = (
            self.db_session.query(BackfilledPools)
            .filter(BackfilledPools.pool_id == pool_id)
            .scalar()
        )

        pool_init_block = (
            self.db_session.query(UniV3PoolCreations)
            .filter(UniV3PoolCreations.pool_address == pool_id)
            .first()
            .block_number
        )
        current_block = self.w3.eth.block_number
        if from_block is None or from_block < pool_init_block:
            from_block = pool_init_block

        if to_block is None or to_block > current_block:
            to_block = current_block

        if from_block >= to_block:
            return []

        if old_backfill is None:
            return [(from_block, to_block)]

        if (
            from_block >= old_backfill.backfill_start
            and to_block <= old_backfill.backfill_end
        ):
            return []

        if from_block < old_backfill.backfill_start:
            if to_block <= old_backfill.backfill_end:
                return [(from_block, old_backfill.backfill_start)]

            return [
                (from_block, old_backfill.backfill_start),
                (old_backfill.backfill_end, to_block),
            ]
        return [(old_backfill.backfill_end, to_block)]

    def _update_backfill(
        self, pool_id: ChecksumAddress, from_block: int, to_block: int
    ):
        backfill = (
            self.db_session.query(BackfilledPools)
            .filter(BackfilledPools.pool_id == pool_id)
            .scalar()
        )

        if backfill is None:
            backfill = BackfilledPools(
                pool_id=pool_id, backfill_start=from_block, backfill_end=to_block
            )
            self.db_session.add(backfill)

        else:
            if backfill.backfill_start == to_block:
                backfill.backfill_start = from_block
            elif backfill.backfill_end == from_block:
                backfill.backfill_end = to_block
            else:
                raise ValueError(
                    "Backfills Occurred out of Order,  Delete Events for Pool to Reset"
                )

        self.db_session.commit()

    def _fetch_last_event_for_blocks(
        self, from_block: int, to_block: int, pool_id: ChecksumAddress
    ):
        result = self.db_session.execute(
            sqlalchemy.text(LAST_EVENT_PER_BLOCK_QUERY),
            {"from_block": from_block, "to_block": to_block, "pool_id": pool_id},
        )

        return result.fetchall()

    def _fetch_price_from_pool(
        self,
        pool_id: ChecksumAddress,
        reference_token: Optional[ChecksumAddress] = USDC_ADDRESS,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None,
    ):
        backfills = self._compute_backfill_ranges(pool_id, from_block, to_block)

        self.logger.debug(f"Backfill Ranges: {backfills}")

        if not backfills:
            self.logger.info("Block range already backfilled.  Skipping price query")
            return

        pool: UniswapV3Pool = self.factory.initialize_from_chain(
            pool_type="uniswap_v3",
            pool_address=pool_id,
            initialization_args={"load_pool_state": False},
        )

        for backfill_start, backfill_end in backfills:
            self._run_backfill(
                backfill_start=backfill_start,
                backfill_end=backfill_end,
                v3_pool=pool,
                reference_token_num=0
                if pool.immutables.token_0.address == reference_token
                else 1,
            )

    def _get_weth_price(self, block_number: int) -> float:
        if self._weth_prices is None:
            self._weth_prices = self.get_price_over_time(WETH_ADDRESS)

        if self._weth_prices.tail(1).block_number < block_number:
            raise PriceBackfillError(
                f"WETH price not backfilled for block {block_number}"
            )
        return self._weth_prices.iloc[
            self._weth_prices.index.get_loc(block_number, method="ffill")
        ].spot_price

    def _run_backfill(
        self,
        backfill_start: int,
        backfill_end: int,
        v3_pool: UniswapV3Pool,
        reference_token_num: int,
    ):
        pricing_token, base_token = (
            (v3_pool.immutables.token_1, v3_pool.immutables.token_0)
            if reference_token_num == 0
            else (v3_pool.immutables.token_1, v3_pool.immutables.token_0)
        )

        weth_conversion = True if base_token.address == WETH_ADDRESS else False
        if not weth_conversion and base_token.address != USDC_ADDRESS:
            raise ValueError(f"Base Token {base_token.address} is not USDC or WETH")

        for one_month_chunk in range(backfill_start, backfill_end, 225_000):
            v3_pool.save_events(
                event_name="Swap",
                from_block=one_month_chunk + 1,
                to_block=min(one_month_chunk + 225_000, backfill_end),
            )
            db_models = []
            events = self._fetch_last_event_for_blocks(
                from_block=backfill_start,
                to_block=backfill_end,
                pool_id=v3_pool.immutables.pool_address,
            )
            for event in events:
                spot_price = v3_pool.get_price_at_sqrt_ratio(
                    int(event.sqrt_price), not bool(reference_token_num)
                )

                if weth_conversion:
                    spot_price *= self._get_weth_price(event.block_number)

                db_models.append(
                    TokenPrices(
                        token_id=pricing_token.address,
                        block_number=event.block_number,
                        spot_price=spot_price,
                    )
                )

            self.db_session.bulk_save_objects(db_models)
            self.db_session.commit()
        self._update_backfill(
            v3_pool.immutables.pool_address, backfill_start, backfill_end
        )

    def block_to_datetime(self, block_number: int) -> datetime.datetime:
        floor_num = block_number // self.timestamp_resolution
        if block_number % self.timestamp_resolution == 0:
            return self._timestamps[floor_num * self.timestamp_resolution]
        lower, upper = [
            self.timestamp_resolution * val for val in (floor_num, floor_num + 1)
        ]
        block_time = (
            self._timestamps[upper] - self._timestamps[lower]
        ) / self.timestamp_resolution

        return self._timestamps[lower] + ((block_number - lower) * block_time)

    def backfill_prices(self, token_id: ChecksumAddress, start_block: int):
        pass

    def get_price_at_block(self, block_number: int, token_id: ChecksumAddress):
        return (
            self.db_session.query(TokenPrices.spot_price)
            .filter(
                TokenPrices.token_id == token_id,
                TokenPrices.block_number <= block_number,
            )
            .order_by(TokenPrices.block_number.desc())
            .first()
        )

    def get_price_over_time(self, token_id: ChecksumAddress) -> DataFrame:
        data_dict = {"timestamp": [], "block_number": [], "spot_price": []}
        price_data = (
            self.db_session.query(TokenPrices.block_number, TokenPrices.spot_price)
            .filter(TokenPrices.token_id == token_id)
            .order_by(TokenPrices.block_number)
            .all()
        )

        for block_number, spot_price in price_data:
            data_dict["timestamp"].append(self.block_to_datetime(block_number))
            data_dict["block_number"].append(block_number)
            data_dict["spot_price"].append(float(spot_price))

        return DataFrame(data_dict)
