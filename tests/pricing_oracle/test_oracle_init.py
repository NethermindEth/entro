import os

from eth_utils import to_checksum_address as tca
from web3 import Web3

from python_eth_amm import PoolFactory
from python_eth_amm.pricing_oracle import PricingOracle

LINK_TOKEN = tca("0x514910771af9ca656af840dff83e8264ecf986ca")
LINK_USDC_POOL = tca("0xfad57d2039c21811c8f2b5d5b65308aa99d31559")

WETH_ADDRESS = tca("0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2")


class TestPoolComputations:
    def test_pools_are_loaded(self, w3_archive_node, db_session, test_logger):
        pool_factory = PoolFactory(
            w3=w3_archive_node, sqlalchemy_uri=os.environ["SQLALCHEMY_DB_URI"]
        )

        oracle_instance = PricingOracle(
            factory=pool_factory,
            timestamp_resolution=100_000,
        )

        pools = oracle_instance._v3_pools["pool_address"].tolist()

        assert tca("0xf4ad61db72f114be877e87d62dc5e7bd52df4d9b") in pools  # LDO-WETH
        assert tca("0x7bea39867e4169dbe237d55c8242a8f2fcdcc387") in pools  # USDC-WETH
        assert tca("0x99ac8ca7087fa4a2a1fb6357269965a2014abc35") in pools  # USDC-WBTC

        blocks = sorted(oracle_instance._v3_pools["block_number"].tolist())

        assert blocks[0] == 12369739
        assert blocks[-1] <= w3_archive_node.eth.block_number

    def test_pool_usdc_pathing(self, initialize_empty_oracle):
        oracle = initialize_empty_oracle()
        pool_address, weth_conversion = oracle._fetch_token_pool(WETH_ADDRESS)

        assert pool_address == tca("0x8ad599c3a0ff1de082011efddc58f1908eb6e6d8")
        assert not weth_conversion

    def test_pool_weth_pathing(self, initialize_empty_oracle):
        oracle = initialize_empty_oracle()

        pool_address, weth_conversion = oracle._fetch_token_pool(
            tca("0x5aaEFe84E0fB3DD1f0fCfF6fA7468124986B91bd")
        )

        assert pool_address == tca("0xf25B7A9ba9321F9Bb587571ff266330327Bf30d9")
        assert weth_conversion


class TestComputeBackfillRanges:
    FACTORY = PoolFactory(
        sqlalchemy_uri=os.environ.get("SQLALCHEMY_DB_URI", "sqlite:///:memory:"),
        w3=Web3(Web3.HTTPProvider(os.environ["ARCHIVE_NODE_RPC_URL"])),
    )

    def test_start_inside_end_inside(self, initialize_empty_oracle, add_test_backfill):
        oracle = initialize_empty_oracle(factory=self.FACTORY)
        add_test_backfill()

        backfills = oracle._compute_backfill_ranges(
            pool_id=LINK_USDC_POOL,
            from_block=14_500_000,
            to_block=14_600_000,
        )
        assert backfills == []

    def test_start_at_end_at(self, initialize_empty_oracle, add_test_backfill):
        oracle = initialize_empty_oracle(factory=self.FACTORY)
        add_test_backfill()

        backfills = oracle._compute_backfill_ranges(
            pool_id=LINK_USDC_POOL,
            from_block=14_000_000,
            to_block=15_000_000,
        )
        assert backfills == []

    def test_start_inside_end_after(self, initialize_empty_oracle, add_test_backfill):
        oracle = initialize_empty_oracle(factory=self.FACTORY)
        add_test_backfill()

        backfills = oracle._compute_backfill_ranges(
            pool_id=LINK_USDC_POOL,
            from_block=14_500_000,
            to_block=15_500_000,
        )

        assert len(backfills) == 1
        assert backfills[0][0] == 15_000_000
        assert backfills[0][1] == 15_500_000

    def test_start_before_end_inside(self, initialize_empty_oracle, add_test_backfill):
        oracle = initialize_empty_oracle(factory=self.FACTORY)
        add_test_backfill()

        backfills = oracle._compute_backfill_ranges(
            pool_id=LINK_USDC_POOL,
            from_block=13_500_000,
            to_block=14_500_000,
        )
        assert len(backfills) == 1
        assert backfills[0][0] == 13_500_000
        assert backfills[0][1] == 14_000_000

    def test_start_before_end_after(self, initialize_empty_oracle, add_test_backfill):
        oracle = initialize_empty_oracle(factory=self.FACTORY)
        add_test_backfill()

        backfills = oracle._compute_backfill_ranges(
            pool_id=LINK_USDC_POOL,
            from_block=13_500_000,
            to_block=15_500_000,
        )
        assert len(backfills) == 2

        assert backfills[0][0] == 13_500_000
        assert backfills[0][1] == 14_000_000

        assert backfills[1][0] == 15_000_000
        assert backfills[1][1] == 15_500_000

    def test_start_at_0_end_above_current_block(
        self,
        initialize_empty_oracle,
        add_test_backfill,
    ):
        oracle = initialize_empty_oracle(factory=self.FACTORY)
        add_test_backfill()

        backfills = oracle._compute_backfill_ranges(
            pool_id=LINK_USDC_POOL,
            from_block=0,
            to_block=oracle.w3.eth.block_number * 2,
        )

        assert len(backfills) == 2

        assert backfills[0][0] == 12390598
        assert backfills[0][1] == 14_000_000

        assert backfills[1][0] == 15_000_000
        assert abs(backfills[1][1] - oracle.w3.eth.block_number) < 10
