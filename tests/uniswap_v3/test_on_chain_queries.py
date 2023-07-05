import pytest
from eth_utils import to_checksum_address

from python_eth_amm.events import backfill_events, query_events_from_db
from python_eth_amm.exceptions import UniswapV3Revert
from python_eth_amm.math import TickMathModule
from python_eth_amm.uniswap_v3.chain_interface import (
    _get_pos_from_bitmap,
    fetch_initialization_block,
    fetch_liquidity,
    fetch_pool_immutables,
    fetch_pool_state,
    fetch_positions,
    fetch_slot_0,
)
from python_eth_amm.uniswap_v3.db import UniV3MintEvent, _parse_uniswap_events


class TestPoolInitialization:
    def test_fetches_initialization_block(self, usdc_weth_contract):
        assert fetch_initialization_block(usdc_weth_contract) == 12370624

    def test_querying_old_pool_raises(self, exact_math_factory, w3_archive_node):
        with pytest.raises(UniswapV3Revert):
            exact_math_factory.initialize_from_chain(
                pool_type="uniswap_v3",
                pool_address=to_checksum_address(
                    "0x8ad599c3a0ff1de082011efddc58f1908eb6e6d8"
                ),
                at_block=12370000,
            )

    def test_position_owners_match_mint_events(
        self, exact_math_factory, w3_archive_node, db_session
    ):
        db_session.query(UniV3MintEvent).filter(
            UniV3MintEvent.contract_address
            == "0x8ad599c3a0ff1de082011efddc58f1908eb6e6d8"
            and UniV3MintEvent.block_number <= 12_400_000
        ).delete()

        usdc_weth_pool = exact_math_factory.initialize_from_chain(
            pool_type="uniswap_v3",
            pool_address=to_checksum_address(
                "0x8ad599c3a0ff1de082011efddc58f1908eb6e6d8"
            ),
            at_block=12400000,
        )

        mint_events = query_events_from_db(
            db_session=db_session,
            db_model=UniV3MintEvent,
            to_block=12400000,
            contract_address=usdc_weth_pool.immutables.pool_address
        )

        minting_lp_addresses = set([event.owner for event in mint_events])
        for key, data in usdc_weth_pool.positions.items():
            assert key[0] in minting_lp_addresses

    def test_initialized_ticks_match_positions(
        self, exact_math_factory, w3_archive_node
    ):
        usdc_weth_pool = exact_math_factory.initialize_from_chain(
            pool_type="uniswap_v3",
            pool_address=to_checksum_address(
                "0x8ad599c3a0ff1de082011efddc58f1908eb6e6d8"
            ),
            at_block=12400000,
        )

        position_keys = usdc_weth_pool.positions.keys()
        active_ticks = set(
            [key[1] for key in position_keys] + [key[2] for key in position_keys]
        )

        for tick_num in usdc_weth_pool.ticks.keys():
            assert tick_num in active_ticks

            assert tick_num % usdc_weth_pool.immutables.tick_spacing == 0
            assert tick_num >= TickMathModule.MIN_TICK
            assert tick_num <= TickMathModule.MAX_TICK


class TestFetchOnChainLiquidity:
    def test_bitmap_returns_none_on_zero(self):
        bitmap = int(("0" * 256), 2)
        assert _get_pos_from_bitmap(bitmap) == []

    def test_bitmap_returns_correct_number_of_bits(self, get_random_binary_string):
        bitmap = get_random_binary_string(256)
        tick_queue = _get_pos_from_bitmap(int(bitmap, 2))
        assert len(tick_queue) == bitmap.count("1")

    def test_fetch_liquidity_raises_uninintialized_pool(
        self, w3_archive_node, usdc_weth_contract, test_logger
    ):
        with pytest.raises(UniswapV3Revert):
            fetch_liquidity(
                contract=usdc_weth_contract,
                tick_spacing=10,
                logger=test_logger,
                at_block=12370000,
            )

    def test_liquidity_net_is_zero_established_pool_low_fee(
        self, w3_archive_node, usdc_weth_contract, test_logger
    ):
        liquidity = fetch_liquidity(
            contract=usdc_weth_contract,
            tick_spacing=10,
            logger=test_logger,
            at_block=15000000,
        )
        assert sum([liq.liquidity_net for liq in liquidity.values()]) == 0

    def test_liquidity_net_is_zero_established_pool_medium_fee(
        self, w3_archive_node, wbtc_weth_contract, test_logger
    ):
        liquidity = fetch_liquidity(
            contract=wbtc_weth_contract,
            tick_spacing=60,
            logger=test_logger,
            at_block=15000000,
        )
        assert sum([liq.liquidity_net for liq in liquidity.values()]) == 0

    def test_liquidity_net_is_zero_established_pool_high_fee(
        self, w3_archive_node, usdt_weth_contract, test_logger
    ):
        liquidity = fetch_liquidity(
            contract=usdt_weth_contract,
            tick_spacing=200,
            logger=test_logger,
            at_block=15000000,
        )
        assert sum([liq.liquidity_net for liq in liquidity.values()]) == 0


class TestFetchPositions:
    def test_fetch_positions_for_invalid_pool_raises(
        self, w3_archive_node, usdc_weth_contract, test_logger, db_session
    ):
        with pytest.raises(UniswapV3Revert):
            fetch_positions(
                contract=usdc_weth_contract,
                logger=test_logger,
                db_session=db_session,
                initialization_block=12370624,
                at_block=12370000,
            )

    def test_fetch_positions_on_new_pool_succeeds_and_returns_zero(
        self, w3_archive_node, usdc_weth_contract, test_logger, db_session
    ):
        positions = fetch_positions(
            contract=usdc_weth_contract,
            logger=test_logger,
            db_session=db_session,
            initialization_block=12370624,
            at_block=12380000,
        )

        assert len(positions) == 243
        assert (
            positions[
                (
                    to_checksum_address("0xC36442b4a4522E871399CD717aBDD847Ab11FE88"),
                    192180,
                    193380,
                )
            ].liquidity
            == 45664982023859
        )


class TestFetchPoolState:
    def test_fetch_pool_immutables_usdc_weth(
        self, w3_archive_node, usdc_weth_contract, test_logger
    ):
        immutables = fetch_pool_immutables(
            w3=w3_archive_node,
            contract=usdc_weth_contract,
            logger=test_logger,
        )
        assert immutables.fee == 3000
        assert immutables.tick_spacing == 60
        assert immutables.max_liquidity_per_tick == 11505743598341114571880798222544994

        assert (
            immutables.token_0.address.lower()
            == "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
        )
        assert immutables.token_0.name == "USD Coin"
        assert immutables.token_0.symbol == "USDC"
        assert immutables.token_0.decimals == 6

        assert (
            immutables.token_1.address.lower()
            == "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
        )
        assert immutables.token_1.name == "Wrapped Ether"
        assert immutables.token_1.symbol == "WETH"
        assert immutables.token_1.decimals == 18

    def test_fetch_pool_state(self, w3_archive_node, usdc_weth_contract, test_logger):
        immutables = fetch_pool_immutables(
            w3=w3_archive_node,
            contract=usdc_weth_contract,
            logger=test_logger,
        )

        state = fetch_pool_state(
            contract=usdc_weth_contract,
            token_0=immutables.token_0,
            token_1=immutables.token_1,
            logger=test_logger,
            at_block=15_000_000,
        )
        assert state.balance_0 == 63321438203194
        assert state.balance_1 == 125957720212193473568385
        assert state.liquidity == 17783115650573390796
        assert state.fee_growth_global_0 == 2384901816825010603876380800662915
        assert state.fee_growth_global_1 == 968198056183068283229668960768177396717155


class TestFetchSlot0:
    def test_fetch_slot_0_raises_unintialized_pool(
        self, w3_archive_node, usdc_weth_contract, test_logger
    ):
        with pytest.raises(UniswapV3Revert):
            fetch_slot_0(
                contract=usdc_weth_contract,
                logger=test_logger,
                at_block=12370000,
            )

    def test_slot_0_returns_historical_snapshot(self, usdc_weth_contract, test_logger):
        slot_0 = fetch_slot_0(
            contract=usdc_weth_contract,
            logger=test_logger,
            at_block=15000000,
        )

        assert slot_0.tick == 206129
        assert slot_0.sqrt_price == 2369736745864564341698764262195618
        assert slot_0.observation_cardinality == 1440
        assert slot_0.observation_cardinality_next == 1440
        assert slot_0.observation_index == 205
        assert slot_0.fee_protocol == 0

    def test_slot_0_is_not_equal_at_different_blocks(
        self, usdc_weth_contract, test_logger
    ):
        slot_0_1 = fetch_slot_0(
            contract=usdc_weth_contract,
            logger=test_logger,
            at_block=14000000,
        )
        slot_0_2 = fetch_slot_0(
            contract=usdc_weth_contract,
            logger=test_logger,
            at_block=15000000,
        )
        assert slot_0_1 != slot_0_2
