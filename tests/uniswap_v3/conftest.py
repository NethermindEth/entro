from typing import Optional, Tuple

import pytest
from eth_typing import ChecksumAddress
from eth_utils import to_checksum_address

from nethermind.entro.uniswap_v3 import UniswapV3Pool

from .utils import MAX_TICK, MIN_TICK, encode_sqrt_price


@pytest.fixture(name="initialize_empty_pool")
def fixture_initialize_empty_pool():
    def _initialize_empty_pool(
        tick_spacing: Optional[int] = 60,
        fee: Optional[int] = 3_000,
        **kwargs,
    ):
        return UniswapV3Pool(
            tick_spacing=tick_spacing,
            initial_block=10_000_000,
            fee=fee,
            **kwargs,
        )

    return _initialize_empty_pool


@pytest.fixture(name="initialize_mint_test_pool")
def fixture_initialize_mint_test_pool(random_address):
    def _initialize_mint_test_pool(tick_spacing: int, **kwargs) -> Tuple[UniswapV3Pool, ChecksumAddress]:
        minter_address = random_address()

        mint_test_pool = UniswapV3Pool(
            tick_spacing=tick_spacing,
            initial_price=encode_sqrt_price(1, 10),
            initial_block=10_000_000,
            **kwargs,
        )

        mint_test_pool.mint(minter_address, MIN_TICK[tick_spacing], MAX_TICK[tick_spacing], 3161)
        return mint_test_pool, minter_address

    return _initialize_mint_test_pool


@pytest.fixture(name="initialize_burn_test_pool")
def fixture_initialize_burn_test_pool():
    def _initialize_burn_test_pool(**kwargs):
        return UniswapV3Pool(
            tick_spacing=60,
            initial_price=encode_sqrt_price(1, 10),
            initial_block=10_000_000,
            **kwargs,
        )

    return _initialize_burn_test_pool
