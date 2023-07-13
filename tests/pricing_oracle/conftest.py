# pylint: skip-file
import os
from typing import Optional

import pytest
from eth_utils import to_checksum_address as tca

from python_eth_amm import PoolFactory
from python_eth_amm.pricing_oracle import PricingOracle
from python_eth_amm.pricing_oracle.db import (
    BackfilledPools,
    BlockTimestamps,
    TokenPrices,
)


@pytest.fixture(autouse=True)
def db_teardown(db_session):
    yield
    db_session.query(TokenPrices).delete()
    db_session.query(BackfilledPools).delete()
    db_session.commit()


@pytest.fixture(name="initialize_empty_oracle")
def fixture_initialize_empty_oracle(w3_archive_node, db_session, test_logger):
    def _initialize_empty_oracle(
        factory: Optional[PoolFactory] = None,
        timestamp_resolution: int = 10_000,
    ) -> PricingOracle:
        if factory is None:
            factory = PoolFactory(
                sqlalchemy_uri=os.environ.get(
                    "SQLALCHEMY_DB_URI", "sqlite:///:memory:"
                ),
                w3=w3_archive_node,
                logger=test_logger,
            )
        return factory.initialize_pricing_oracle(
            timestamp_resolution=timestamp_resolution
        )

    return _initialize_empty_oracle


@pytest.fixture(name="add_test_backfill")
def fixture_add_test_backfill(db_session):
    def _add_test_backfill():
        db_session.add(
            BackfilledPools(
                pool_id=tca("0xfad57d2039c21811c8f2b5d5b65308aa99d31559"),
                priced_token=tca("0x514910771af9ca656af840dff83e8264ecf986ca"),
                reference_token=tca("0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"),
                backfill_start=14_000_000,
                backfill_end=15_000_000,
            )
        )
        db_session.commit()

    return _add_test_backfill


@pytest.fixture(name="delete_timestamps")
def fixture_delete_timestamps(db_session):
    def _delete_timestamps():
        db_session.query(BlockTimestamps).delete()
        db_session.commit()

    return _delete_timestamps


@pytest.fixture(name="delete_prices_for_token")
def fixture_delete_prices_for_token(db_session):
    def _delete_prices_for_token(token_address: str):
        db_session.query(TokenPrices).filter(
            TokenPrices.token_id == token_address
        ).delete()
        db_session.commit()

    return _delete_prices_for_token


@pytest.fixture(name="delete_backfill_for_pool")
def fixture_delete_backfill_for_pool(db_session):
    def _delete_backfill_for_pool(pool_address: str):
        db_session.query(BackfilledPools).filter(
            BackfilledPools.pool_id == pool_address
        ).delete()
        db_session.commit()

    return _delete_backfill_for_pool
