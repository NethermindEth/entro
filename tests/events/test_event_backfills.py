import logging

from eth_utils import to_checksum_address

from python_eth_amm.events import backfill_events
from python_eth_amm.events.main import _get_last_backfilled_block
from python_eth_amm.uniswap_v3 import UniswapV3Pool
from python_eth_amm.uniswap_v3.db import UniV3MintEvent, _parse_uniswap_events


class TestGeneralizedBackfill:
    def test_backfill_events_chunk_sizes(
        self, w3_archive_node, db_session, test_logger
    ):
        weth_wbtc_pool = w3_archive_node.eth.contract(
            to_checksum_address("0xcbcdf9626bc03e24f779434178a73a0b4bad62ed"),
            abi=UniswapV3Pool.get_abi(),
        )

        db_session.query(UniV3MintEvent).filter(
            UniV3MintEvent.contract_address == weth_wbtc_pool.address
        ).delete()

        backfill_events(
            contract=weth_wbtc_pool,
            event_name="Mint",
            db_session=db_session,
            db_model=UniV3MintEvent,
            model_parsing_func=_parse_uniswap_events,
            from_block=12_369_821,
            to_block=12_400_000,
            logger=test_logger,
            chunk_size=1_000_000,
        )

        large_chunk_mint_events = (
            db_session.query(UniV3MintEvent)
            .filter(UniV3MintEvent.contract_address == weth_wbtc_pool.address)
            .all()
        )

        db_session.query(UniV3MintEvent).filter(
            UniV3MintEvent.contract_address == weth_wbtc_pool.address
        ).delete()

        backfill_events(
            contract=weth_wbtc_pool,
            event_name="Mint",
            db_session=db_session,
            db_model=UniV3MintEvent,
            model_parsing_func=_parse_uniswap_events,
            from_block=12_369_821,
            to_block=12_400_000,
            logger=test_logger,
            chunk_size=1_000,
        )

        small_chunk_mint_events = (
            db_session.query(UniV3MintEvent)
            .filter(UniV3MintEvent.contract_address == weth_wbtc_pool.address)
            .all()
        )

        assert len(small_chunk_mint_events) == 409 == len(large_chunk_mint_events)
        assert (
            small_chunk_mint_events[0].block_number
            == 12369821
            == large_chunk_mint_events[0].block_number
        )
        assert (
            small_chunk_mint_events[0].log_index
            == 48
            == large_chunk_mint_events[0].log_index
        )
        assert (
            small_chunk_mint_events[-1].block_number
            == 12399993
            == large_chunk_mint_events[-1].block_number
        )
        assert (
            small_chunk_mint_events[-1].log_index
            == 143
            == large_chunk_mint_events[-1].log_index
        )

    def test_backfill_loads_db_block(
        self, w3_archive_node, db_session, test_logger, caplog
    ):
        weth_wbtc_pool = w3_archive_node.eth.contract(
            to_checksum_address("0xcbcdf9626bc03e24f779434178a73a0b4bad62ed"),
            abi=UniswapV3Pool.get_abi(),
        )

        db_session.query(UniV3MintEvent).filter(
            UniV3MintEvent.contract_address == weth_wbtc_pool.address
        ).delete()

        backfill_events(
            contract=weth_wbtc_pool,
            event_name="Mint",
            db_session=db_session,
            db_model=UniV3MintEvent,
            model_parsing_func=_parse_uniswap_events,
            from_block=12_369_821,
            to_block=12_400_000,
            logger=test_logger,
            chunk_size=100_000,
        )

        last_event = (
            db_session.query(UniV3MintEvent)
            .filter(UniV3MintEvent.contract_address == weth_wbtc_pool.address)
            .order_by(UniV3MintEvent.block_number.desc())
            .limit(1)
            .first()
        )

        assert last_event.block_number == _get_last_backfilled_block(
            db_session, weth_wbtc_pool.address, UniV3MintEvent
        )

        with caplog.at_level(logging.DEBUG):
            backfill_events(
                contract=weth_wbtc_pool,
                event_name="Mint",
                db_session=db_session,
                db_model=UniV3MintEvent,
                model_parsing_func=_parse_uniswap_events,
                from_block=12_369_821,
                to_block=12_600_000,
                logger=test_logger,
                chunk_size=100_000,
            )

        assert f"Last block in DB: {last_event.block_number}" in [
            rec.message for rec in caplog.records
        ]
