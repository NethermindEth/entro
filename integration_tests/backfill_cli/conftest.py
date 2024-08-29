import os
from typing import List

import pytest
from click.testing import CliRunner

from tests.resources.ABI import (
    ERC20_ABI_JSON,
    ERC721_ABI_JSON,
    UNISWAP_V2_PAIR_JSON,
    UNISWAP_V3_POOL_JSON,
)


@pytest.fixture
def cli_db_url(integration_db_url) -> List[str]:
    return ["--db-url", integration_db_url]


@pytest.fixture()
def eth_rpc_cli_config() -> List[str]:
    return [
        "--json-rpc",
        os.environ["ETH_JSON_RPC"],
    ]


@pytest.fixture()
def etherscan_cli_config() -> List[str]:
    return ["--etherscan-api-key", os.environ["ETHERSCAN_API_KEY"]]


@pytest.fixture()
def voyager_cli_config() -> List[str]:
    return ["--api-key", os.environ["VOYAGER_API_KEY"]]


@pytest.fixture()
def add_abis_to_db(cli_db_url):
    def _add_abis(cli_runner: CliRunner):
        from nethermind.entro.cli import entro_cli

        with cli_runner.isolated_filesystem():
            with open("ERC20.json", "w") as f:
                f.write(ERC20_ABI_JSON)
            with open("ERC721.json", "w") as f:
                f.write(ERC721_ABI_JSON)
            with open("UniswapV3Pool.json", "w") as f:
                f.write(UNISWAP_V3_POOL_JSON)
            with open("UniswapV2Pair.json", "w") as f:
                f.write(UNISWAP_V2_PAIR_JSON)

            erc20_abi = cli_runner.invoke(
                entro_cli,
                [
                    "add-abi",
                    "ERC20",
                    "ERC20.json",
                    "--priority",
                    "1000",
                    *cli_db_url,
                ],
            )
            assert erc20_abi.exit_code == 0
            erc_721_abi = cli_runner.invoke(
                entro_cli,
                [
                    "add-abi",
                    "ERC721",
                    "ERC721.json",
                    "--priority",
                    "1001",
                    *cli_db_url,
                ],
            )
            assert erc_721_abi.exit_code == 0
            uni_v2_abi = cli_runner.invoke(
                entro_cli,
                [
                    "add-abi",
                    "UniswapV2Pair",
                    "UniswapV2Pair.json",
                    "--priority",
                    "919",
                    *cli_db_url,
                ],
            )
            assert uni_v2_abi.exit_code == 0
            uni_v3_abi = cli_runner.invoke(
                entro_cli,
                [
                    "add-abi",
                    "UniswapV3Pool",
                    "UniswapV3Pool.json",
                    "--priority",
                    "920",
                    *cli_db_url,
                ],
            )

    return _add_abis
