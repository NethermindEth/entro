import os

from eth_utils import to_checksum_address as tca
from sqlalchemy import create_engine
from sqlalchemy.orm import create_session
from web3 import Web3

from python_eth_amm import PoolFactory
from python_eth_amm.pricing_oracle import PricingOracle
from python_eth_amm.pricing_oracle.db import BackfilledPools


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


class TestComputeBackfillRanges:
    UNI_WETH_POOL = tca("0x1d42064fc4beb5f8aaf85f4617ae8b3b5b8bd801")

    FACTORY = PoolFactory(
        sqlalchemy_uri=os.environ.get("SQLALCHEMY_DB_URI", "sqlite:///:memory:"),
        w3=Web3(Web3.HTTPProvider(os.environ["ARCHIVE_NODE_RPC_URL"])),
    )

    def setup_class(self):
        db_session = create_session(
            bind=create_engine(
                os.environ.get("SQLALCHEMY_DB_URI", "sqlite:///:memory:")
            )
        )

        db_session.query(BackfilledPools).filter(
            BackfilledPools.pool_id == self.UNI_WETH_POOL
        ).delete()

        uni_weth_pool_backfill = BackfilledPools(
            pool_id=self.UNI_WETH_POOL,
            backfill_start=14_000_000,
            backfill_end=15_000_000,
        )
        db_session.add(uni_weth_pool_backfill)
        db_session.commit()

    def test_start_inside_end_inside(self, initialize_empty_oracle):
        oracle = initialize_empty_oracle(factory=self.FACTORY)
        backfills = oracle._compute_backfill_ranges(
            pool_id=self.UNI_WETH_POOL,
            from_block=14_500_000,
            to_block=14_600_000,
        )
        assert backfills == []

    def test_start_at_end_at(self, initialize_empty_oracle):
        oracle = initialize_empty_oracle(factory=self.FACTORY)
        backfills = oracle._compute_backfill_ranges(
            pool_id=self.UNI_WETH_POOL,
            from_block=14_000_000,
            to_block=15_000_000,
        )
        assert backfills == []

    def test_start_inside_end_after(self, initialize_empty_oracle):
        oracle = initialize_empty_oracle(factory=self.FACTORY)
        backfills = oracle._compute_backfill_ranges(
            pool_id=self.UNI_WETH_POOL,
            from_block=14_500_000,
            to_block=15_500_000,
        )

        assert len(backfills) == 1
        assert backfills[0][0] == 15_000_000
        assert backfills[0][1] == 15_500_000

    def test_start_before_end_inside(self, initialize_empty_oracle):
        oracle = initialize_empty_oracle(factory=self.FACTORY)
        backfills = oracle._compute_backfill_ranges(
            pool_id=self.UNI_WETH_POOL,
            from_block=13_500_000,
            to_block=14_500_000,
        )
        assert len(backfills) == 1
        assert backfills[0][0] == 13_500_000
        assert backfills[0][1] == 14_000_000

    def test_start_before_end_after(self, initialize_empty_oracle):
        oracle = initialize_empty_oracle(factory=self.FACTORY)
        backfills = oracle._compute_backfill_ranges(
            pool_id=self.UNI_WETH_POOL,
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
    ):
        oracle = initialize_empty_oracle(factory=self.FACTORY)

        backfills = oracle._compute_backfill_ranges(
            pool_id=self.UNI_WETH_POOL,
            from_block=0,
            to_block=oracle.w3.eth.block_number * 2,
        )

        assert len(backfills) == 2

        assert backfills[0][0] == 12369739
        assert backfills[0][1] == 14_000_000

        assert backfills[1][0] == 15_000_000
        assert abs(backfills[1][1] - oracle.w3.eth.block_number) < 10
