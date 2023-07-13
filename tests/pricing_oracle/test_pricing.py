import logging
import os
from decimal import Decimal

import pytest
from eth_utils import to_checksum_address as tca
from web3 import Web3

from python_eth_amm import PoolFactory
from python_eth_amm.events import backfill_events, query_events_from_db
from python_eth_amm.pricing_oracle.db import BackfilledPools, TokenPrices
from python_eth_amm.uniswap_v3 import UniswapV3Pool
from python_eth_amm.uniswap_v3.db import UniV3SwapEvent, _parse_uniswap_events

from ..utils import TEST_LOGGER

WETH_ADDRESS = tca("0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2")
WETH_USDC_POOL = tca("0x8ad599c3a0ff1de082011efddc58f1908eb6e6d8")

UNI_TOKEN = tca("0x1f9840a85d5af5bf1d1762f925bdaddc4201f984")
UNI_USDC_POOL = tca("0xd0fc8ba7e267f2bc56044a7715a489d851dc6d78")

WBTC_WETH_POOL = tca("0xcbcdf9626bc03e24f779434178a73a0b4bad62ed")

DAI_ETH_POOL = tca("0x60594a405d53811d3bc4766596efd80fd545a270")

WBTC_USDC_POOL = tca("0x99ac8ca7087fa4a2a1fb6357269965a2014abc35")
WBTC_ADDRESS = tca("0x2260fac5e5542a773aa44fbcfedf7c193bc2c599")

LINK_TOKEN = tca("0x514910771af9ca656af840dff83e8264ecf986ca")
LINK_USDC_POOL = tca("0xfad57d2039c21811c8f2b5d5b65308aa99d31559")


class TestFetchPriceForPool:
    def test_fetch_last_event_per_block(self, w3_archive_node, initialize_empty_oracle):
        oracle = initialize_empty_oracle()

        dai_eth_pool = w3_archive_node.eth.contract(
            address=DAI_ETH_POOL, abi=UniswapV3Pool.get_abi()
        )

        backfill_events(
            contract=dai_eth_pool,
            event_name="Swap",
            db_session=oracle.db_session,
            db_model=UniV3SwapEvent,
            model_parsing_func=_parse_uniswap_events,
            from_block=12375738,
            to_block=12400000,
            logger=oracle.logger,
        )

        raw_events = query_events_from_db(
            db_session=oracle.db_session,
            db_model=UniV3SwapEvent,
            from_block=12_300_000,
            to_block=12_400_000,
            contract_address=DAI_ETH_POOL,
        )

        events_by_blocks = oracle._fetch_last_event_for_blocks(
            from_block=12_300_000,
            to_block=12_400_000,
            pool_id=DAI_ETH_POOL,
        )

        assert len(raw_events) == 1919
        assert len(events_by_blocks) == 1781

        assert events_by_blocks[0][0] == 12375769
        assert events_by_blocks[0][1] == Decimal("1355158458637472828653342134")

        assert events_by_blocks[-1][0] == 12399949
        assert events_by_blocks[-1][1] == Decimal("1269440327112981924293855287")

    def test_fetch_price_for_WBTC_WETH_POOL_no_existing_events(
        self, initialize_empty_oracle
    ):
        oracle = initialize_empty_oracle()

        oracle.db_session.query(UniV3SwapEvent).filter(
            UniV3SwapEvent.contract_address == WBTC_USDC_POOL,
            UniV3SwapEvent.block_number < 12_500_000,
        ).delete()

        oracle.db_session.commit()

        oracle._fetch_price_from_pool(
            pool_id=WBTC_USDC_POOL,
            to_block=12_500_000,
        )
        prices = (
            oracle.db_session.query(TokenPrices)
            .filter(TokenPrices.token_id == WBTC_ADDRESS)
            .all()
        )

        assert abs(prices[10].spot_price - 57_300) < 200  # May 5th price +- $200
        assert abs(prices[-1].spot_price - 38_750) < 200  # May 24th price +- $200

    def test_fetch_price_for_WBTC_WETH_POOL_with_existing_events(
        self, initialize_empty_oracle, delete_prices_for_token, delete_backfill_for_pool
    ):
        pass

    def test_querying_non_usdc_pool_raises(self, initialize_empty_oracle):
        oracle = initialize_empty_oracle()
        with pytest.raises(ValueError) as exc:
            oracle._fetch_price_from_pool(
                pool_id=WBTC_WETH_POOL,
                to_block=12_500_000,
            )

            assert exc == "Pool must be USDC denominated"


class TestBackfillPrices:
    def test_querying_pool_raises_already_backfilled(
        self,
        initialize_empty_oracle,
        caplog,
    ):
        oracle = initialize_empty_oracle()

        oracle.db_session.query(UniV3SwapEvent).filter(
            UniV3SwapEvent.contract_address == LINK_USDC_POOL
        ).delete()

        oracle.db_session.commit()

        oracle._fetch_price_from_pool(LINK_USDC_POOL, to_block=12_500_000)

        backfill = (
            oracle.db_session.query(BackfilledPools)
            .filter(BackfilledPools.pool_id == LINK_USDC_POOL)
            .first()
        )

        assert backfill.backfill_start == 12_390_598
        assert backfill.backfill_end == 12_500_000

        with caplog.at_level(logging.INFO):
            oracle._fetch_price_from_pool(LINK_USDC_POOL, to_block=12_500_000)

        assert "Block range already backfilled.  Skipping price query" in [
            record.message for record in caplog.records
        ]

        assert (
            backfill
            == oracle.db_session.query(BackfilledPools)
            .filter(BackfilledPools.pool_id == LINK_USDC_POOL)
            .first()
        )

    def test_fetch_weth_price_dataframe(self, initialize_empty_oracle):
        oracle = initialize_empty_oracle()

        oracle.backfill_prices(WETH_ADDRESS, end=13_000_000)

        prices = oracle.get_price_over_time(WETH_ADDRESS)
        print(prices)

        assert False

    def test_fetch_uni_price(
        self,
        initialize_empty_oracle,
    ):
        oracle = initialize_empty_oracle()

        oracle.backfill_prices(UNI_TOKEN, end=13_000_000)

        prices = oracle.get_price_over_time(UNI_TOKEN)

        pool_backfill = (
            oracle.db_session.query(BackfilledPools)
            .filter(
                BackfilledPools.pool_id == UNI_USDC_POOL,
            )
            .scalar()
        )

        assert pool_backfill.backfill_start == 12369739
        assert pool_backfill.backfill_end == 13000000

    def test_backfill_invalid_range_raises(self, initialize_empty_oracle):
        oracle = initialize_empty_oracle()

        with pytest.raises(ValueError):
            oracle.backfill_prices(UNI_TOKEN, start=13_000_000, end=12_000_000)

        with pytest.raises(ValueError):
            oracle.backfill_prices(UNI_TOKEN, start=1_000_000, end=2_000_000)

        with pytest.raises(ValueError):
            oracle.backfill_prices(UNI_TOKEN, start=14_000_000, end=14_000_000)


class TestUpdatePrices:
    FACTORY = PoolFactory(
        sqlalchemy_uri=os.environ.get("SQLALCHEMY_DB_URI", "sqlite:///:memory:"),
        w3=Web3(Web3.HTTPProvider(os.environ["ARCHIVE_NODE_RPC_URL"])),
        logger=TEST_LOGGER,
    )

    def test_update_weth_price(self, initialize_empty_oracle):
        oracle = self.FACTORY.initialize_pricing_oracle()
        current_block = oracle.w3.eth.block_number

        oracle.backfill_prices(
            WETH_ADDRESS, start=current_block - 500, end=current_block - 20
        )

        pool_backfill = (
            oracle.db_session.query(BackfilledPools)
            .filter(BackfilledPools.pool_id == WETH_USDC_POOL)
            .scalar()
        )

        assert pool_backfill.backfill_end == current_block - 20
        assert pool_backfill.backfill_start == current_block - 500

        oracle.update_price_feeds()

        pool_backfill = (
            oracle.db_session.query(BackfilledPools)
            .filter(BackfilledPools.pool_id == WETH_USDC_POOL)
            .scalar()
        )

        assert pool_backfill.backfill_end >= current_block
        assert pool_backfill.backfill_start == current_block - 500

    def test_update_multiple_prices_with_an_old_backfill(self, caplog):
        oracle = self.FACTORY.initialize_pricing_oracle()

        current_block = oracle.w3.eth.block_number

        oracle.backfill_prices(
            WETH_ADDRESS, start=current_block - 500, end=current_block - 20
        )

        oracle.backfill_prices(
            UNI_TOKEN,
            start=current_block - 1_005_000,
            end=current_block - 1_000_000,
        )

        with caplog.at_level(logging.WARNING):
            oracle.update_price_feeds()

        expected_error = (
            "Skipping price update for 0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984 "
            "as the last backfill was more than 1 week ago."
            "To update the price, run the backfill_prices() method for the token "
            "before attempting to update"
        )

        assert expected_error in [record.message for record in caplog.records]

        weth_backfill = (
            oracle.db_session.query(BackfilledPools)
            .filter(BackfilledPools.pool_id == WETH_USDC_POOL)
            .scalar()
        )

        assert weth_backfill.backfill_end >= current_block
        assert weth_backfill.backfill_start == current_block - 500

        uni_backfill = (
            oracle.db_session.query(BackfilledPools)
            .filter(BackfilledPools.pool_id == UNI_USDC_POOL)
            .scalar()
        )

        assert uni_backfill.backfill_start == current_block - 1_005_000
        assert uni_backfill.backfill_end == current_block - 1_000_000
