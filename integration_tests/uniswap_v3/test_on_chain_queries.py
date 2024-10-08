import pytest
from eth_utils import to_checksum_address as tca

from nethermind.entro.database.models.uniswap import UniV3MintEvent
from nethermind.entro.exceptions import UniswapV3Revert
from nethermind.entro.uniswap_v3 import UniswapV3Pool
from nethermind.entro.uniswap_v3.chain_interface import (
    _get_pos_from_bitmap,
    fetch_initialization_block,
    fetch_liquidity,
    fetch_pool_immutables,
    fetch_pool_state,
    fetch_positions,
    fetch_slot_0,
)
from nethermind.entro.uniswap_v3.math import TickMathModule
from tests.resources.addresses import USDC_WETH_UNI_V3_POOL


class TestPoolInitModes:
    def test_sqrt_price_converters_fail_empty_init(self):
        pool = UniswapV3Pool()

        with pytest.raises(
            UniswapV3Revert,
            match="Method get_price_at_sqrt_ratio can only be called if pool is initialized from chain",
        ):
            pool.get_price_at_sqrt_ratio(79228162514264337593543950336)

        with pytest.raises(
            UniswapV3Revert,
            match="Method get_price_at_tick can only be called if pool is initialized from chain",
        ):
            pool.get_price_at_tick(0)

    def test_load_liquidity_mode(self, w3_archive_node, db_session):
        liquidity_pool = UniswapV3Pool.from_chain(
            w3=w3_archive_node,
            db_session=db_session,
            pool_address=USDC_WETH_UNI_V3_POOL,
            init_mode="load_liquidity",
            at_block=12380000,
        )

        assert abs(liquidity_pool.get_price_at_tick(0)) < 0.00000000001

        with pytest.raises(
            UniswapV3Revert,
            match="Method save_position_snapshot can only be called in simulation mode",
        ):
            liquidity_pool.save_position_snapshot()


class TestPoolInitialization:
    def test_fetches_initialization_block(self, usdc_weth_contract):
        assert fetch_initialization_block(usdc_weth_contract) == 12370624

    def test_querying_old_pool_raises(self, exact_math_factory):
        with pytest.raises(UniswapV3Revert):
            exact_math_factory.initialize_from_chain(
                pool_type="uniswap_v3",
                pool_address=USDC_WETH_UNI_V3_POOL,
                at_block=12370000,
            )

    def test_position_owners_match_mint_events(self, integration_db_session, integration_postgres_db, eth_archival_w3):
        usdc_weth_pool = UniswapV3Pool.from_chain(
            w3=eth_archival_w3,
            db_session=integration_db_session,
            pool_address=USDC_WETH_UNI_V3_POOL,
            init_mode="simulation",
            at_block=12400000,
        )

        mint_events = integration_db_session.query(UniV3MintEvent).all()

        minting_lp_addresses = set([event.owner for event in mint_events])
        for key, data in usdc_weth_pool.positions.items():
            assert key[0] in minting_lp_addresses

    def test_initialized_ticks_match_positions(self, integration_db_session, integration_postgres_db, eth_archival_w3):
        usdc_weth_pool = UniswapV3Pool.from_chain(
            w3=eth_archival_w3,
            db_session=integration_db_session,
            pool_address=USDC_WETH_UNI_V3_POOL,
            init_mode="simulation",
            at_block=12400000,
        )

        position_keys = usdc_weth_pool.positions.keys()
        active_ticks = set([key[1] for key in position_keys] + [key[2] for key in position_keys])

        for tick_num in usdc_weth_pool.ticks.keys():
            assert tick_num in active_ticks

            assert tick_num % usdc_weth_pool.immutables.tick_spacing == 0
            assert tick_num >= MIN_TICK
            assert tick_num <= MAX_TICK


class TestFetchOnChainLiquidity:
    def test_fetch_liquidity_raises_uninintialized_pool(self, usdc_weth_contract):
        with pytest.raises(UniswapV3Revert):
            fetch_liquidity(
                contract=usdc_weth_contract,
                tick_spacing=10,
                at_block=12370000,
            )

    def test_liquidity_net_is_zero_established_pool_low_fee(self, usdc_weth_contract):
        liquidity = fetch_liquidity(
            contract=usdc_weth_contract,
            tick_spacing=10,
            at_block=15000000,
        )
        assert sum([liq.liquidity_net for liq in liquidity.values()]) == 0

    def test_liquidity_net_is_zero_established_pool_medium_fee(self, wbtc_weth_contract):
        liquidity = fetch_liquidity(
            contract=wbtc_weth_contract,
            tick_spacing=60,
            at_block=15000000,
        )
        assert sum([liq.liquidity_net for liq in liquidity.values()]) == 0

    def test_liquidity_net_is_zero_established_pool_high_fee(self, usdt_weth_contract):
        liquidity = fetch_liquidity(
            contract=usdt_weth_contract,
            tick_spacing=200,
            at_block=15000000,
        )
        assert sum([liq.liquidity_net for liq in liquidity.values()]) == 0


class TestFetchPositions:
    def test_fetch_positions_for_invalid_pool_raises(
        self, usdc_weth_contract, integration_db_session, integration_postgres_db
    ):
        with pytest.raises(UniswapV3Revert):
            fetch_positions(
                contract=usdc_weth_contract,
                db_session=integration_db_session,
                initialization_block=12370624,
                at_block=12370000,
            )

    def test_fetch_positions_on_new_pool_succeeds_and_returns_zero(
        self, usdc_weth_contract, integration_db_session, integration_postgres_db
    ):
        positions = fetch_positions(
            contract=usdc_weth_contract,
            db_session=integration_db_session,
            initialization_block=12370624,
            at_block=12380000,
        )

        assert len(positions) == 243
        assert (
            positions[
                (
                    tca("0xC36442b4a4522E871399CD717aBDD847Ab11FE88"),
                    192180,
                    193380,
                )
            ].liquidity
            == 45664982023859
        )


class TestFetchPoolState:
    def test_fetch_pool_immutables_usdc_weth(self, usdc_weth_contract):
        immutables = fetch_pool_immutables(
            contract=usdc_weth_contract,
        )
        assert immutables.fee == 3000
        assert immutables.tick_spacing == 60
        assert immutables.max_liquidity_per_tick == 11505743598341114571880798222544994

        assert immutables.token_0.address.lower() == "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
        assert immutables.token_0.name == "USD Coin"
        assert immutables.token_0.symbol == "USDC"
        assert immutables.token_0.decimals == 6

        assert immutables.token_1.address.lower() == "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
        assert immutables.token_1.name == "Wrapped Ether"
        assert immutables.token_1.symbol == "WETH"
        assert immutables.token_1.decimals == 18

    def test_fetch_pool_state(self, usdc_weth_contract):
        immutables = fetch_pool_immutables(
            contract=usdc_weth_contract,
        )

        state = fetch_pool_state(
            contract=usdc_weth_contract,
            token_0=immutables.token_0,
            token_1=immutables.token_1,
            at_block=15_000_000,
        )
        assert state.balance_0 == 63321438203194
        assert state.balance_1 == 125957720212193473568385
        assert state.liquidity == 17783115650573390796
        assert state.fee_growth_global_0 == 2384901816825010603876380800662915
        assert state.fee_growth_global_1 == 968198056183068283229668960768177396717155


class TestFetchSlot0:
    def test_fetch_slot_0_raises_unintialized_pool(self, usdc_weth_contract):
        with pytest.raises(UniswapV3Revert):
            fetch_slot_0(
                contract=usdc_weth_contract,
                at_block=12370000,
            )

    def test_slot_0_returns_historical_snapshot(self, usdc_weth_contract):
        slot_0 = fetch_slot_0(
            contract=usdc_weth_contract,
            at_block=15000000,
        )

        assert slot_0.tick == 206129
        assert slot_0.sqrt_price == 2369736745864564341698764262195618
        assert slot_0.observation_cardinality == 1440
        assert slot_0.observation_cardinality_next == 1440
        assert slot_0.observation_index == 205
        assert slot_0.fee_protocol == 0

    def test_slot_0_is_not_equal_at_different_blocks(self, usdc_weth_contract):
        slot_0_1 = fetch_slot_0(
            contract=usdc_weth_contract,
            at_block=14000000,
        )
        slot_0_2 = fetch_slot_0(
            contract=usdc_weth_contract,
            at_block=15000000,
        )
        assert slot_0_1 != slot_0_2
