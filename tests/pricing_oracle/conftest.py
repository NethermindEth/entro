# pylint: skip-file
import os
from typing import Optional

import pytest

from python_eth_amm import PoolFactory
from python_eth_amm.pricing_oracle import PricingOracle
from python_eth_amm.pricing_oracle.db import (
    BackfilledPools,
    BlockTimestamps,
    TokenPrices,
)


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
