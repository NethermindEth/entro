import datetime
import json
import os

import pytest

from python_eth_amm import PoolFactory
from python_eth_amm.base.token import ERC20Token
from python_eth_amm.exceptions import UniswapV3Revert
from python_eth_amm.lib.math import TickMathModule
from python_eth_amm.uniswap_v3 import UniswapV3Pool

from ..utils import TEST_LOGGER, expand_to_decimals
from .utils import MAX_TICK, MIN_TICK, encode_sqrt_price


class TestPoolInitialization:
    factory = PoolFactory(
        exact_math=True,
        logger=TEST_LOGGER,
        sqlalchemy_uri=os.environ["SQLALCHEMY_DB_URI"],
    )

    def test_initiailizes_immutables(self, initialize_empty_pool):
        pool = initialize_empty_pool(
            pool_factory=self.factory,
        )
        assert pool.immutables.pool_address is not None
        assert pool.immutables.token_0 == ERC20Token.default_token(0)
        assert pool.immutables.token_1 == ERC20Token.default_token(1)
        assert pool.immutables.tick_spacing == 60
        assert (
            pool.immutables.max_liquidity_per_tick
            == 11505743598341114571880798222544994
        )

    def test_initialize_with_valid_price(self, initialize_empty_pool):
        pool = initialize_empty_pool(
            pool_factory=self.factory, initial_price=encode_sqrt_price(1, 10)
        )
        assert pool.slot0.sqrt_price == encode_sqrt_price(1, 10)

    def test_raises_if_initialization_price_too_low(self):
        assert False  # TODO

    def test_raises_if_initialization_price_too_high(self):
        assert False  # TODO


class TestSavePool:
    def test_save_and_load_pool(self, exact_math_factory):
        pool = exact_math_factory.initialize_from_chain(
            "uniswap_v3", "0x8ad599c3a0ff1de082011efddc58f1908eb6e6d8", 12380000
        )
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
                file_path=f, pool_factory=exact_math_factory
            )

        os.remove("test_save_pool.json")


class TestObservations:
    def test_increase_observation_cardinality_sets_slot_0(self):
        pass

    def test_increase_observation_cardinality_does_not_set_lower_than_current(self):
        pass


@pytest.mark.parametrize("tick_spacing", [10, 60, 200])
class TestMint:
    factory = PoolFactory(
        exact_math=True,
        logger=TEST_LOGGER,
        sqlalchemy_uri=os.environ["SQLALCHEMY_DB_URI"],
    )

    def test_mint_fails_if_tick_lower_is_higher_than_tick_upper(
        self, initialize_empty_pool, random_address, tick_spacing
    ):
        with pytest.raises(UniswapV3Revert):
            pool = initialize_empty_pool(
                pool_factory=self.factory, tick_spacing=tick_spacing
            )
            pool.mint(
                random_address(),
                tick_lower=2 * tick_spacing,
                tick_upper=tick_spacing,
                amount=100,
            )

    def test_mint_fails_if_tick_lower_is_equal_to_tick_upper(
        self, initialize_empty_pool, random_address, tick_spacing
    ):
        with pytest.raises(UniswapV3Revert):
            pool = initialize_empty_pool(
                pool_factory=self.factory, tick_spacing=tick_spacing
            )
            pool.mint(
                random_address(),
                tick_lower=MIN_TICK[tick_spacing],
                tick_upper=MIN_TICK[tick_spacing],
                amount=100,
            )

    def test_mint_fails_if_tick_lower_less_than_min_tick(
        self, initialize_empty_pool, random_address, tick_spacing
    ):
        with pytest.raises(UniswapV3Revert):
            pool = initialize_empty_pool(
                pool_factory=self.factory, tick_spacing=tick_spacing
            )
            pool.mint(
                random_address(),
                tick_lower=MIN_TICK[tick_spacing] - tick_spacing,
                tick_upper=MAX_TICK[tick_spacing],
                amount=100,
            )

    def test_mint_fails_if_tick_upper_greater_than_max_tick(
        self, initialize_empty_pool, random_address, tick_spacing
    ):
        with pytest.raises(UniswapV3Revert):
            pool = initialize_empty_pool(
                pool_factory=self.factory, tick_spacing=tick_spacing
            )
            pool.mint(
                random_address(),
                tick_lower=MIN_TICK[tick_spacing],
                tick_upper=MAX_TICK[tick_spacing] + tick_spacing,
                amount=100,
            )

    def test_mint_fails_if_amount_exceeds_max(
        self, initialize_empty_pool, random_address, tick_spacing
    ):
        minter_address = random_address()
        pool = initialize_empty_pool(
            pool_factory=self.factory, tick_spacing=tick_spacing
        )
        with pytest.raises(UniswapV3Revert):
            pool.mint(
                minter_address,
                tick_lower=MIN_TICK[tick_spacing],
                tick_upper=MAX_TICK[tick_spacing],
                amount=pool.immutables.max_liquidity_per_tick + 1,
            )
        pool.mint(
            minter_address,
            tick_lower=MIN_TICK[tick_spacing],
            tick_upper=MAX_TICK[tick_spacing],
            amount=pool.immutables.max_liquidity_per_tick,
        )

    def test_mint_fails_if_amount_is_zero(
        self, initialize_empty_pool, random_address, tick_spacing
    ):
        with pytest.raises(UniswapV3Revert):
            pool = initialize_empty_pool(
                pool_factory=self.factory, tick_spacing=tick_spacing
            )
            pool.mint(
                random_address(),
                tick_lower=MIN_TICK[tick_spacing],
                tick_upper=MAX_TICK[tick_spacing],
                amount=0,
            )

    def test_mint_fails_if_amount_exceeds_max_2_mints(
        self, initialize_empty_pool, random_address, tick_spacing
    ):
        pool = initialize_empty_pool(
            pool_factory=self.factory, tick_spacing=tick_spacing
        )
        minter_address = random_address()
        pool.mint(
            minter_address,
            tick_lower=MIN_TICK[tick_spacing],
            tick_upper=MAX_TICK[tick_spacing],
            amount=pool.immutables.max_liquidity_per_tick - 1000,
        )
        with pytest.raises(UniswapV3Revert):
            pool.mint(
                minter_address,
                tick_lower=MIN_TICK[tick_spacing],
                tick_upper=MAX_TICK[tick_spacing],
                amount=1001,
            )
        pool.mint(
            minter_address,
            tick_lower=MIN_TICK[tick_spacing],
            tick_upper=MAX_TICK[tick_spacing],
            amount=1000,
        )

    def test_mint_initial_price(self, initialize_mint_test_pool, tick_spacing):
        pool, _ = initialize_mint_test_pool(
            pool_factory=self.factory,
            tick_spacing=tick_spacing,
        )

        assert pool.state.balance_0 == 9996
        assert pool.state.balance_1 == 1000
        assert pool.slot0.tick == -23028

    def test_mint_above_current_price(self, initialize_mint_test_pool, tick_spacing):
        pool, minter_address = initialize_mint_test_pool(
            pool_factory=self.factory,
            tick_spacing=tick_spacing,
        )

        pool.mint(minter_address, tick_lower=-22980, tick_upper=0, amount=10000)
        assert pool.state.balance_0 == 9996 + 21549
        assert pool.state.balance_1 == 1000

    def test_mint_max_tick_max_leverage(self, initialize_mint_test_pool, tick_spacing):
        pool, minter_address = initialize_mint_test_pool(
            pool_factory=self.factory,
            tick_spacing=tick_spacing,
        )

        pool.mint(
            minter_address,
            tick_lower=MAX_TICK[tick_spacing] - tick_spacing,
            tick_upper=MAX_TICK[tick_spacing],
            amount=2**102,
        )
        assert pool.state.balance_0 == 9996 + 828011525
        assert pool.state.balance_1 == 1000

    def test_mint_works_with_max_tick(self, initialize_mint_test_pool, tick_spacing):
        pool, minter_address = initialize_mint_test_pool(
            pool_factory=self.factory,
            tick_spacing=tick_spacing,
        )

        pool.mint(
            minter_address,
            tick_lower=-22980,
            tick_upper=MAX_TICK[60],
            amount=10000,
        )
        assert pool.state.balance_0 == 9996 + 31549
        assert pool.state.balance_1 == 1000

    def test_removing_mint_succeeds(self, initialize_mint_test_pool, tick_spacing):
        pool, minter_address = initialize_mint_test_pool(
            pool_factory=self.factory,
            tick_spacing=tick_spacing,
        )

        pool.mint(minter_address, tick_lower=-240, tick_upper=0, amount=10000)
        amount_0, amount_1 = pool.burn(minter_address, -240, 0, 10000)
        assert amount_0 == 120
        assert amount_1 == 0

    def test_mint_adds_liquidity_to_liquidity_gross(
        self, initialize_empty_pool, random_address, tick_spacing
    ):
        pool = initialize_empty_pool(
            pool_factory=self.factory, tick_spacing=tick_spacing
        )
        minter_address = random_address()
        pool.mint(
            minter_address, tick_lower=-4 * tick_spacing, tick_upper=0, amount=100
        )
        assert pool.ticks[-4 * tick_spacing].liquidity_gross == 100
        assert pool.ticks[0].liquidity_gross == 100
        with pytest.raises(KeyError):
            zero_tick = pool.ticks[tick_spacing].liquidity_gross
        with pytest.raises(KeyError):
            two_tick = pool.ticks[2 * tick_spacing].liquidity_gross

        pool.mint(
            minter_address,
            tick_lower=-4 * tick_spacing,
            tick_upper=tick_spacing,
            amount=150,
        )
        assert pool.ticks[-4 * tick_spacing].liquidity_gross == 250
        assert pool.ticks[0].liquidity_gross == 100
        assert pool.ticks[tick_spacing].liquidity_gross == 150
        with pytest.raises(KeyError):
            two_tick = pool.ticks[2 * tick_spacing].liquidity_gross
        pool.mint(minter_address, tick_lower=0, tick_upper=2 * tick_spacing, amount=60)
        assert pool.ticks[-4 * tick_spacing].liquidity_gross == 250
        assert pool.ticks[0].liquidity_gross == 160
        assert pool.ticks[tick_spacing].liquidity_gross == 150
        assert pool.ticks[2 * tick_spacing].liquidity_gross == 60

    def test_burn_removes_from_liquidity_gross(
        self, initialize_empty_pool, random_address, tick_spacing
    ):
        pool = initialize_empty_pool(
            pool_factory=self.factory, tick_spacing=tick_spacing
        )
        minter_address = random_address()
        pool.mint(
            minter_address, tick_lower=-4 * tick_spacing, tick_upper=0, amount=100
        )
        pool.mint(
            minter_address,
            tick_lower=-4 * tick_spacing,
            tick_upper=tick_spacing,
            amount=40,
        )
        pool.burn(minter_address, -4 * tick_spacing, 0, 90)
        assert pool.ticks[-4 * tick_spacing].liquidity_gross == 50
        assert pool.ticks[0].liquidity_gross == 50

    def test_burn_unitiailizes_tick_if_liquidity_gross_goes_to_zero(
        self, initialize_empty_pool, random_address, tick_spacing
    ):
        pool = initialize_empty_pool(
            pool_factory=self.factory, tick_spacing=tick_spacing
        )
        minter_address = random_address()
        pool.mint(
            minter_address, tick_lower=-4 * tick_spacing, tick_upper=0, amount=100
        )
        pool.burn(minter_address, -4 * tick_spacing, 0, 100)

        with pytest.raises(KeyError):
            assert not pool.ticks[-4 * tick_spacing]

        with pytest.raises(KeyError):
            assert not pool.ticks[0]

    def test_clears_tick_that_is_not_used(
        self, initialize_empty_pool, random_address, tick_spacing
    ):
        pool = initialize_empty_pool(
            pool_factory=self.factory, tick_spacing=tick_spacing
        )
        minter_address = random_address()
        pool.mint(
            minter_address, tick_lower=-4 * tick_spacing, tick_upper=0, amount=100
        )
        pool.mint(minter_address, tick_lower=-tick_spacing, tick_upper=0, amount=250)
        pool.burn(minter_address, -4 * tick_spacing, 0, 100)

        with pytest.raises(KeyError):
            assert not pool.ticks[-4 * tick_spacing]

        assert pool.ticks[-tick_spacing].liquidity_gross == 250
        assert pool.ticks[-tick_spacing].fee_growth_outside_0 == 0
        assert pool.ticks[-tick_spacing].fee_growth_outside_1 == 0

    def test_does_not_write_observation(
        self, initialize_empty_pool, random_address, tick_spacing
    ):
        start_time = int(datetime.datetime.now().timestamp())
        pool = initialize_empty_pool(
            pool_factory=self.factory,
            tick_spacing=tick_spacing,
            initial_timestamp=start_time,
        )
        assert pool.observations[0].tick_cumulative == 0
        assert pool.observations[0].block_timestamp == start_time
        assert pool.observations[0].initialized
        assert pool.observations[0].seconds_per_liquidity_cumulative == 0
        pool.advance_block()

        pool.mint(
            random_address, tick_lower=-4 * tick_spacing, tick_upper=0, amount=100
        )
        assert pool.observations[0].tick_cumulative == 0
        assert pool.observations[0].block_timestamp == start_time
        assert pool.observations[0].initialized
        assert pool.observations[0].seconds_per_liquidity_cumulative == 0

    def test_mint_within_price_range_transfers_both_tokens(
        self, initialize_mint_test_pool, tick_spacing
    ):
        pool, minter_address = initialize_mint_test_pool(
            tick_spacing=tick_spacing, pool_factory=self.factory
        )

        pool.mint(
            minter_address,
            tick_lower=MIN_TICK[tick_spacing] + tick_spacing,
            tick_upper=MAX_TICK[tick_spacing] - tick_spacing,
            amount=100,
        )
        assert pool.state.balance_0 == 9996 + 317
        assert pool.state.balance_1 == 1000 + 32

    def test_mint_within_price_range_initialized_ticks(
        self, initialize_mint_test_pool, tick_spacing
    ):
        pool, minter_address = initialize_mint_test_pool(
            tick_spacing=tick_spacing, pool_factory=self.factory
        )

        pool.mint(
            minter_address,
            tick_lower=MIN_TICK[tick_spacing] + tick_spacing,
            tick_upper=MAX_TICK[tick_spacing] - tick_spacing,
            amount=100,
        )
        assert pool.ticks[MIN_TICK[tick_spacing] + tick_spacing].liquidity_gross == 100
        assert pool.ticks[MAX_TICK[tick_spacing] - tick_spacing].liquidity_gross == 100

    def test_mint_additional_liquidity_min_max_ticks(
        self, initialize_mint_test_pool, tick_spacing
    ):
        pool, minter_address = initialize_mint_test_pool(
            tick_spacing=tick_spacing, pool_factory=self.factory
        )

        pool.mint(
            minter_address,
            tick_lower=MIN_TICK[tick_spacing],
            tick_upper=MAX_TICK[tick_spacing],
            amount=10000,
        )
        assert pool.state.balance_0 == 9996 + 31623
        assert pool.state.balance_1 == 1000 + 3163

    def test_removing_liquidity_min_max_ticks(
        self, initialize_mint_test_pool, tick_spacing
    ):
        pool, minter_address = initialize_mint_test_pool(
            tick_spacing=tick_spacing, pool_factory=self.factory
        )

        pool.mint(
            minter_address,
            tick_lower=MIN_TICK[tick_spacing],
            tick_upper=MAX_TICK[tick_spacing],
            amount=100,
        )
        amount_0, amount_1 = pool.burn(
            minter_address, MIN_TICK[tick_spacing], MAX_TICK[tick_spacing], 100
        )
        assert amount_0 == 316
        assert amount_1 == 31

    def test_writes_an_observation(
        self, initialize_empty_pool, random_address, tick_spacing
    ):
        start_time = int(datetime.datetime.now().timestamp())
        pool = initialize_empty_pool(
            pool_factory=self.factory,
            tick_spacing=tick_spacing,
            initial_timestamp=start_time,
            initial_price=encode_sqrt_price(1, 10),
        )
        minter_address = random_address()
        pool.mint(
            minter_address,
            tick_lower=MIN_TICK[tick_spacing],
            tick_upper=MAX_TICK[tick_spacing],
            amount=3161,
        )
        assert pool.observations[0].tick_cumulative == 0
        assert pool.observations[0].block_timestamp == start_time
        assert pool.observations[0].initialized
        assert pool.observations[0].seconds_per_liquidity_cumulative == 0

        pool.advance_block()
        pool.mint(
            minter_address,
            tick_lower=MIN_TICK[tick_spacing],
            tick_upper=MAX_TICK[tick_spacing],
            amount=100,
        )

        assert pool.observations[0].tick_cumulative == -23028
        assert pool.observations[0].block_timestamp == start_time + 1
        assert pool.observations[0].initialized
        assert (
            pool.observations[0].seconds_per_liquidity_cumulative
            == 107650226801941937191829992860413859
        )

    def test_mint_below_current_price(self, initialize_mint_test_pool, tick_spacing):
        pool, minter_address = initialize_mint_test_pool(
            tick_spacing=tick_spacing, pool_factory=self.factory
        )

        pool.mint(minter_address, tick_lower=-46080, tick_upper=-23040, amount=10000)

        assert pool.state.balance_0 == 9996
        assert pool.state.balance_1 == 1000 + 2162

    def test_mint_min_tick_with_max_leverage(
        self, initialize_mint_test_pool, tick_spacing
    ):
        pool, minter_address = initialize_mint_test_pool(
            tick_spacing=tick_spacing, pool_factory=self.factory
        )

        pool.mint(
            minter_address,
            tick_lower=MIN_TICK[tick_spacing],
            tick_upper=MIN_TICK[tick_spacing] + tick_spacing,
            amount=2**102,
        )

        assert pool.state.balance_0 == 9996
        assert pool.state.balance_1 == 1000 + 828011520

    def test_mint_min_tick(self, initialize_mint_test_pool, tick_spacing):
        pool, minter_address = initialize_mint_test_pool(
            tick_spacing=tick_spacing, pool_factory=self.factory
        )

        pool.mint(
            minter_address,
            tick_lower=MIN_TICK[60],
            tick_upper=-23040,
            amount=10000,
        )

        assert pool.state.balance_0 == 9996
        assert pool.state.balance_1 == 1000 + 3161

    def test_removing_min_tick_liquidity(self, initialize_mint_test_pool, tick_spacing):
        pool, minter_address = initialize_mint_test_pool(
            pool_factory=self.factory,
            tick_spacing=tick_spacing,
        )

        pool.mint(minter_address, tick_lower=-46080, tick_upper=-46020, amount=10000)
        amount_0, amount_1 = pool.burn(minter_address, -46080, -46020, 10000)
        assert amount_0 == 0
        assert amount_1 == 3

    def test_mint_lower_than_price_does_not_write_observation(
        self, initialize_mint_test_pool, tick_spacing
    ):
        start_time = int(datetime.datetime.now().timestamp())
        pool, minter_address = initialize_mint_test_pool(
            pool_factory=self.factory,
            tick_spacing=tick_spacing,
            initial_timestamp=start_time,
        )

        assert pool.observations[0].tick_cumulative == 0
        assert pool.observations[0].block_timestamp == start_time
        assert pool.observations[0].initialized
        assert pool.observations[0].seconds_per_liquidity_cumulative == 0

        pool.advance_block()
        pool.mint(minter_address, tick_lower=-46080, tick_upper=-23040, amount=100)

        assert pool.observations[0].tick_cumulative == 0
        assert pool.observations[0].block_timestamp == start_time
        assert pool.observations[0].initialized
        assert pool.observations[0].seconds_per_liquidity_cumulative == 0

    @pytest.mark.skip("Protocol Fees Skipped for now")
    def test_protocol_fees_accumulate_as_expected_during_swap(
        self, initialize_mint_test_pool, tick_spacing
    ):
        pool, minter_address = initialize_mint_test_pool(
            pool_factory=self.factory,
            tick_spacing=tick_spacing,
        )

        pool.mint(
            minter_address,
            tick_lower=MIN_TICK[tick_spacing] + tick_spacing,
            tick_upper=-MAX_TICK[tick_spacing] - tick_spacing,
            amount=10000,
        )
        pool.swap(
            sender=minter_address,
            recipient=minter_address,
            zero_for_one=True,
            amount_specified=expand_to_decimals(1, 17),
            sqrt_price_limit=TickMathModule.MAX_SQRT_RATIO,
        )
        pool.swap(
            sender=minter_address,
            recipient=minter_address,
            zero_for_one=False,
            amount_specified=expand_to_decimals(1, 16),
            sqrt_price_limit=TickMathModule.MIN_SQRT_RATIO,
        )

        assert pool.protocol_fees_0 == 50000000000000
        assert pool.protocol_fees_1 == 5000000000000

    @pytest.mark.skip("Protocol Fees Skipped for now")
    def test_positions_are_protected_before_protocol_fee_is_turned_on(
        self, initialize_mint_test_pool, tick_spacing
    ):
        pool, minter_address = initialize_mint_test_pool(
            pool_factory=self.factory,
            tick_spacing=tick_spacing,
        )

        pool.mint(
            minter_address,
            tick_lower=MIN_TICK[tick_spacing] + tick_spacing,
            tick_upper=MAX_TICK[tick_spacing] - tick_spacing,
            amount=expand_to_decimals(1, 18),
        )
        pool.swap(
            sender=minter_address,
            recipient=minter_address,
            zero_for_one=True,
            amount_specified=expand_to_decimals(1, 17),
            sqrt_price_limit=TickMathModule.MAX_SQRT_RATIO,
        )
        pool.swap(
            sender=minter_address,
            recipient=minter_address,
            zero_for_one=False,
            amount_specified=expand_to_decimals(1, 16),
            sqrt_price_limit=TickMathModule.MIN_SQRT_RATIO,
        )

        assert pool.protocol_fees_0 == 0
        assert pool.protocol_fees_1 == 0

        pool.set_fee_protocol(6, 6)
        assert pool.protocol_fees_0 == 0
        assert pool.protocol_fees_1 == 0

    def test_poke_is_not_allowed_on_uninitialized_position(
        self, initialize_mint_test_pool, tick_spacing
    ):
        pool, minter_address = initialize_mint_test_pool(
            pool_factory=self.factory,
            tick_spacing=tick_spacing,
        )

        min_tick_1 = MIN_TICK[tick_spacing] + tick_spacing
        max_tick_1 = MAX_TICK[tick_spacing] - tick_spacing

        pool.swap(
            zero_for_one=True,
            amount_specified=expand_to_decimals(1, 17),
            sqrt_price_limit=TickMathModule.MIN_SQRT_RATIO,
        )
        pool.swap(
            zero_for_one=False,
            amount_specified=expand_to_decimals(1, 16),
            sqrt_price_limit=TickMathModule.MAX_SQRT_RATIO,
        )
        with pytest.raises(UniswapV3Revert):
            pool.burn(minter_address, min_tick_1, max_tick_1, 0)

        pool.mint(
            minter_address, tick_lower=min_tick_1, tick_upper=max_tick_1, amount=1
        )

        position_before_burn = pool.positions[(minter_address, min_tick_1, max_tick_1)]

        assert position_before_burn.liquidity == 1
        assert (
            position_before_burn.fee_growth_inside_1_last
            == 102084710076281216349243831104605583
        )
        assert (
            position_before_burn.fee_growth_inside_1_last
            == 10208471007628121634924383110460558
        )
        assert position_before_burn.tokens_owed_0 == 0
        assert position_before_burn.tokens_owed_1 == 0

        pool.burn(minter_address, min_tick_1, max_tick_1, 1)

        position_after_burn = pool.positions[(minter_address, min_tick_1, max_tick_1)]
        assert position_before_burn.liquidity == 0
        assert (
            position_before_burn.fee_growth_inside_1_last
            == 102084710076281216349243831104605583
        )
        assert (
            position_before_burn.fee_growth_inside_1_last
            == 10208471007628121634924383110460558
        )
        assert position_after_burn.tokens_owed_0 == 3
        assert position_after_burn.tokens_owed_1 == 0


class TestBurn:
    factory = PoolFactory(
        exact_math=True,
        logger=TEST_LOGGER,
        sqlalchemy_uri=os.environ["SQLALCHEMY_DB_URI"],
    )

    def test_zero_tick_is_clear(self, initialize_burn_test_pool):
        pool = initialize_burn_test_pool(pool_factory=self.factory)
        with pytest.raises(KeyError):
            zero_tick = pool.ticks[0]

    def test_does_not_clear_position_fee_growth_snapshot_if_no_more_liquidity(
        self, initialize_burn_test_pool, random_address
    ):
        pool = initialize_burn_test_pool(pool_factory=self.factory)
        mint_addr = random_address()

        pool.advance_block()
        pool.mint(mint_addr, MIN_TICK[60], MAX_TICK[60], expand_to_decimals(1, 18))
        pool.swap(
            zero_for_one=True,
            amount_specified=expand_to_decimals(1, 18),
            sqrt_price_limit=TickMathModule.MIN_SQRT_RATIO,
        )
        pool.swap(
            zero_for_one=False,
            amount_specified=expand_to_decimals(1, 18),
            sqrt_price_limit=TickMathModule.MAX_SQRT_RATIO,
        )

        pool.burn(mint_addr, MIN_TICK[60], MAX_TICK[60], expand_to_decimals(1, 18))

        position = pool.positions[(mint_addr, MIN_TICK[60], MAX_TICK[60])]
        assert position.liquidity == 0

        assert position.tokens_owed_0 != 0
        assert position.tokens_owed_1 != 0
        assert position.fee_growth_inside_0_last == 340282366920938463463374607431768211
        assert position.fee_growth_inside_1_last == 340282366920938576890830247744589365

    def test_clears_tick_if_last_position_using_it(
        self, initialize_burn_test_pool, random_address
    ):
        pool = initialize_burn_test_pool(pool_factory=self.factory)
        mint_addr = random_address()

        pool.mint(mint_addr, MIN_TICK[60], MAX_TICK[60], 1)
        pool.swap(
            zero_for_one=True,
            amount_specified=expand_to_decimals(1, 18),
            sqrt_price_limit=TickMathModule.MIN_SQRT_RATIO,
        )
        pool.burn(mint_addr, MIN_TICK[60], MAX_TICK[60], 1)

        with pytest.raises(KeyError):
            MIN_TICK[60] = pool.ticks[MIN_TICK[60]]
        with pytest.raises(KeyError):
            MAX_TICK[60] = pool.ticks[MAX_TICK[60]]

    def test_clears_only_lower_tick_if_upper_tick_still_used(
        self, initialize_burn_test_pool, random_address
    ):
        pool = initialize_burn_test_pool(pool_factory=self.factory)
        mint_addr = random_address()
        tick_lower, tick_upper = MIN_TICK[60] + 60, MAX_TICK[60] - 60

        pool.advance_block()
        pool.mint(mint_addr, tick_lower, tick_upper, 1)
        pool.mint(mint_addr, tick_lower + 60, tick_upper, 1)
        pool.swap(
            zero_for_one=True,
            amount_specified=expand_to_decimals(1, 18),
            sqrt_price_limit=TickMathModule.MIN_SQRT_RATIO,
        )
        pool.burn(mint_addr, tick_lower, tick_upper, 1)
        with pytest.raises(KeyError):
            tick_lower = pool.ticks[tick_lower]

        assert pool.ticks[tick_upper].liquidity_gross == 1

    def test_clears_only_upper_tick_if_lower_still_used(
        self, initialize_burn_test_pool, random_address
    ):
        pool = initialize_burn_test_pool(pool_factory=self.factory)
        mint_addr = random_address()
        tick_lower, tick_upper = MIN_TICK[60] + 60, MAX_TICK[60] - 60

        pool.advance_block()
        pool.mint(mint_addr, tick_lower, tick_upper, 1)
        pool.mint(mint_addr, tick_lower, tick_upper - 60, 1)
        pool.swap(
            zero_for_one=True,
            amount_specified=expand_to_decimals(1, 18),
            sqrt_price_limit=TickMathModule.MIN_SQRT_RATIO,
        )
        pool.burn(mint_addr, tick_lower, tick_upper, 1)
        with pytest.raises(KeyError):
            tick_upper = pool.ticks[tick_upper]

        assert pool.ticks[tick_lower].liquidity_gross == 1


"""


  // the combined amount of liquidity that the pool is initialized with (including the 1 minimum liquidity that is burned)
  const initializeLiquidityAmount = expandTo18Decimals(2)
  async function initializeAtZeroTick(pool: MockTimeUniswapV3Pool): Promise<void> {
    await pool.initialize(encodePriceSqrt(1, 1))
    const tickSpacing = await pool.tickSpacing()
    const [min, max] = [getMinTick(tickSpacing), getMaxTick(tickSpacing)]
    await mint(wallet.address, min, max, initializeLiquidityAmount)
  }

  describe('#observe', () => {
    beforeEach(() => initializeAtZeroTick(pool))

    // zero tick
    it('current tick accumulator increases by tick over time', async () => {
      let {
        tickCumulatives: [tickCumulative],
      } = await pool.observe([0])
      expect(tickCumulative).to.eq(0)
      await pool.advanceTime(10)
      ;({
        tickCumulatives: [tickCumulative],
      } = await pool.observe([0]))
      expect(tickCumulative).to.eq(0)
    })

    it('current tick accumulator after single swap', async () => {
      // moves to tick -1
      await swapExact0For1(1000, wallet.address)
      await pool.advanceTime(4)
      let {
        tickCumulatives: [tickCumulative],
      } = await pool.observe([0])
      expect(tickCumulative).to.eq(-4)
    })

    it('current tick accumulator after two swaps', async () => {
      await swapExact0For1(expandTo18Decimals(1).div(2), wallet.address)
      expect((await pool.slot0()).tick).to.eq(-4452)
      await pool.advanceTime(4)
      await swapExact1For0(expandTo18Decimals(1).div(4), wallet.address)
      expect((await pool.slot0()).tick).to.eq(-1558)
      await pool.advanceTime(6)
      let {
        tickCumulatives: [tickCumulative],
      } = await pool.observe([0])
      // -4452*4 + -1558*6
      expect(tickCumulative).to.eq(-27156)
    })
  })

  describe('miscellaneous mint tests', () => {
    beforeEach('initialize at zero tick', async () => {
      pool = await createPool(FeeAmount.LOW, TICK_SPACINGS[FeeAmount.LOW])
      await initializeAtZeroTick(pool)
    })

    it('mint to the right of the current price', async () => {
      const liquidityDelta = 1000
      const lowerTick = tickSpacing
      const upperTick = tickSpacing * 2

      const liquidityBefore = await pool.liquidity()

      const b0 = await token0.balanceOf(pool.address)
      const b1 = await token1.balanceOf(pool.address)

      await mint(wallet.address, lowerTick, upperTick, liquidityDelta)

      const liquidityAfter = await pool.liquidity()
      expect(liquidityAfter).to.be.gte(liquidityBefore)

      expect((await token0.balanceOf(pool.address)).sub(b0)).to.eq(1)
      expect((await token1.balanceOf(pool.address)).sub(b1)).to.eq(0)
    })

    it('mint to the left of the current price', async () => {
      const liquidityDelta = 1000
      const lowerTick = -tickSpacing * 2
      const upperTick = -tickSpacing

      const liquidityBefore = await pool.liquidity()

      const b0 = await token0.balanceOf(pool.address)
      const b1 = await token1.balanceOf(pool.address)

      await mint(wallet.address, lowerTick, upperTick, liquidityDelta)

      const liquidityAfter = await pool.liquidity()
      expect(liquidityAfter).to.be.gte(liquidityBefore)

      expect((await token0.balanceOf(pool.address)).sub(b0)).to.eq(0)
      expect((await token1.balanceOf(pool.address)).sub(b1)).to.eq(1)
    })

    it('mint within the current price', async () => {
      const liquidityDelta = 1000
      const lowerTick = -tickSpacing
      const upperTick = tickSpacing

      const liquidityBefore = await pool.liquidity()

      const b0 = await token0.balanceOf(pool.address)
      const b1 = await token1.balanceOf(pool.address)

      await mint(wallet.address, lowerTick, upperTick, liquidityDelta)

      const liquidityAfter = await pool.liquidity()
      expect(liquidityAfter).to.be.gte(liquidityBefore)

      expect((await token0.balanceOf(pool.address)).sub(b0)).to.eq(1)
      expect((await token1.balanceOf(pool.address)).sub(b1)).to.eq(1)
    })

    it('cannot remove more than the entire position', async () => {
      const lowerTick = -tickSpacing
      const upperTick = tickSpacing
      await mint(wallet.address, lowerTick, upperTick, expandTo18Decimals(1000))
      // should be 'LS', hardhat is bugged
      await expect(pool.burn(lowerTick, upperTick, expandTo18Decimals(1001))).to.be.reverted
    })

    it('collect fees within the current price after swap', async () => {
      const liquidityDelta = expandTo18Decimals(100)
      const lowerTick = -tickSpacing * 100
      const upperTick = tickSpacing * 100

      await mint(wallet.address, lowerTick, upperTick, liquidityDelta)

      const liquidityBefore = await pool.liquidity()

      const amount0In = expandTo18Decimals(1)
      await swapExact0For1(amount0In, wallet.address)

      const liquidityAfter = await pool.liquidity()
      expect(liquidityAfter, 'k increases').to.be.gte(liquidityBefore)

      const token0BalanceBeforePool = await token0.balanceOf(pool.address)
      const token1BalanceBeforePool = await token1.balanceOf(pool.address)
      const token0BalanceBeforeWallet = await token0.balanceOf(wallet.address)
      const token1BalanceBeforeWallet = await token1.balanceOf(wallet.address)

      await pool.burn(lowerTick, upperTick, 0)
      await pool.collect(wallet.address, lowerTick, upperTick, MaxUint128, MaxUint128)

      await pool.burn(lowerTick, upperTick, 0)
      const { amount0: fees0, amount1: fees1 } = await pool.callStatic.collect(
        wallet.address,
        lowerTick,
        upperTick,
        MaxUint128,
        MaxUint128
      )
      expect(fees0).to.be.eq(0)
      expect(fees1).to.be.eq(0)

      const token0BalanceAfterWallet = await token0.balanceOf(wallet.address)
      const token1BalanceAfterWallet = await token1.balanceOf(wallet.address)
      const token0BalanceAfterPool = await token0.balanceOf(pool.address)
      const token1BalanceAfterPool = await token1.balanceOf(pool.address)

      expect(token0BalanceAfterWallet).to.be.gt(token0BalanceBeforeWallet)
      expect(token1BalanceAfterWallet).to.be.eq(token1BalanceBeforeWallet)

      expect(token0BalanceAfterPool).to.be.lt(token0BalanceBeforePool)
      expect(token1BalanceAfterPool).to.be.eq(token1BalanceBeforePool)
    })
  })

  describe('post-initialize at medium fee', () => {
    describe('k (implicit)', () => {
      it('returns 0 before initialization', async () => {
        expect(await pool.liquidity()).to.eq(0)
      })
      describe('post initialized', () => {
        beforeEach(() => initializeAtZeroTick(pool))

        it('returns initial liquidity', async () => {
          expect(await pool.liquidity()).to.eq(expandTo18Decimals(2))
        })
        it('returns in supply in range', async () => {
          await mint(wallet.address, -tickSpacing, tickSpacing, expandTo18Decimals(3))
          expect(await pool.liquidity()).to.eq(expandTo18Decimals(5))
        })
        it('excludes supply at tick above current tick', async () => {
          await mint(wallet.address, tickSpacing, tickSpacing * 2, expandTo18Decimals(3))
          expect(await pool.liquidity()).to.eq(expandTo18Decimals(2))
        })
        it('excludes supply at tick below current tick', async () => {
          await mint(wallet.address, -tickSpacing * 2, -tickSpacing, expandTo18Decimals(3))
          expect(await pool.liquidity()).to.eq(expandTo18Decimals(2))
        })
        it('updates correctly when exiting range', async () => {
          const kBefore = await pool.liquidity()
          expect(kBefore).to.be.eq(expandTo18Decimals(2))

          // add liquidity at and above current tick
          const liquidityDelta = expandTo18Decimals(1)
          const lowerTick = 0
          const upperTick = tickSpacing
          await mint(wallet.address, lowerTick, upperTick, liquidityDelta)

          // ensure virtual supply has increased appropriately
          const kAfter = await pool.liquidity()
          expect(kAfter).to.be.eq(expandTo18Decimals(3))

          // swap toward the left (just enough for the tick transition function to trigger)
          await swapExact0For1(1, wallet.address)
          const { tick } = await pool.slot0()
          expect(tick).to.be.eq(-1)

          const kAfterSwap = await pool.liquidity()
          expect(kAfterSwap).to.be.eq(expandTo18Decimals(2))
        })
        it('updates correctly when entering range', async () => {
          const kBefore = await pool.liquidity()
          expect(kBefore).to.be.eq(expandTo18Decimals(2))

          // add liquidity below the current tick
          const liquidityDelta = expandTo18Decimals(1)
          const lowerTick = -tickSpacing
          const upperTick = 0
          await mint(wallet.address, lowerTick, upperTick, liquidityDelta)

          // ensure virtual supply hasn't changed
          const kAfter = await pool.liquidity()
          expect(kAfter).to.be.eq(kBefore)

          // swap toward the left (just enough for the tick transition function to trigger)
          await swapExact0For1(1, wallet.address)
          const { tick } = await pool.slot0()
          expect(tick).to.be.eq(-1)

          const kAfterSwap = await pool.liquidity()
          expect(kAfterSwap).to.be.eq(expandTo18Decimals(3))
        })
      })
    })
  })

  describe('limit orders', () => {
    beforeEach('initialize at tick 0', () => initializeAtZeroTick(pool))

    it('limit selling 0 for 1 at tick 0 thru 1', async () => {
      await expect(mint(wallet.address, 0, 120, expandTo18Decimals(1)))
        .to.emit(token0, 'Transfer')
        .withArgs(wallet.address, pool.address, '5981737760509663')
      // somebody takes the limit order
      await swapExact1For0(expandTo18Decimals(2), other.address)
      await expect(pool.burn(0, 120, expandTo18Decimals(1)))
        .to.emit(pool, 'Burn')
        .withArgs(wallet.address, 0, 120, expandTo18Decimals(1), 0, '6017734268818165')
        .to.not.emit(token0, 'Transfer')
        .to.not.emit(token1, 'Transfer')
      await expect(pool.collect(wallet.address, 0, 120, MaxUint128, MaxUint128))
        .to.emit(token1, 'Transfer')
        .withArgs(pool.address, wallet.address, BigNumber.from('6017734268818165').add('18107525382602')) // roughly 0.3% despite other liquidity
        .to.not.emit(token0, 'Transfer')
      expect((await pool.slot0()).tick).to.be.gte(120)
    })
    it('limit selling 1 for 0 at tick 0 thru -1', async () => {
      await expect(mint(wallet.address, -120, 0, expandTo18Decimals(1)))
        .to.emit(token1, 'Transfer')
        .withArgs(wallet.address, pool.address, '5981737760509663')
      // somebody takes the limit order
      await swapExact0For1(expandTo18Decimals(2), other.address)
      await expect(pool.burn(-120, 0, expandTo18Decimals(1)))
        .to.emit(pool, 'Burn')
        .withArgs(wallet.address, -120, 0, expandTo18Decimals(1), '6017734268818165', 0)
        .to.not.emit(token0, 'Transfer')
        .to.not.emit(token1, 'Transfer')
      await expect(pool.collect(wallet.address, -120, 0, MaxUint128, MaxUint128))
        .to.emit(token0, 'Transfer')
        .withArgs(pool.address, wallet.address, BigNumber.from('6017734268818165').add('18107525382602')) // roughly 0.3% despite other liquidity
      expect((await pool.slot0()).tick).to.be.lt(-120)
    })

    describe('fee is on', () => {
      beforeEach(() => pool.setFeeProtocol(6, 6))
      it('limit selling 0 for 1 at tick 0 thru 1', async () => {
        await expect(mint(wallet.address, 0, 120, expandTo18Decimals(1)))
          .to.emit(token0, 'Transfer')
          .withArgs(wallet.address, pool.address, '5981737760509663')
        // somebody takes the limit order
        await swapExact1For0(expandTo18Decimals(2), other.address)
        await expect(pool.burn(0, 120, expandTo18Decimals(1)))
          .to.emit(pool, 'Burn')
          .withArgs(wallet.address, 0, 120, expandTo18Decimals(1), 0, '6017734268818165')
          .to.not.emit(token0, 'Transfer')
          .to.not.emit(token1, 'Transfer')
        await expect(pool.collect(wallet.address, 0, 120, MaxUint128, MaxUint128))
          .to.emit(token1, 'Transfer')
          .withArgs(pool.address, wallet.address, BigNumber.from('6017734268818165').add('15089604485501')) // roughly 0.25% despite other liquidity
          .to.not.emit(token0, 'Transfer')
        expect((await pool.slot0()).tick).to.be.gte(120)
      })
      it('limit selling 1 for 0 at tick 0 thru -1', async () => {
        await expect(mint(wallet.address, -120, 0, expandTo18Decimals(1)))
          .to.emit(token1, 'Transfer')
          .withArgs(wallet.address, pool.address, '5981737760509663')
        // somebody takes the limit order
        await swapExact0For1(expandTo18Decimals(2), other.address)
        await expect(pool.burn(-120, 0, expandTo18Decimals(1)))
          .to.emit(pool, 'Burn')
          .withArgs(wallet.address, -120, 0, expandTo18Decimals(1), '6017734268818165', 0)
          .to.not.emit(token0, 'Transfer')
          .to.not.emit(token1, 'Transfer')
        await expect(pool.collect(wallet.address, -120, 0, MaxUint128, MaxUint128))
          .to.emit(token0, 'Transfer')
          .withArgs(pool.address, wallet.address, BigNumber.from('6017734268818165').add('15089604485501')) // roughly 0.25% despite other liquidity
        expect((await pool.slot0()).tick).to.be.lt(-120)
      })
    })
  })

  describe('#collect', () => {
    beforeEach(async () => {
      pool = await createPool(FeeAmount.LOW, TICK_SPACINGS[FeeAmount.LOW])
      await pool.initialize(encodePriceSqrt(1, 1))
    })

    it('works with multiple LPs', async () => {
      await mint(wallet.address, minTick, maxTick, expandTo18Decimals(1))
      await mint(wallet.address, minTick + tickSpacing, maxTick - tickSpacing, expandTo18Decimals(2))

      await swapExact0For1(expandTo18Decimals(1), wallet.address)

      // poke positions
      await pool.burn(minTick, maxTick, 0)
      await pool.burn(minTick + tickSpacing, maxTick - tickSpacing, 0)

      const { tokensOwed0: tokensOwed0Position0 } = await pool.positions(
        getPositionKey(wallet.address, minTick, maxTick)
      )
      const { tokensOwed0: tokensOwed0Position1 } = await pool.positions(
        getPositionKey(wallet.address, minTick + tickSpacing, maxTick - tickSpacing)
      )

      expect(tokensOwed0Position0).to.be.eq('166666666666667')
      expect(tokensOwed0Position1).to.be.eq('333333333333334')
    })

    describe('works across large increases', () => {
      beforeEach(async () => {
        await mint(wallet.address, minTick, maxTick, expandTo18Decimals(1))
      })

      // type(uint128).max * 2**128 / 1e18
      // https://www.wolframalpha.com/input/?i=%282**128+-+1%29+*+2**128+%2F+1e18
      const magicNumber = BigNumber.from('115792089237316195423570985008687907852929702298719625575994')

      it('works just before the cap binds', async () => {
        await pool.setFeeGrowthGlobal0X128(magicNumber)
        await pool.burn(minTick, maxTick, 0)

        const { tokensOwed0, tokensOwed1 } = await pool.positions(getPositionKey(wallet.address, minTick, maxTick))

        expect(tokensOwed0).to.be.eq(MaxUint128.sub(1))
        expect(tokensOwed1).to.be.eq(0)
      })

      it('works just after the cap binds', async () => {
        await pool.setFeeGrowthGlobal0X128(magicNumber.add(1))
        await pool.burn(minTick, maxTick, 0)

        const { tokensOwed0, tokensOwed1 } = await pool.positions(getPositionKey(wallet.address, minTick, maxTick))

        expect(tokensOwed0).to.be.eq(MaxUint128)
        expect(tokensOwed1).to.be.eq(0)
      })

      it('works well after the cap binds', async () => {
        await pool.setFeeGrowthGlobal0X128(constants.MaxUint256)
        await pool.burn(minTick, maxTick, 0)

        const { tokensOwed0, tokensOwed1 } = await pool.positions(getPositionKey(wallet.address, minTick, maxTick))

        expect(tokensOwed0).to.be.eq(MaxUint128)
        expect(tokensOwed1).to.be.eq(0)
      })
    })

    describe('works across overflow boundaries', () => {
      beforeEach(async () => {
        await pool.setFeeGrowthGlobal0X128(constants.MaxUint256)
        await pool.setFeeGrowthGlobal1X128(constants.MaxUint256)
        await mint(wallet.address, minTick, maxTick, expandTo18Decimals(10))
      })

      it('token0', async () => {
        await swapExact0For1(expandTo18Decimals(1), wallet.address)
        await pool.burn(minTick, maxTick, 0)
        const { amount0, amount1 } = await pool.callStatic.collect(
          wallet.address,
          minTick,
          maxTick,
          MaxUint128,
          MaxUint128
        )
        expect(amount0).to.be.eq('499999999999999')
        expect(amount1).to.be.eq(0)
      })
      it('token1', async () => {
        await swapExact1For0(expandTo18Decimals(1), wallet.address)
        await pool.burn(minTick, maxTick, 0)
        const { amount0, amount1 } = await pool.callStatic.collect(
          wallet.address,
          minTick,
          maxTick,
          MaxUint128,
          MaxUint128
        )
        expect(amount0).to.be.eq(0)
        expect(amount1).to.be.eq('499999999999999')
      })
      it('token0 and token1', async () => {
        await swapExact0For1(expandTo18Decimals(1), wallet.address)
        await swapExact1For0(expandTo18Decimals(1), wallet.address)
        await pool.burn(minTick, maxTick, 0)
        const { amount0, amount1 } = await pool.callStatic.collect(
          wallet.address,
          minTick,
          maxTick,
          MaxUint128,
          MaxUint128
        )
        expect(amount0).to.be.eq('499999999999999')
        expect(amount1).to.be.eq('500000000000000')
      })
    })
  })

  describe('#feeProtocol', () => {
    const liquidityAmount = expandTo18Decimals(1000)

    beforeEach(async () => {
      pool = await createPool(FeeAmount.LOW, TICK_SPACINGS[FeeAmount.LOW])
      await pool.initialize(encodePriceSqrt(1, 1))
      await mint(wallet.address, minTick, maxTick, liquidityAmount)
    })

    it('is initially set to 0', async () => {
      expect((await pool.slot0()).feeProtocol).to.eq(0)
    })

    it('can be changed by the owner', async () => {
      await pool.setFeeProtocol(6, 6)
      expect((await pool.slot0()).feeProtocol).to.eq(102)
    })

    it('cannot be changed out of bounds', async () => {
      await expect(pool.setFeeProtocol(3, 3)).to.be.reverted
      await expect(pool.setFeeProtocol(11, 11)).to.be.reverted
    })

    it('cannot be changed by addresses that are not owner', async () => {
      await expect(pool.connect(other).setFeeProtocol(6, 6)).to.be.reverted
    })

    async function swapAndGetFeesOwed({
      amount,
      zeroForOne,
      poke,
    }: {
      amount: BigNumberish
      zeroForOne: boolean
      poke: boolean
    }) {
      await (zeroForOne ? swapExact0For1(amount, wallet.address) : swapExact1For0(amount, wallet.address))

      if (poke) await pool.burn(minTick, maxTick, 0)

      const { amount0: fees0, amount1: fees1 } = await pool.callStatic.collect(
        wallet.address,
        minTick,
        maxTick,
        MaxUint128,
        MaxUint128
      )

      expect(fees0, 'fees owed in token0 are greater than 0').to.be.gte(0)
      expect(fees1, 'fees owed in token1 are greater than 0').to.be.gte(0)

      return { token0Fees: fees0, token1Fees: fees1 }
    }

    it('position owner gets full fees when protocol fee is off', async () => {
      const { token0Fees, token1Fees } = await swapAndGetFeesOwed({
        amount: expandTo18Decimals(1),
        zeroForOne: true,
        poke: true,
      })

      // 6 bips * 1e18
      expect(token0Fees).to.eq('499999999999999')
      expect(token1Fees).to.eq(0)
    })

    it('swap fees accumulate as expected (0 for 1)', async () => {
      let token0Fees
      let token1Fees
      ;({ token0Fees, token1Fees } = await swapAndGetFeesOwed({
        amount: expandTo18Decimals(1),
        zeroForOne: true,
        poke: true,
      }))
      expect(token0Fees).to.eq('499999999999999')
      expect(token1Fees).to.eq(0)
      ;({ token0Fees, token1Fees } = await swapAndGetFeesOwed({
        amount: expandTo18Decimals(1),
        zeroForOne: true,
        poke: true,
      }))
      expect(token0Fees).to.eq('999999999999998')
      expect(token1Fees).to.eq(0)
      ;({ token0Fees, token1Fees } = await swapAndGetFeesOwed({
        amount: expandTo18Decimals(1),
        zeroForOne: true,
        poke: true,
      }))
      expect(token0Fees).to.eq('1499999999999997')
      expect(token1Fees).to.eq(0)
    })

    it('swap fees accumulate as expected (1 for 0)', async () => {
      let token0Fees
      let token1Fees
      ;({ token0Fees, token1Fees } = await swapAndGetFeesOwed({
        amount: expandTo18Decimals(1),
        zeroForOne: false,
        poke: true,
      }))
      expect(token0Fees).to.eq(0)
      expect(token1Fees).to.eq('499999999999999')
      ;({ token0Fees, token1Fees } = await swapAndGetFeesOwed({
        amount: expandTo18Decimals(1),
        zeroForOne: false,
        poke: true,
      }))
      expect(token0Fees).to.eq(0)
      expect(token1Fees).to.eq('999999999999998')
      ;({ token0Fees, token1Fees } = await swapAndGetFeesOwed({
        amount: expandTo18Decimals(1),
        zeroForOne: false,
        poke: true,
      }))
      expect(token0Fees).to.eq(0)
      expect(token1Fees).to.eq('1499999999999997')
    })

    it('position owner gets partial fees when protocol fee is on', async () => {
      await pool.setFeeProtocol(6, 6)

      const { token0Fees, token1Fees } = await swapAndGetFeesOwed({
        amount: expandTo18Decimals(1),
        zeroForOne: true,
        poke: true,
      })

      expect(token0Fees).to.be.eq('416666666666666')
      expect(token1Fees).to.be.eq(0)
    })

    describe('#collectProtocol', () => {
      it('returns 0 if no fees', async () => {
        await pool.setFeeProtocol(6, 6)
        const { amount0, amount1 } = await pool.callStatic.collectProtocol(wallet.address, MaxUint128, MaxUint128)
        expect(amount0).to.be.eq(0)
        expect(amount1).to.be.eq(0)
      })

      it('can collect fees', async () => {
        await pool.setFeeProtocol(6, 6)

        await swapAndGetFeesOwed({
          amount: expandTo18Decimals(1),
          zeroForOne: true,
          poke: true,
        })

        await expect(pool.collectProtocol(other.address, MaxUint128, MaxUint128))
          .to.emit(token0, 'Transfer')
          .withArgs(pool.address, other.address, '83333333333332')
      })

      it('fees collected can differ between token0 and token1', async () => {
        await pool.setFeeProtocol(8, 5)

        await swapAndGetFeesOwed({
          amount: expandTo18Decimals(1),
          zeroForOne: true,
          poke: false,
        })
        await swapAndGetFeesOwed({
          amount: expandTo18Decimals(1),
          zeroForOne: false,
          poke: false,
        })

        await expect(pool.collectProtocol(other.address, MaxUint128, MaxUint128))
          .to.emit(token0, 'Transfer')
          // more token0 fees because it's 1/5th the swap fees
          .withArgs(pool.address, other.address, '62499999999999')
          .to.emit(token1, 'Transfer')
          // less token1 fees because it's 1/8th the swap fees
          .withArgs(pool.address, other.address, '99999999999998')
      })
    })

    it('fees collected by lp after two swaps should be double one swap', async () => {
      await swapAndGetFeesOwed({
        amount: expandTo18Decimals(1),
        zeroForOne: true,
        poke: true,
      })
      const { token0Fees, token1Fees } = await swapAndGetFeesOwed({
        amount: expandTo18Decimals(1),
        zeroForOne: true,
        poke: true,
      })

      // 6 bips * 2e18
      expect(token0Fees).to.eq('999999999999998')
      expect(token1Fees).to.eq(0)
    })

    it('fees collected after two swaps with fee turned on in middle are fees from last swap (not confiscatory)', async () => {
      await swapAndGetFeesOwed({
        amount: expandTo18Decimals(1),
        zeroForOne: true,
        poke: false,
      })

      await pool.setFeeProtocol(6, 6)

      const { token0Fees, token1Fees } = await swapAndGetFeesOwed({
        amount: expandTo18Decimals(1),
        zeroForOne: true,
        poke: true,
      })

      expect(token0Fees).to.eq('916666666666666')
      expect(token1Fees).to.eq(0)
    })

    it('fees collected by lp after two swaps with intermediate withdrawal', async () => {
      await pool.setFeeProtocol(6, 6)

      const { token0Fees, token1Fees } = await swapAndGetFeesOwed({
        amount: expandTo18Decimals(1),
        zeroForOne: true,
        poke: true,
      })

      expect(token0Fees).to.eq('416666666666666')
      expect(token1Fees).to.eq(0)

      // collect the fees
      await pool.collect(wallet.address, minTick, maxTick, MaxUint128, MaxUint128)

      const { token0Fees: token0FeesNext, token1Fees: token1FeesNext } = await swapAndGetFeesOwed({
        amount: expandTo18Decimals(1),
        zeroForOne: true,
        poke: false,
      })

      expect(token0FeesNext).to.eq(0)
      expect(token1FeesNext).to.eq(0)

      let { token0: token0ProtocolFees, token1: token1ProtocolFees } = await pool.protocolFees()
      expect(token0ProtocolFees).to.eq('166666666666666')
      expect(token1ProtocolFees).to.eq(0)

      await pool.burn(minTick, maxTick, 0) // poke to update fees
      await expect(pool.collect(wallet.address, minTick, maxTick, MaxUint128, MaxUint128))
        .to.emit(token0, 'Transfer')
        .withArgs(pool.address, wallet.address, '416666666666666')
      ;({ token0: token0ProtocolFees, token1: token1ProtocolFees } = await pool.protocolFees())
      expect(token0ProtocolFees).to.eq('166666666666666')
      expect(token1ProtocolFees).to.eq(0)
    })
  })

  describe('#tickSpacing', () => {
    describe('tickSpacing = 12', () => {
      beforeEach('deploy pool', async () => {
        pool = await createPool(FeeAmount.MEDIUM, 12)
      })
      describe('post initialize', () => {
        beforeEach('initialize pool', async () => {
          await pool.initialize(encodePriceSqrt(1, 1))
        })
        it('mint can only be called for multiples of 12', async () => {
          await expect(mint(wallet.address, -6, 0, 1)).to.be.reverted
          await expect(mint(wallet.address, 0, 6, 1)).to.be.reverted
        })
        it('mint can be called with multiples of 12', async () => {
          await mint(wallet.address, 12, 24, 1)
          await mint(wallet.address, -144, -120, 1)
        })
        it('swapping across gaps works in 1 for 0 direction', async () => {
          const liquidityAmount = expandTo18Decimals(1).div(4)
          await mint(wallet.address, 120000, 121200, liquidityAmount)
          await swapExact1For0(expandTo18Decimals(1), wallet.address)
          await expect(pool.burn(120000, 121200, liquidityAmount))
            .to.emit(pool, 'Burn')
            .withArgs(wallet.address, 120000, 121200, liquidityAmount, '30027458295511', '996999999999999999')
            .to.not.emit(token0, 'Transfer')
            .to.not.emit(token1, 'Transfer')
          expect((await pool.slot0()).tick).to.eq(120196)
        })
        it('swapping across gaps works in 0 for 1 direction', async () => {
          const liquidityAmount = expandTo18Decimals(1).div(4)
          await mint(wallet.address, -121200, -120000, liquidityAmount)
          await swapExact0For1(expandTo18Decimals(1), wallet.address)
          await expect(pool.burn(-121200, -120000, liquidityAmount))
            .to.emit(pool, 'Burn')
            .withArgs(wallet.address, -121200, -120000, liquidityAmount, '996999999999999999', '30027458295511')
            .to.not.emit(token0, 'Transfer')
            .to.not.emit(token1, 'Transfer')
          expect((await pool.slot0()).tick).to.eq(-120197)
        })
      })
    })
  })

  // https://github.com/Uniswap/uniswap-v3-core/issues/214
  it('tick transition cannot run twice if zero for one swap ends at fractional price just below tick', async () => {
    pool = await createPool(FeeAmount.MEDIUM, 1)
    const sqrtTickMath = (await (await ethers.getContractFactory('TickMathTest')).deploy()) as TickMathTest
    const swapMath = (await (await ethers.getContractFactory('SwapMathTest')).deploy()) as SwapMathTest
    const p0 = (await sqrtTickMath.getSqrtRatioAtTick(-24081)).add(1)
    // initialize at a price of ~0.3 token1/token0
    // meaning if you swap in 2 token0, you should end up getting 0 token1
    await pool.initialize(p0)
    expect(await pool.liquidity(), 'current pool liquidity is 1').to.eq(0)
    expect((await pool.slot0()).tick, 'pool tick is -24081').to.eq(-24081)

    // add a bunch of liquidity around current price
    const liquidity = expandTo18Decimals(1000)
    await mint(wallet.address, -24082, -24080, liquidity)
    expect(await pool.liquidity(), 'current pool liquidity is now liquidity + 1').to.eq(liquidity)

    await mint(wallet.address, -24082, -24081, liquidity)
    expect(await pool.liquidity(), 'current pool liquidity is still liquidity + 1').to.eq(liquidity)

    // check the math works out to moving the price down 1, sending no amount out, and having some amount remaining
    {
      const { feeAmount, amountIn, amountOut, sqrtQ } = await swapMath.computeSwapStep(
        p0,
        p0.sub(1),
        liquidity,
        3,
        FeeAmount.MEDIUM
      )
      expect(sqrtQ, 'price moves').to.eq(p0.sub(1))
      expect(feeAmount, 'fee amount is 1').to.eq(1)
      expect(amountIn, 'amount in is 1').to.eq(1)
      expect(amountOut, 'zero amount out').to.eq(0)
    }

    // swap 2 amount in, should get 0 amount out
    await expect(swapExact0For1(3, wallet.address))
      .to.emit(token0, 'Transfer')
      .withArgs(wallet.address, pool.address, 3)
      .to.not.emit(token1, 'Transfer')

    const { tick, sqrtPriceX96 } = await pool.slot0()

    expect(tick, 'pool is at the next tick').to.eq(-24082)
    expect(sqrtPriceX96, 'pool price is still on the p0 boundary').to.eq(p0.sub(1))
    expect(await pool.liquidity(), 'pool has run tick transition and liquidity changed').to.eq(liquidity.mul(2))
  })

  describe('#flash', () => {
    it('fails if not initialized', async () => {
      await expect(flash(100, 200, other.address)).to.be.reverted
      await expect(flash(100, 0, other.address)).to.be.reverted
      await expect(flash(0, 200, other.address)).to.be.reverted
    })
    it('fails if no liquidity', async () => {
      await pool.initialize(encodePriceSqrt(1, 1))
      await expect(flash(100, 200, other.address)).to.be.revertedWith('L')
      await expect(flash(100, 0, other.address)).to.be.revertedWith('L')
      await expect(flash(0, 200, other.address)).to.be.revertedWith('L')
    })
    describe('after liquidity added', () => {
      let balance0: BigNumber
      let balance1: BigNumber
      beforeEach('add some tokens', async () => {
        await initializeAtZeroTick(pool)
        ;[balance0, balance1] = await Promise.all([token0.balanceOf(pool.address), token1.balanceOf(pool.address)])
      })

      describe('fee off', () => {
        it('emits an event', async () => {
          await expect(flash(1001, 2001, other.address))
            .to.emit(pool, 'Flash')
            .withArgs(swapTarget.address, other.address, 1001, 2001, 4, 7)
        })

        it('transfers the amount0 to the recipient', async () => {
          await expect(flash(100, 200, other.address))
            .to.emit(token0, 'Transfer')
            .withArgs(pool.address, other.address, 100)
        })
        it('transfers the amount1 to the recipient', async () => {
          await expect(flash(100, 200, other.address))
            .to.emit(token1, 'Transfer')
            .withArgs(pool.address, other.address, 200)
        })
        it('can flash only token0', async () => {
          await expect(flash(101, 0, other.address))
            .to.emit(token0, 'Transfer')
            .withArgs(pool.address, other.address, 101)
            .to.not.emit(token1, 'Transfer')
        })
        it('can flash only token1', async () => {
          await expect(flash(0, 102, other.address))
            .to.emit(token1, 'Transfer')
            .withArgs(pool.address, other.address, 102)
            .to.not.emit(token0, 'Transfer')
        })
        it('can flash entire token balance', async () => {
          await expect(flash(balance0, balance1, other.address))
            .to.emit(token0, 'Transfer')
            .withArgs(pool.address, other.address, balance0)
            .to.emit(token1, 'Transfer')
            .withArgs(pool.address, other.address, balance1)
        })
        it('no-op if both amounts are 0', async () => {
          await expect(flash(0, 0, other.address)).to.not.emit(token0, 'Transfer').to.not.emit(token1, 'Transfer')
        })
        it('fails if flash amount is greater than token balance', async () => {
          await expect(flash(balance0.add(1), balance1, other.address)).to.be.reverted
          await expect(flash(balance0, balance1.add(1), other.address)).to.be.reverted
        })
        it('calls the flash callback on the sender with correct fee amounts', async () => {
          await expect(flash(1001, 2002, other.address)).to.emit(swapTarget, 'FlashCallback').withArgs(4, 7)
        })
        it('increases the fee growth by the expected amount', async () => {
          await flash(1001, 2002, other.address)
          expect(await pool.feeGrowthGlobal0X128()).to.eq(
            BigNumber.from(4).mul(BigNumber.from(2).pow(128)).div(expandTo18Decimals(2))
          )
          expect(await pool.feeGrowthGlobal1X128()).to.eq(
            BigNumber.from(7).mul(BigNumber.from(2).pow(128)).div(expandTo18Decimals(2))
          )
        })
        it('fails if original balance not returned in either token', async () => {
          await expect(flash(1000, 0, other.address, 999, 0)).to.be.reverted
          await expect(flash(0, 1000, other.address, 0, 999)).to.be.reverted
        })
        it('fails if underpays either token', async () => {
          await expect(flash(1000, 0, other.address, 1002, 0)).to.be.reverted
          await expect(flash(0, 1000, other.address, 0, 1002)).to.be.reverted
        })
        it('allows donating token0', async () => {
          await expect(flash(0, 0, constants.AddressZero, 567, 0))
            .to.emit(token0, 'Transfer')
            .withArgs(wallet.address, pool.address, 567)
            .to.not.emit(token1, 'Transfer')
          expect(await pool.feeGrowthGlobal0X128()).to.eq(
            BigNumber.from(567).mul(BigNumber.from(2).pow(128)).div(expandTo18Decimals(2))
          )
        })
        it('allows donating token1', async () => {
          await expect(flash(0, 0, constants.AddressZero, 0, 678))
            .to.emit(token1, 'Transfer')
            .withArgs(wallet.address, pool.address, 678)
            .to.not.emit(token0, 'Transfer')
          expect(await pool.feeGrowthGlobal1X128()).to.eq(
            BigNumber.from(678).mul(BigNumber.from(2).pow(128)).div(expandTo18Decimals(2))
          )
        })
        it('allows donating token0 and token1 together', async () => {
          await expect(flash(0, 0, constants.AddressZero, 789, 1234))
            .to.emit(token0, 'Transfer')
            .withArgs(wallet.address, pool.address, 789)
            .to.emit(token1, 'Transfer')
            .withArgs(wallet.address, pool.address, 1234)

          expect(await pool.feeGrowthGlobal0X128()).to.eq(
            BigNumber.from(789).mul(BigNumber.from(2).pow(128)).div(expandTo18Decimals(2))
          )
          expect(await pool.feeGrowthGlobal1X128()).to.eq(
            BigNumber.from(1234).mul(BigNumber.from(2).pow(128)).div(expandTo18Decimals(2))
          )
        })
      })

      describe('fee on', () => {
        beforeEach('turn protocol fee on', async () => {
          await pool.setFeeProtocol(6, 6)
        })

        it('emits an event', async () => {
          await expect(flash(1001, 2001, other.address))
            .to.emit(pool, 'Flash')
            .withArgs(swapTarget.address, other.address, 1001, 2001, 4, 7)
        })

        it('increases the fee growth by the expected amount', async () => {
          await flash(2002, 4004, other.address)

          const { token0: token0ProtocolFees, token1: token1ProtocolFees } = await pool.protocolFees()
          expect(token0ProtocolFees).to.eq(1)
          expect(token1ProtocolFees).to.eq(2)

          expect(await pool.feeGrowthGlobal0X128()).to.eq(
            BigNumber.from(6).mul(BigNumber.from(2).pow(128)).div(expandTo18Decimals(2))
          )
          expect(await pool.feeGrowthGlobal1X128()).to.eq(
            BigNumber.from(11).mul(BigNumber.from(2).pow(128)).div(expandTo18Decimals(2))
          )
        })
        it('allows donating token0', async () => {
          await expect(flash(0, 0, constants.AddressZero, 567, 0))
            .to.emit(token0, 'Transfer')
            .withArgs(wallet.address, pool.address, 567)
            .to.not.emit(token1, 'Transfer')

          const { token0: token0ProtocolFees } = await pool.protocolFees()
          expect(token0ProtocolFees).to.eq(94)

          expect(await pool.feeGrowthGlobal0X128()).to.eq(
            BigNumber.from(473).mul(BigNumber.from(2).pow(128)).div(expandTo18Decimals(2))
          )
        })
        it('allows donating token1', async () => {
          await expect(flash(0, 0, constants.AddressZero, 0, 678))
            .to.emit(token1, 'Transfer')
            .withArgs(wallet.address, pool.address, 678)
            .to.not.emit(token0, 'Transfer')

          const { token1: token1ProtocolFees } = await pool.protocolFees()
          expect(token1ProtocolFees).to.eq(113)

          expect(await pool.feeGrowthGlobal1X128()).to.eq(
            BigNumber.from(565).mul(BigNumber.from(2).pow(128)).div(expandTo18Decimals(2))
          )
        })
        it('allows donating token0 and token1 together', async () => {
          await expect(flash(0, 0, constants.AddressZero, 789, 1234))
            .to.emit(token0, 'Transfer')
            .withArgs(wallet.address, pool.address, 789)
            .to.emit(token1, 'Transfer')
            .withArgs(wallet.address, pool.address, 1234)

          const { token0: token0ProtocolFees, token1: token1ProtocolFees } = await pool.protocolFees()
          expect(token0ProtocolFees).to.eq(131)
          expect(token1ProtocolFees).to.eq(205)

          expect(await pool.feeGrowthGlobal0X128()).to.eq(
            BigNumber.from(658).mul(BigNumber.from(2).pow(128)).div(expandTo18Decimals(2))
          )
          expect(await pool.feeGrowthGlobal1X128()).to.eq(
            BigNumber.from(1029).mul(BigNumber.from(2).pow(128)).div(expandTo18Decimals(2))
          )
        })
      })
    })
  })

  describe('#increaseObservationCardinalityNext', () => {
    it('cannot be called before initialization', async () => {
      await expect(pool.increaseObservationCardinalityNext(2)).to.be.reverted
    })
    describe('after initialization', () => {
      beforeEach('initialize the pool', () => pool.initialize(encodePriceSqrt(1, 1)))
      it('oracle starting state after initialization', async () => {
        const { observationCardinality, observationIndex, observationCardinalityNext } = await pool.slot0()
        expect(observationCardinality).to.eq(1)
        expect(observationIndex).to.eq(0)
        expect(observationCardinalityNext).to.eq(1)
        const {
          secondsPerLiquidityCumulativeX128,
          tickCumulative,
          initialized,
          blockTimestamp,
        } = await pool.observations(0)
        expect(secondsPerLiquidityCumulativeX128).to.eq(0)
        expect(tickCumulative).to.eq(0)
        expect(initialized).to.eq(true)
        expect(blockTimestamp).to.eq(TEST_POOL_START_TIME)
      })
      it('increases observation cardinality next', async () => {
        await pool.increaseObservationCardinalityNext(2)
        const { observationCardinality, observationIndex, observationCardinalityNext } = await pool.slot0()
        expect(observationCardinality).to.eq(1)
        expect(observationIndex).to.eq(0)
        expect(observationCardinalityNext).to.eq(2)
      })
      it('is no op if target is already exceeded', async () => {
        await pool.increaseObservationCardinalityNext(5)
        await pool.increaseObservationCardinalityNext(3)
        const { observationCardinality, observationIndex, observationCardinalityNext } = await pool.slot0()
        expect(observationCardinality).to.eq(1)
        expect(observationIndex).to.eq(0)
        expect(observationCardinalityNext).to.eq(5)
      })
    })
  })

  describe('#setFeeProtocol', () => {
    beforeEach('initialize the pool', async () => {
      await pool.initialize(encodePriceSqrt(1, 1))
    })

    it('can only be called by factory owner', async () => {
      await expect(pool.connect(other).setFeeProtocol(5, 5)).to.be.reverted
    })
    it('fails if fee is lt 4 or gt 10', async () => {
      await expect(pool.setFeeProtocol(3, 3)).to.be.reverted
      await expect(pool.setFeeProtocol(6, 3)).to.be.reverted
      await expect(pool.setFeeProtocol(3, 6)).to.be.reverted
      await expect(pool.setFeeProtocol(11, 11)).to.be.reverted
      await expect(pool.setFeeProtocol(6, 11)).to.be.reverted
      await expect(pool.setFeeProtocol(11, 6)).to.be.reverted
    })
    it('succeeds for fee of 4', async () => {
      await pool.setFeeProtocol(4, 4)
    })
    it('succeeds for fee of 10', async () => {
      await pool.setFeeProtocol(10, 10)
    })
    it('sets protocol fee', async () => {
      await pool.setFeeProtocol(7, 7)
      expect((await pool.slot0()).feeProtocol).to.eq(119)
    })
    it('can change protocol fee', async () => {
      await pool.setFeeProtocol(7, 7)
      await pool.setFeeProtocol(5, 8)
      expect((await pool.slot0()).feeProtocol).to.eq(133)
    })
    it('can turn off protocol fee', async () => {
      await pool.setFeeProtocol(4, 4)
      await pool.setFeeProtocol(0, 0)
      expect((await pool.slot0()).feeProtocol).to.eq(0)
    })
    it('emits an event when turned on', async () => {
      await expect(pool.setFeeProtocol(7, 7)).to.be.emit(pool, 'SetFeeProtocol').withArgs(0, 0, 7, 7)
    })
    it('emits an event when turned off', async () => {
      await pool.setFeeProtocol(7, 5)
      await expect(pool.setFeeProtocol(0, 0)).to.be.emit(pool, 'SetFeeProtocol').withArgs(7, 5, 0, 0)
    })
    it('emits an event when changed', async () => {
      await pool.setFeeProtocol(4, 10)
      await expect(pool.setFeeProtocol(6, 8)).to.be.emit(pool, 'SetFeeProtocol').withArgs(4, 10, 6, 8)
    })
    it('emits an event when unchanged', async () => {
      await pool.setFeeProtocol(5, 9)
      await expect(pool.setFeeProtocol(5, 9)).to.be.emit(pool, 'SetFeeProtocol').withArgs(5, 9, 5, 9)
    })
  })

  describe('#lock', () => {
    beforeEach('initialize the pool', async () => {
      await pool.initialize(encodePriceSqrt(1, 1))
      await mint(wallet.address, minTick, maxTick, expandTo18Decimals(1))
    })

    it('cannot reenter from swap callback', async () => {
      const reentrant = (await (
        await ethers.getContractFactory('TestUniswapV3ReentrantCallee')
      ).deploy()) as TestUniswapV3ReentrantCallee

      // the tests happen in solidity
      await expect(reentrant.swapToReenter(pool.address)).to.be.revertedWith('Unable to reenter')
    })
  })

  describe('#snapshotCumulativesInside', () => {
    const tickLower = -TICK_SPACINGS[FeeAmount.MEDIUM]
    const tickUpper = TICK_SPACINGS[FeeAmount.MEDIUM]
    const tickSpacing = TICK_SPACINGS[FeeAmount.MEDIUM]
    beforeEach(async () => {
      await pool.initialize(encodePriceSqrt(1, 1))
      await mint(wallet.address, tickLower, tickUpper, 10)
    })
    it('throws if ticks are in reverse order', async () => {
      await expect(pool.snapshotCumulativesInside(tickUpper, tickLower)).to.be.reverted
    })
    it('throws if ticks are the same', async () => {
      await expect(pool.snapshotCumulativesInside(tickUpper, tickUpper)).to.be.reverted
    })
    it('throws if tick lower is too low', async () => {
      await expect(pool.snapshotCumulativesInside(getMinTick(tickSpacing) - 1, tickUpper)).be.reverted
    })
    it('throws if tick upper is too high', async () => {
      await expect(pool.snapshotCumulativesInside(tickLower, getMaxTick(tickSpacing) + 1)).be.reverted
    })
    it('throws if tick lower is not initialized', async () => {
      await expect(pool.snapshotCumulativesInside(tickLower - tickSpacing, tickUpper)).to.be.reverted
    })
    it('throws if tick upper is not initialized', async () => {
      await expect(pool.snapshotCumulativesInside(tickLower, tickUpper + tickSpacing)).to.be.reverted
    })
    it('is zero immediately after initialize', async () => {
      const {
        secondsPerLiquidityInsideX128,
        tickCumulativeInside,
        secondsInside,
      } = await pool.snapshotCumulativesInside(tickLower, tickUpper)
      expect(secondsPerLiquidityInsideX128).to.eq(0)
      expect(tickCumulativeInside).to.eq(0)
      expect(secondsInside).to.eq(0)
    })
    it('increases by expected amount when time elapses in the range', async () => {
      await pool.advanceTime(5)
      const {
        secondsPerLiquidityInsideX128,
        tickCumulativeInside,
        secondsInside,
      } = await pool.snapshotCumulativesInside(tickLower, tickUpper)
      expect(secondsPerLiquidityInsideX128).to.eq(BigNumber.from(5).shl(128).div(10))
      expect(tickCumulativeInside, 'tickCumulativeInside').to.eq(0)
      expect(secondsInside).to.eq(5)
    })
    it('does not account for time increase above range', async () => {
      await pool.advanceTime(5)
      await swapToHigherPrice(encodePriceSqrt(2, 1), wallet.address)
      await pool.advanceTime(7)
      const {
        secondsPerLiquidityInsideX128,
        tickCumulativeInside,
        secondsInside,
      } = await pool.snapshotCumulativesInside(tickLower, tickUpper)
      expect(secondsPerLiquidityInsideX128).to.eq(BigNumber.from(5).shl(128).div(10))
      expect(tickCumulativeInside, 'tickCumulativeInside').to.eq(0)
      expect(secondsInside).to.eq(5)
    })
    it('does not account for time increase below range', async () => {
      await pool.advanceTime(5)
      await swapToLowerPrice(encodePriceSqrt(1, 2), wallet.address)
      await pool.advanceTime(7)
      const {
        secondsPerLiquidityInsideX128,
        tickCumulativeInside,
        secondsInside,
      } = await pool.snapshotCumulativesInside(tickLower, tickUpper)
      expect(secondsPerLiquidityInsideX128).to.eq(BigNumber.from(5).shl(128).div(10))
      // tick is 0 for 5 seconds, then not in range
      expect(tickCumulativeInside, 'tickCumulativeInside').to.eq(0)
      expect(secondsInside).to.eq(5)
    })
    it('time increase below range is not counted', async () => {
      await swapToLowerPrice(encodePriceSqrt(1, 2), wallet.address)
      await pool.advanceTime(5)
      await swapToHigherPrice(encodePriceSqrt(1, 1), wallet.address)
      await pool.advanceTime(7)
      const {
        secondsPerLiquidityInsideX128,
        tickCumulativeInside,
        secondsInside,
      } = await pool.snapshotCumulativesInside(tickLower, tickUpper)
      expect(secondsPerLiquidityInsideX128).to.eq(BigNumber.from(7).shl(128).div(10))
      // tick is not in range then tick is 0 for 7 seconds
      expect(tickCumulativeInside, 'tickCumulativeInside').to.eq(0)
      expect(secondsInside).to.eq(7)
    })
    it('time increase above range is not counted', async () => {
      await swapToHigherPrice(encodePriceSqrt(2, 1), wallet.address)
      await pool.advanceTime(5)
      await swapToLowerPrice(encodePriceSqrt(1, 1), wallet.address)
      await pool.advanceTime(7)
      const {
        secondsPerLiquidityInsideX128,
        tickCumulativeInside,
        secondsInside,
      } = await pool.snapshotCumulativesInside(tickLower, tickUpper)
      expect(secondsPerLiquidityInsideX128).to.eq(BigNumber.from(7).shl(128).div(10))
      expect((await pool.slot0()).tick).to.eq(-1) // justify the -7 tick cumulative inside value
      expect(tickCumulativeInside, 'tickCumulativeInside').to.eq(-7)
      expect(secondsInside).to.eq(7)
    })
    it('positions minted after time spent', async () => {
      await pool.advanceTime(5)
      await mint(wallet.address, tickUpper, getMaxTick(tickSpacing), 15)
      await swapToHigherPrice(encodePriceSqrt(2, 1), wallet.address)
      await pool.advanceTime(8)
      const {
        secondsPerLiquidityInsideX128,
        tickCumulativeInside,
        secondsInside,
      } = await pool.snapshotCumulativesInside(tickUpper, getMaxTick(tickSpacing))
      expect(secondsPerLiquidityInsideX128).to.eq(BigNumber.from(8).shl(128).div(15))
      // the tick of 2/1 is 6931
      // 8 seconds * 6931 = 55448
      expect(tickCumulativeInside, 'tickCumulativeInside').to.eq(55448)
      expect(secondsInside).to.eq(8)
    })
    it('overlapping liquidity is aggregated', async () => {
      await mint(wallet.address, tickLower, getMaxTick(tickSpacing), 15)
      await pool.advanceTime(5)
      await swapToHigherPrice(encodePriceSqrt(2, 1), wallet.address)
      await pool.advanceTime(8)
      const {
        secondsPerLiquidityInsideX128,
        tickCumulativeInside,
        secondsInside,
      } = await pool.snapshotCumulativesInside(tickLower, tickUpper)
      expect(secondsPerLiquidityInsideX128).to.eq(BigNumber.from(5).shl(128).div(25))
      expect(tickCumulativeInside, 'tickCumulativeInside').to.eq(0)
      expect(secondsInside).to.eq(5)
    })
    it('relative behavior of snapshots', async () => {
      await pool.advanceTime(5)
      await mint(wallet.address, getMinTick(tickSpacing), tickLower, 15)
      const {
        secondsPerLiquidityInsideX128: secondsPerLiquidityInsideX128Start,
        tickCumulativeInside: tickCumulativeInsideStart,
        secondsInside: secondsInsideStart,
      } = await pool.snapshotCumulativesInside(getMinTick(tickSpacing), tickLower)
      await pool.advanceTime(8)
      // 13 seconds in starting range, then 3 seconds in newly minted range
      await swapToLowerPrice(encodePriceSqrt(1, 2), wallet.address)
      await pool.advanceTime(3)
      const {
        secondsPerLiquidityInsideX128,
        tickCumulativeInside,
        secondsInside,
      } = await pool.snapshotCumulativesInside(getMinTick(tickSpacing), tickLower)
      const expectedDiffSecondsPerLiquidity = BigNumber.from(3).shl(128).div(15)
      expect(secondsPerLiquidityInsideX128.sub(secondsPerLiquidityInsideX128Start)).to.eq(
        expectedDiffSecondsPerLiquidity
      )
      expect(secondsPerLiquidityInsideX128).to.not.eq(expectedDiffSecondsPerLiquidity)
      // the tick is the one corresponding to the price of 1/2, or log base 1.0001 of 0.5
      // this is -6932, and 3 seconds have passed, so the cumulative computed from the diff equals 6932 * 3
      expect(tickCumulativeInside.sub(tickCumulativeInsideStart), 'tickCumulativeInside').to.eq(-20796)
      expect(secondsInside - secondsInsideStart).to.eq(3)
      expect(secondsInside).to.not.eq(3)
    })
  })

  describe('fees overflow scenarios', async () => {
    it('up to max uint 128', async () => {
      await pool.initialize(encodePriceSqrt(1, 1))
      await mint(wallet.address, minTick, maxTick, 1)
      await flash(0, 0, wallet.address, MaxUint128, MaxUint128)

      const [feeGrowthGlobal0X128, feeGrowthGlobal1X128] = await Promise.all([
        pool.feeGrowthGlobal0X128(),
        pool.feeGrowthGlobal1X128(),
      ])
      // all 1s in first 128 bits
      expect(feeGrowthGlobal0X128).to.eq(MaxUint128.shl(128))
      expect(feeGrowthGlobal1X128).to.eq(MaxUint128.shl(128))
      await pool.burn(minTick, maxTick, 0)
      const { amount0, amount1 } = await pool.callStatic.collect(
        wallet.address,
        minTick,
        maxTick,
        MaxUint128,
        MaxUint128
      )
      expect(amount0).to.eq(MaxUint128)
      expect(amount1).to.eq(MaxUint128)
    })

    it('overflow max uint 128', async () => {
      await pool.initialize(encodePriceSqrt(1, 1))
      await mint(wallet.address, minTick, maxTick, 1)
      await flash(0, 0, wallet.address, MaxUint128, MaxUint128)
      await flash(0, 0, wallet.address, 1, 1)

      const [feeGrowthGlobal0X128, feeGrowthGlobal1X128] = await Promise.all([
        pool.feeGrowthGlobal0X128(),
        pool.feeGrowthGlobal1X128(),
      ])
      // all 1s in first 128 bits
      expect(feeGrowthGlobal0X128).to.eq(0)
      expect(feeGrowthGlobal1X128).to.eq(0)
      await pool.burn(minTick, maxTick, 0)
      const { amount0, amount1 } = await pool.callStatic.collect(
        wallet.address,
        minTick,
        maxTick,
        MaxUint128,
        MaxUint128
      )
      // fees burned
      expect(amount0).to.eq(0)
      expect(amount1).to.eq(0)
    })

    it('overflow max uint 128 after poke burns fees owed to 0', async () => {
      await pool.initialize(encodePriceSqrt(1, 1))
      await mint(wallet.address, minTick, maxTick, 1)
      await flash(0, 0, wallet.address, MaxUint128, MaxUint128)
      await pool.burn(minTick, maxTick, 0)
      await flash(0, 0, wallet.address, 1, 1)
      await pool.burn(minTick, maxTick, 0)

      const { amount0, amount1 } = await pool.callStatic.collect(
        wallet.address,
        minTick,
        maxTick,
        MaxUint128,
        MaxUint128
      )
      // fees burned
      expect(amount0).to.eq(0)
      expect(amount1).to.eq(0)
    })

    it('two positions at the same snapshot', async () => {
      await pool.initialize(encodePriceSqrt(1, 1))
      await mint(wallet.address, minTick, maxTick, 1)
      await mint(other.address, minTick, maxTick, 1)
      await flash(0, 0, wallet.address, MaxUint128, 0)
      await flash(0, 0, wallet.address, MaxUint128, 0)
      const feeGrowthGlobal0X128 = await pool.feeGrowthGlobal0X128()
      expect(feeGrowthGlobal0X128).to.eq(MaxUint128.shl(128))
      await flash(0, 0, wallet.address, 2, 0)
      await pool.burn(minTick, maxTick, 0)
      await pool.connect(other).burn(minTick, maxTick, 0)
      let { amount0 } = await pool.callStatic.collect(wallet.address, minTick, maxTick, MaxUint128, MaxUint128)
      expect(amount0, 'amount0 of wallet').to.eq(0)
      ;({ amount0 } = await pool
        .connect(other)
        .callStatic.collect(other.address, minTick, maxTick, MaxUint128, MaxUint128))
      expect(amount0, 'amount0 of other').to.eq(0)
    })

    it('two positions 1 wei of fees apart overflows exactly once', async () => {
      await pool.initialize(encodePriceSqrt(1, 1))
      await mint(wallet.address, minTick, maxTick, 1)
      await flash(0, 0, wallet.address, 1, 0)
      await mint(other.address, minTick, maxTick, 1)
      await flash(0, 0, wallet.address, MaxUint128, 0)
      await flash(0, 0, wallet.address, MaxUint128, 0)
      const feeGrowthGlobal0X128 = await pool.feeGrowthGlobal0X128()
      expect(feeGrowthGlobal0X128).to.eq(0)
      await flash(0, 0, wallet.address, 2, 0)
      await pool.burn(minTick, maxTick, 0)
      await pool.connect(other).burn(minTick, maxTick, 0)
      let { amount0 } = await pool.callStatic.collect(wallet.address, minTick, maxTick, MaxUint128, MaxUint128)
      expect(amount0, 'amount0 of wallet').to.eq(1)
      ;({ amount0 } = await pool
        .connect(other)
        .callStatic.collect(other.address, minTick, maxTick, MaxUint128, MaxUint128))
      expect(amount0, 'amount0 of other').to.eq(0)
    })
  })

  describe('swap underpayment tests', () => {
    let underpay: TestUniswapV3SwapPay
    beforeEach('deploy swap test', async () => {
      const underpayFactory = await ethers.getContractFactory('TestUniswapV3SwapPay')
      underpay = (await underpayFactory.deploy()) as TestUniswapV3SwapPay
      await token0.approve(underpay.address, constants.MaxUint256)
      await token1.approve(underpay.address, constants.MaxUint256)
      await pool.initialize(encodePriceSqrt(1, 1))
      await mint(wallet.address, minTick, maxTick, expandTo18Decimals(1))
    })

    it('underpay zero for one and exact in', async () => {
      await expect(
        underpay.swap(pool.address, wallet.address, true, MIN_SQRT_RATIO.add(1), 1000, 1, 0)
      ).to.be.revertedWith('IIA')
    })
    it('pay in the wrong token zero for one and exact in', async () => {
      await expect(
        underpay.swap(pool.address, wallet.address, true, MIN_SQRT_RATIO.add(1), 1000, 0, 2000)
      ).to.be.revertedWith('IIA')
    })
    it('overpay zero for one and exact in', async () => {
      await expect(
        underpay.swap(pool.address, wallet.address, true, MIN_SQRT_RATIO.add(1), 1000, 2000, 0)
      ).to.not.be.revertedWith('IIA')
    })
    it('underpay zero for one and exact out', async () => {
      await expect(
        underpay.swap(pool.address, wallet.address, true, MIN_SQRT_RATIO.add(1), -1000, 1, 0)
      ).to.be.revertedWith('IIA')
    })
    it('pay in the wrong token zero for one and exact out', async () => {
      await expect(
        underpay.swap(pool.address, wallet.address, true, MIN_SQRT_RATIO.add(1), -1000, 0, 2000)
      ).to.be.revertedWith('IIA')
    })
    it('overpay zero for one and exact out', async () => {
      await expect(
        underpay.swap(pool.address, wallet.address, true, MIN_SQRT_RATIO.add(1), -1000, 2000, 0)
      ).to.not.be.revertedWith('IIA')
    })
    it('underpay one for zero and exact in', async () => {
      await expect(
        underpay.swap(pool.address, wallet.address, false, MAX_SQRT_RATIO.sub(1), 1000, 0, 1)
      ).to.be.revertedWith('IIA')
    })
    it('pay in the wrong token one for zero and exact in', async () => {
      await expect(
        underpay.swap(pool.address, wallet.address, false, MAX_SQRT_RATIO.sub(1), 1000, 2000, 0)
      ).to.be.revertedWith('IIA')
    })
    it('overpay one for zero and exact in', async () => {
      await expect(
        underpay.swap(pool.address, wallet.address, false, MAX_SQRT_RATIO.sub(1), 1000, 0, 2000)
      ).to.not.be.revertedWith('IIA')
    })
    it('underpay one for zero and exact out', async () => {
      await expect(
        underpay.swap(pool.address, wallet.address, false, MAX_SQRT_RATIO.sub(1), -1000, 0, 1)
      ).to.be.revertedWith('IIA')
    })
    it('pay in the wrong token one for zero and exact out', async () => {
      await expect(
        underpay.swap(pool.address, wallet.address, false, MAX_SQRT_RATIO.sub(1), -1000, 2000, 0)
      ).to.be.revertedWith('IIA')
    })
    it('overpay one for zero and exact out', async () => {
      await expect(
        underpay.swap(pool.address, wallet.address, false, MAX_SQRT_RATIO.sub(1), -1000, 0, 2000)
      ).to.not.be.revertedWith('IIA')
    })
  })
})
"""
