import json

import pytest
from web3 import Web3

from tests.resources.ABI import UNISWAP_V3_POOL_JSON
from tests.resources.addresses import (
    USDC_WETH_UNI_V3_POOL,
    USDT_WETH_UNI_V3_POOL,
    WBTC_WETH_UNI_V3_POOL,
)

uni_v3_abi = json.loads(UNISWAP_V3_POOL_JSON)


@pytest.fixture()
def usdc_weth_contract(eth_archival_w3):
    return eth_archival_w3.eth.contract(
        address=USDC_WETH_UNI_V3_POOL,
        abi=uni_v3_abi,
    )


@pytest.fixture()
def wbtc_weth_contract(eth_archival_w3):
    return eth_archival_w3.eth.contract(
        address=WBTC_WETH_UNI_V3_POOL,
        abi=uni_v3_abi,
    )


@pytest.fixture()
def usdt_weth_contract(eth_archival_w3):
    return eth_archival_w3.eth.contract(
        address=USDT_WETH_UNI_V3_POOL,
        abi=uni_v3_abi,
    )
