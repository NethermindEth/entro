import os

from eth_utils import to_checksum_address as tca

from python_eth_amm import PoolFactory
from python_eth_amm.pricing_oracle import PricingOracle


class TestPoolComputations:
    def test_pools_are_loaded(self, w3_archive_node, db_session, test_logger):
        pool_factory = PoolFactory(
            w3=w3_archive_node, sqlalchemy_uri=os.environ["SQLALCHEMY_DB_URI"]
        )

        oracle_instance = PricingOracle(
            pool_factory=pool_factory,
            timestamp_resolution=100_000,
        )

        pools = oracle_instance._v3_pools["pool_address"].tolist()

        assert tca("0xf4ad61db72f114be877e87d62dc5e7bd52df4d9b") in pools  # LDO-WETH
        assert tca("0x7bea39867e4169dbe237d55c8242a8f2fcdcc387") in pools  # USDC-WETH
        assert tca("0x99ac8ca7087fa4a2a1fb6357269965a2014abc35") in pools  # USDC-WBTC

        blocks = sorted(oracle_instance._v3_pools["block_number"].tolist())

        assert blocks[0] == 12369739
        assert blocks[-1] <= w3_archive_node.eth.block_number
