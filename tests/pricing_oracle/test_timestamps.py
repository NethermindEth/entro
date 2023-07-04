import datetime


class TestTimestampInitialization:
    def test_backfills_timestamps(self, initialize_empty_oracle, delete_timestamps):
        delete_timestamps()
        oracle = initialize_empty_oracle(timestamp_resolution=500_000)

        timestamps = oracle._timestamps

        assert oracle.timestamp_resolution == 500_000

        assert all([(key % 500_000) == 0 for key in timestamps.keys()])
        assert len(timestamps) == (oracle.w3.eth.block_number // 500_000) + 1

        assert timestamps[0] == datetime.datetime(
            2015, 7, 30, 15, 26, 28, tzinfo=datetime.timezone.utc
        )

        delete_timestamps()

    def test_backfills_timestamps_default_resolution(
        self, initialize_empty_oracle, delete_timestamps
    ):
        delete_timestamps()
        oracle = initialize_empty_oracle()

        timestamps = oracle._timestamps

        assert oracle.timestamp_resolution == 10_000

        assert all([(key % 10_000) == 0 for key in timestamps.keys()])
        assert len(timestamps) == (oracle.w3.eth.block_number // 10_000) + 1

    def test_get_timestamp_at_block(self, initialize_empty_oracle, delete_timestamps):
        delete_timestamps()
        oracle = initialize_empty_oracle()

        assert oracle.block_to_datetime(0) == datetime.datetime(
            2015, 7, 30, 15, 26, 28, tzinfo=datetime.timezone.utc
        )

        assert oracle.block_to_datetime(12_452_223) - datetime.datetime.fromtimestamp(
            1621258925, tz=datetime.timezone.utc
        ) < datetime.timedelta(minutes=10)

    def test_get_block_at_date(self, initialize_empty_oracle, delete_timestamps):
        delete_timestamps()
        oracle = initialize_empty_oracle()

        # Asset Date objects are converted to datetime objects at 00:00:00 UTC

        result = oracle.datetime_to_block(datetime.date(2023, 4, 8))
        assert abs(result - 17000009) <= 5  # Within 5 blocks of the correct answer

        # Check that datetime objects are correctly handled

        result = oracle.datetime_to_block(
            datetime.datetime(2022, 12, 18, 8, 21, 35, tzinfo=datetime.timezone.utc)
        )

        assert abs(result - 16210345) <= 200  # Within 200 blocks of the correct answer
