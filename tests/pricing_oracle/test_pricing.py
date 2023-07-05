from decimal import Decimal

import pytest
from eth_utils import to_checksum_address as tca

from python_eth_amm.events import backfill_events, query_events_from_db
from python_eth_amm.exceptions import OracleError
from python_eth_amm.pricing_oracle.db import BackfilledPools, TokenPrices
from python_eth_amm.uniswap_v3 import UniswapV3Pool
from python_eth_amm.uniswap_v3.db import UniV3SwapEvent, _parse_uniswap_events

WETH_ADDRESS = tca("0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2")


class TestFetchPriceForPool:
    def test_fetch_last_event_per_block(self, w3_archive_node, initialize_empty_oracle):
        oracle = initialize_empty_oracle()
        DAI_ETH_POOL = tca("0x60594a405d53811d3bc4766596efd80fd545a270")

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

    def test_fetch_price_for_wbtc_weth_pool(self, initialize_empty_oracle):
        wbtc_usdc_pool = tca("0x99ac8ca7087fa4a2a1fb6357269965a2014abc35")
        wbtc_address = tca("0x2260fac5e5542a773aa44fbcfedf7c193bc2c599")
        oracle = initialize_empty_oracle()

        oracle.db_session.query(BackfilledPools).filter(
            BackfilledPools.pool_id == wbtc_usdc_pool
        ).delete()
        oracle.db_session.query(TokenPrices).filter(
            TokenPrices.token_id == wbtc_address
        ).delete()
        oracle.db_session.query(UniV3SwapEvent).filter(
            UniV3SwapEvent.contract_address == wbtc_usdc_pool,
            UniV3SwapEvent.block_number < 12_500_000,
        ).delete()

        oracle.db_session.commit()

        oracle._fetch_price_from_pool(
            pool_id=wbtc_usdc_pool,
            to_block=12_500_000,
        )

        prices = (
            oracle.db_session.query(TokenPrices)
            .filter(TokenPrices.token_id == wbtc_address)
            .all()
        )
        for data in prices:
            print(data.spot_price)

    def test_querying_non_usdc_pool_raises(self, initialize_empty_oracle):
        wbtc_weth_pool = tca("0xcbcdf9626bc03e24f779434178a73a0b4bad62ed")

        oracle = initialize_empty_oracle()
        with pytest.raises(ValueError) as exc:
            oracle._fetch_price_from_pool(
                pool_id=wbtc_weth_pool,
                to_block=12_500_000,
            )

            assert exc == "Pool must be USDC denominated"


class TestBackfillPrices:
    def test_querying_weth_pool_raises_already_backfilled(
        self, initialize_empty_oracle
    ):
        usdc_weth_100_bps_pool = tca("0x7bea39867e4169dbe237d55c8242a8f2fcdcc387")

        oracle = initialize_empty_oracle()
        with pytest.raises(OracleError) as exc:
            oracle._fetch_price_from_pool(usdc_weth_100_bps_pool, 12_500_000)

            assert str(exc) == "Token Price already backfilled"

    def test_fetch_weth_price_dataframe(self, initialize_empty_oracle):
        oracle = initialize_empty_oracle()

        oracle.backfill_prices(WETH_ADDRESS, end=13_000_000)

        prices = oracle.get_price_over_time(WETH_ADDRESS)
        print(prices)

        assert False

    def test_fetch_uni_price(self, initialize_empty_oracle):
        UNI_TOKEN = tca("0x1f9840a85d5af5bf1d1762f925bdaddc4201f984")

        oracle = initialize_empty_oracle()

        oracle.backfill_prices(UNI_TOKEN, end=13_000_000)

        prices = oracle.get_price_over_time()

        assert True

        pool_backfill = (
            oracle.db_session.query(BackfilledPools)
            .filter(
                BackfilledPools.pool_id == "0x1d42064Fc4Beb5F8aAF85F4617AE8b3b5B8Bd801"
            )
            .scalar()
        )

        assert pool_backfill is not None

        assert pool_backfill.backfill_start == 12369739
        assert pool_backfill.backfill_end == 13000000
