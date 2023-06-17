import datetime


class TestTimestampInitialization:
    def test_backfills_timestamps(self, initialize_empty_oracle, delete_timestamps):
        delete_timestamps()
        oracle = initialize_empty_oracle(timestamp_resolution=500_000)

        timestamps = oracle._timestamps

        assert oracle.timestamp_resolution == 500_000

        assert all([(key % 500_000) == 0 for key in timestamps.keys()])
        assert len(timestamps) == (oracle.w3.eth.block_number // 500_000) + 1

        assert timestamps[0] == datetime.datetime(2015, 7, 30, 8, 26, 28)

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

    def test_get_timestamp_at_block(self, initialize_empty_oracle):
        oracle = initialize_empty_oracle()

        assert oracle.block_to_datetime(0) == datetime.datetime(2015, 7, 30, 8, 26, 28)

        assert oracle.block_to_datetime(12_452_223) - datetime.datetime.fromtimestamp(
            1621258925
        ) < datetime.timedelta(minutes=10)
