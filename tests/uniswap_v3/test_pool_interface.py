import logging
from datetime import datetime

import pytest

from nethermind.entro.exceptions import UniswapV3Revert
from nethermind.entro.tokens.erc_20 import NULL_TOKEN
from nethermind.entro.uniswap_v3 import UniswapV3Pool
from nethermind.entro.uniswap_v3.chain_interface import _get_pos_from_bitmap
from nethermind.entro.uniswap_v3.math import MAX_SQRT_RATIO, MIN_SQRT_RATIO
from tests.uniswap_v3.utils import encode_sqrt_price


class TestPoolInitialization:
    def test_initiailizes_immutables(self):
        pool = UniswapV3Pool()
        assert pool.immutables.pool_address is not None
        assert pool.immutables.token_0 == NULL_TOKEN
        assert pool.immutables.token_1 == NULL_TOKEN
        assert pool.immutables.tick_spacing == 60
        assert pool.immutables.fee == 3000
        assert pool.immutables.max_liquidity_per_tick == 11505743598341114571880798222544994

    def test_initialization_args_are_passed_to_pool(self):
        pool = UniswapV3Pool(
            initial_price=encode_sqrt_price(1, 10),
            initial_block=12345,
            fee=500,
        )

        assert pool.immutables.fee == 500
        assert pool.immutables.tick_spacing == 10
        assert pool.immutables.token_0 == NULL_TOKEN
        assert pool.immutables.token_1 == NULL_TOKEN

        assert pool.slot0.sqrt_price == encode_sqrt_price(1, 10)

        assert pool.block_number == 12345
        assert pool.immutables.initialization_block is None
        assert pool.block_timestamp - datetime.now().timestamp() < 5

    def test_warning_is_raised_for_fee_tick_spacing_mismatch(self, caplog):
        with caplog.at_level(logging.WARN):
            UniswapV3Pool(fee=1000, tick_spacing=200)

        expected_warn = (
            "Tick spacing & Fee were both specified, but do not match typical values\tFee: 1000, Tick Spacing: 200"
        )
        assert expected_warn in [record.message for record in caplog.records]

    def test_raises_if_initialization_price_too_low(self):
        with pytest.raises(UniswapV3Revert):
            UniswapV3Pool(
                initial_price=MIN_SQRT_RATIO - 10,
            )

    def test_raises_if_initialization_price_too_high(self):
        with pytest.raises(UniswapV3Revert):
            UniswapV3Pool(initial_price=MAX_SQRT_RATIO + 10)


class TestTickBitmap:
    def test_bitmap_returns_none_on_zero(self):
        bitmap = int(("0" * 256), 2)
        assert _get_pos_from_bitmap(bitmap) == []

    def test_bitmap_returns_correct_number_of_bits(self, get_random_binary_string):
        bitmap = get_random_binary_string(256)
        tick_queue = _get_pos_from_bitmap(int(bitmap, 2))
        assert len(tick_queue) == bitmap.count("1")
