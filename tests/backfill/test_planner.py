import uuid

import pytest

from python_eth_amm.backfill.planner import (
    BackfillRangePlan,
    _filter_conflicting_backfills,
    _verify_filters,
)
from python_eth_amm.database.models import BackfilledRange
from python_eth_amm.exceptions import BackfillError
from python_eth_amm.types.backfill import BackfillDataType

# fmt: off

class TestFiltering:
    a1 = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
    a2 = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
    a3 = "0x1F98431c8aD98523631AE4a59f267346ea31F984"

    tx1 = BackfilledRange(data_type=BackfillDataType.transactions, start_block=10_000_000, end_block=12_000_000, filter_data={"for_address": a1})
    tx2 = BackfilledRange(data_type=BackfillDataType.transactions, start_block=13_000_000, end_block=14_000_000, filter_data={"for_address": a2})
    tx3 = BackfilledRange(data_type=BackfillDataType.transactions, start_block=8_000_000, end_block=9_000_000, filter_data=None)

    transfer1 = BackfilledRange(data_type=BackfillDataType.transfers, start_block=10_000_000, end_block=12_000_000, filter_data={"token_address": a1, "from_address": a2})
    transfer2 = BackfilledRange(data_type=BackfillDataType.transfers, start_block=10_000_000, end_block=14_000_000, filter_data={"token_address": a1, "from_address": a3})
    transfer3 = BackfilledRange(data_type=BackfillDataType.transfers, start_block=12_000_000, end_block=14_000_000, filter_data={"token_address": a1, "to_address": a3})
    transfer4 = BackfilledRange(data_type=BackfillDataType.transfers, start_block=6_000_000, end_block=8_000_000, filter_data={"token_address": a2, "from_address": a3})

    transfers = [transfer1, transfer2, transfer3, transfer4]
    def test_filter_errors(self):
        with pytest.raises(BackfillError) as error:
            _verify_filters(BackfillDataType.transactions, {"from_address": "0x123456"})
            assert str(error) == "Address is wrong length.  Double check address: 0x123456"

        with pytest.raises(BackfillError) as error:
            _verify_filters(BackfillDataType.blocks, {"from_address": self.a1})
            assert str(error) == "blocks backfill does not support filters."

        with pytest.raises(BackfillError) as error:
            _verify_filters(BackfillDataType.events, {"from_address": self.a1})
            assert str(error) == "events cannot be filtered by from_address.  Valid filters for events are ['contract_address']"

        with pytest.raises(BackfillError) as error:
            _verify_filters(BackfillDataType.events, {})
            assert str(error) == "'contract_address' must be set to backfill events"

        with pytest.raises(BackfillError) as error:
            _verify_filters(BackfillDataType.transactions, {"contract_address": self.a2})
            assert str(error) == "transactions cannot be filtered by contract_address.  Valid filters for transactions are ['from_address']"


        with pytest.raises(BackfillError) as error:
            _verify_filters(BackfillDataType.traces, {"to_address": self.a3})
            assert str(error) == "traces cannot be filtered by to_address.  Valid filters for traces are ['from_address']"


    def test_transfer_filter_errors(self):
        with pytest.raises(BackfillError) as error:
            _verify_filters(BackfillDataType.transfers, {"token_address": self.a3, "contract_address": self.a2})
            assert str(error) == "transfers cannot be filtered by contract_address.  Valid filters for transfers are ['token_address', 'from_address', 'to_address']"

        with pytest.raises(BackfillError) as error:
            _verify_filters(BackfillDataType.transfers, {"from_address": self.a3})
            assert str(error) == "'token_address' must be set to backfill transfers"

        with pytest.raises(BackfillError) as error:
            _verify_filters(BackfillDataType.transfers, {"token_address": self.a1, "from_address": self.a2, "to_address": self.a2})
            assert str(error) == "transfers cannot be filtered by both from_address and to_address"

    def test_valid_filters(self):
        valid_filters = [
            _verify_filters(BackfillDataType.events, {"contract_address": self.a2, "contract_abi": "ERC20", "event_names": ["Transfer"]}), # Valid Event Filter
            _verify_filters(BackfillDataType.transactions, {"for_address": self.a1}),
            # _verify_filters(BackfillDataType.transactions, {"from_address": self.a3})  # From address has been replaced by For Address
            _verify_filters(BackfillDataType.traces, {"from_address": self.a1}), # Valid Trace Filter
            _verify_filters(BackfillDataType.transfers, {"token_address": self.a1, "from_address": self.a2}), # Valid FROM Transfer Filter
            _verify_filters(BackfillDataType.transfers, {"token_address": self.a1, "to_address": self.a3}), # Valid TO Transfer Filter
        ]

        assert all([filter is None for filter in valid_filters])


    def test_conflicting_transaction_backfill_is_returned(self):
        conflict = _filter_conflicting_backfills(
            data_type=BackfillDataType.transactions,
            backfills=[self.tx1],
            filter_params={"for_address": self.a1}
        )
        assert conflict == [self.tx1]

    def test_filtered_and_unfiltered_transaction_backfills_conflicts(self):
        conflict = _filter_conflicting_backfills(
            data_type=BackfillDataType.transactions,
            backfills=[self.tx1, self.tx2, self.tx3]
        )
        assert conflict == [self.tx3]

    def test_unfiltered_backfill_no_conflict(self):
        conflict = _filter_conflicting_backfills(
            data_type=BackfillDataType.transactions,
            backfills=[self.tx1, self.tx2]
        )
        assert conflict == []

    def test_non_conflicting_transaction_backfills_are_ignored(self):
        conflict = _filter_conflicting_backfills(
            data_type=BackfillDataType.transactions,
            backfills=[self.tx1, self.tx2],
            filter_params={"for_address": self.a3}
        )
        assert conflict == []

    def test_return_two_conflicting_transaction_backfills(self):
        conflicting_transaction = BackfilledRange(
            data_type=BackfillDataType.transactions,
            start_block=8_000_000,
            end_block=9_000_000,
            filter_data={"for_address": self.a1}
        )
        conflict = _filter_conflicting_backfills(
            data_type=BackfillDataType.transactions,
            backfills=[conflicting_transaction, self.tx1],
            filter_params={"for_address": self.a1}
        )

        assert conflict == [conflicting_transaction, self.tx1]

    def test_conflicts_on_no_filter_fields(self):
        block_1 = BackfilledRange(
            data_type=BackfillDataType.blocks,
            start_block=8_000_000,
            end_block=9_000_000,
        )
        block_2 = BackfilledRange(
            data_type=BackfillDataType.blocks,
            start_block=9_000_000,
            end_block=10_000_000,
        )
        conflict = _filter_conflicting_backfills(
            data_type=BackfillDataType.blocks,
            backfills=[block_1, block_2],
        )
        assert conflict == [block_1, block_2]

    def test_transfer_conficts(self):
        from_address_conflict = _filter_conflicting_backfills(
            data_type=BackfillDataType.transfers,
            backfills=self.transfers,
            filter_params={"token_address": self.a1, "from_address": self.a2}
        )
        to_address_conflict = _filter_conflicting_backfills(
            data_type=BackfillDataType.transfers,
            backfills=self.transfers,
            filter_params={"token_address": self.a1, "to_address": self.a3}
        )
        to_address_no_conflict = _filter_conflicting_backfills(
            data_type=BackfillDataType.transfers,
            backfills=self.transfers,
            filter_params={"token_address": self.a1, "to_address": self.a2}
        )
        token_address_no_conflict = _filter_conflicting_backfills(
            data_type=BackfillDataType.transfers,
            backfills=self.transfers,
            filter_params={"token_address": self.a3, "from_address": self.a2}
        )

        assert from_address_conflict == [self.transfer1]
        assert to_address_conflict == [self.transfer3]
        assert to_address_no_conflict == []
        assert token_address_no_conflict == []


    @pytest.mark.skip("TODO")
    def test_trace_conflicts(self):
        pass
