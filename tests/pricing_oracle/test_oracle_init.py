from python_eth_amm.pricing_oracle import PricingOracle


class TestPoolComputations:
    def test_pools_are_loaded(self, w3_archive_node, db_session, test_logger):
        oracle_instance = PricingOracle(
            w3=w3_archive_node, db_session=db_session, logger=test_logger
        )

        assert len(oracle_instance._v3_pools) > 0

        print(oracle_instance._v3_pools.columns)
        print(oracle_instance._v3_pools)
