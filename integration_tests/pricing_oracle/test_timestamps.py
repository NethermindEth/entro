from datetime import date, datetime, timedelta, timezone

from python_eth_amm.backfill.utils import get_current_block_number
from python_eth_amm.database.models.migrations import migrate_up
from python_eth_amm.pricing_oracle.timestamp_converter import TimestampConverter
from python_eth_amm.types.backfill import SupportedNetwork


def test_backfills_timestamps(
    integration_postgres_db,
    integration_db_session,
    eth_rpc_url,
):
    migrate_up(integration_db_session.get_bind())

    timestamp_converter = TimestampConverter(
        network=SupportedNetwork.ethereum,
        db_session=integration_db_session,
        json_rpc=eth_rpc_url,
        resolution=100_000,
    )
    assert timestamp_converter.timestamp_resolution == 100_000

    current_block = get_current_block_number(SupportedNetwork.ethereum)

    assert len(timestamp_converter.timestamp_data) == (current_block // 100_000) + 1


def test_timestamp_conversions(
    eth_rpc_url, integration_db_session, integration_postgres_db
):
    migrate_up(integration_db_session.get_bind())

    timestamp_converter = TimestampConverter(
        network=SupportedNetwork.ethereum,
        db_session=integration_db_session,
        json_rpc=eth_rpc_url,
        resolution=10_000,
    )

    # Assert timestamps are converted to UTC datetime

    assert timestamp_converter.block_to_datetime(0) == datetime(
        2015, 7, 30, 15, 26, 28, tzinfo=timezone.utc
    )

    assert timestamp_converter.block_to_datetime(18_000_000) == datetime(
        2023, 8, 26, 16, 21, 35, tzinfo=timezone.utc
    )

    assert timestamp_converter.block_to_datetime(12_452_223) - datetime.fromtimestamp(
        1621258925, tz=timezone.utc
    ) < timedelta(minutes=10)

    # Checking Date -> Block conversions
    assert abs(timestamp_converter.datetime_to_block(date(2023, 4, 8)) - 17000009) <= 5

    # Checking DateTime -> Block conversions
    assert (
        abs(
            timestamp_converter.datetime_to_block(
                datetime(2022, 12, 18, 8, 21, 35, tzinfo=timezone.utc)
            )
            - 16210345
        )
        <= 5
    )
