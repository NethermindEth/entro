import datetime
import tempfile

import click.utils

from entro.backfill.timestamps import TimestampConverter
from nethermind.entro.backfill.utils import get_current_block_number
from nethermind.entro.database.migrations import migrate_up
from nethermind.entro.types.backfill import SupportedNetwork


def test_backfills_ethereum_timestamps(
    integration_postgres_db,
    integration_db_session,
    integration_db_url,
    eth_rpc_url,
):
    migrate_up(integration_db_session.get_bind())

    timestamp_converter = TimestampConverter(
        network=SupportedNetwork.ethereum,
        db_url=integration_db_url,
        json_rpc=eth_rpc_url,
        resolution=100_000,
    )
    assert timestamp_converter.timestamp_resolution == 100_000

    current_block = get_current_block_number(SupportedNetwork.ethereum)

    assert len(timestamp_converter.timestamp_data) == (current_block // 100_000) + 1


def test_ethereum_timestamp_conversions(
    eth_rpc_url, integration_db_session, integration_db_url, integration_postgres_db
):
    migrate_up(integration_db_session.get_bind())

    timestamp_converter = TimestampConverter(
        network=SupportedNetwork.ethereum,
        db_url=integration_db_url,
        json_rpc=eth_rpc_url,
        resolution=10_000,
    )

    # Assert timestamps are converted to UTC datetime

    assert timestamp_converter.block_to_datetime(0) == datetime.datetime(2015, 7, 30, 15, 26, 28, tzinfo=timezone.utc)

    assert timestamp_converter.block_to_datetime(18_000_000) == datetime.datetime(
        2023, 8, 26, 16, 21, 35, tzinfo=timezone.utc
    )

    assert timestamp_converter.block_to_datetime(12_452_223) - datetime.datetime.fromtimestamp(
        1621258925, tz=datetime.timezone.utc
    ) < datetime.timedelta(minutes=10)

    # Checking Date -> Block conversions
    assert abs(timestamp_converter.datetime_to_block(datetime.date(2023, 4, 8)) - 17000009) <= 5

    # Checking DateTime -> Block conversions
    assert (
        abs(
            timestamp_converter.datetime_to_block(
                datetime.datetime(2022, 12, 18, 8, 21, 35, tzinfo=datetime.timezone.utc)
            )
            - 16210345
        )
        <= 5
    )


def test_backfills_starknet_timestamps_disk_caching(starknet_rpc_url, mocker):
    with tempfile.TemporaryDirectory() as temp_dir:
        mocker.patch("click.utils.get_app_dir", return_value=temp_dir)

        timestamp_converter = TimestampConverter(
            network=SupportedNetwork.starknet, db_url=None, json_rpc=starknet_rpc_url, resolution=10_000
        )

        # This is called once during reading, and once during writing
        click.utils.get_app_dir.call_count == 2

        assert timestamp_converter.timestamp_resolution == 10_000

        current_block = get_current_block_number(SupportedNetwork.starknet)

        assert len(timestamp_converter.timestamp_data) == (current_block // 10_000) + 1


def test_starknet_timestamp_conversions(mocker, starknet_rpc_url):
    with tempfile.TemporaryDirectory() as temp_dir:
        mocker.patch("click.utils.get_app_dir", return_value=temp_dir)

        timestamp_converter = TimestampConverter(
            network=SupportedNetwork.starknet,
            db_url=None,
            json_rpc=starknet_rpc_url,
        )

        # This is called once during reading, and once during writing
        click.utils.get_app_dir.call_count == 2

        # Assert default resolution
        assert timestamp_converter.timestamp_resolution == 100

        assert timestamp_converter.block_to_datetime(0) == datetime.datetime(
            2021, 11, 16, 13, 24, 8, tzinfo=datetime.timezone.utc
        )

        # Saturday, May 11, 2024 4:41:26 PM
        assert timestamp_converter.block_to_datetime(640_000) == datetime.datetime(
            2024, 5, 11, 16, 41, 26, tzinfo=datetime.timezone.utc
        )

        # Sunday, October 22, 2023 2:50:05 PM -- Starknet Block 345223 -- Unix 1697986205
        assert timestamp_converter.block_to_datetime(345_223) - datetime.datetime.fromtimestamp(
            1697986205, tz=datetime.timezone.utc
        ) < datetime.timedelta(minutes=10)

        # Checking Date -> Block conversions within +- 5 blocks
        # Sunday, February 25, 2024 12:00:05 AM  -- Starknet Block 581757  -- Unix 1708819205
        assert abs(timestamp_converter.datetime_to_block(datetime.date(2024, 2, 25)) - 581757) <= 5

        # Checking DateTime -> Block conversions
        # Sunday, June 23, 2024 11:18:30 PM -- Starknet Block 651900 -- Unix 1719184710
        assert (
            abs(
                timestamp_converter.datetime_to_block(
                    datetime.datetime(2024, 6, 23, 23, 18, 30, tzinfo=datetime.timezone.utc)
                )
                - 651900
            )
            <= 5
        )
