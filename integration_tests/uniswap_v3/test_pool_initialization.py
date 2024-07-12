import json

from click.testing import CliRunner

from nethermind.entro.uniswap_v3 import UniswapV3Pool
from tests.resources.addresses import USDC_WETH_UNI_V3_POOL


class TestSavePool:
    def test_save_and_load_pool(
        self,
        eth_archival_w3,
        integration_db_session,
        integration_postgres_db,
        create_debug_logger,
    ):
        runner = CliRunner()
        pool = UniswapV3Pool.from_chain(
            w3=eth_archival_w3,
            db_session=integration_db_session,
            pool_address=USDC_WETH_UNI_V3_POOL,
            at_block=12380000,
            init_mode="load_liquidity",
        )

        with runner.isolated_filesystem():
            with open("test_save_pool.json", "w") as f:
                pool.save_pool(file_path=f)

            with open("test_save_pool.json", "r") as f:
                pool_state = json.load(fp=f)

            assert pool_state["slot0"]["sqrt_price"] == pool.slot0.sqrt_price
            assert pool_state["slot0"]["tick"] == pool.slot0.tick

            assert len(pool_state["ticks"]) == len(pool.ticks)
            assert len(pool_state["observations"]) == len(pool.observations)
            assert len(pool_state["positions"]) == len(pool.positions)

            with open("test_save_pool.json", "r") as f:
                loaded_pool = UniswapV3Pool.load_pool(
                    file_path=f,
                    w3=eth_archival_w3,
                )

            assert loaded_pool.immutables.pool_address == USDC_WETH_UNI_V3_POOL
