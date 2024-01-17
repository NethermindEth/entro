import pytest

from python_eth_amm.backfill.planner import (
    _compute_backfill_ranges,
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

class TestBackfillRangeProcessing:
    single_backfill = [BackfilledRange(
        data_type=BackfillDataType.events,
        start_block=14_000_000,
        end_block=15_000_000,
    )]

    backfill_1 = BackfilledRange(
        data_type=BackfillDataType.blocks,
        start_block=8_000_000,
        end_block=9_000_000,
    )
    
    backfill_2 = BackfilledRange(
        data_type=BackfillDataType.blocks,
        start_block=14_000_000,
        end_block=15_000_000
    )
    backfill_3 = BackfilledRange(
        data_type=BackfillDataType.blocks,
        start_block=16_000_000,
        end_block=17_000_000,
    )


    conflict_backfills = [backfill_1, backfill_2, backfill_3]
    print(conflict_backfills)
    def test_plan_generation_single_conflict(self):

        start_inside_end_inside = _compute_backfill_ranges(from_block=14_500_000, to_block=14_600_000, conflicting_backfills=self.single_backfill.copy()) 
        start_at_end_at = _compute_backfill_ranges(from_block=14_000_000, to_block=15_000_000, conflicting_backfills=self.single_backfill.copy())
        start_inside_end_outside = _compute_backfill_ranges(from_block=14_500_000, to_block=15_500_000, conflicting_backfills=self.single_backfill.copy())
        start_outside_end_inside = _compute_backfill_ranges(from_block=13_500_000, to_block=14_500_000, conflicting_backfills=self.single_backfill.copy())
        start_outside_end_outside = _compute_backfill_ranges(from_block=13_500_000, to_block=15_500_000, conflicting_backfills=self.single_backfill.copy())

        assert start_inside_end_inside.required_backfill_ranges == []
        assert start_inside_end_inside.remove_backfills == []
        assert start_inside_end_inside.add_backfill_range is None

        assert start_at_end_at.required_backfill_ranges == []
        assert start_at_end_at.remove_backfills == []
        assert start_at_end_at.add_backfill_range is None


        assert start_inside_end_outside.required_backfill_ranges == [(15_000_000, 15_500_000)]
        assert start_outside_end_inside.required_backfill_ranges == [(13_500_000, 14_000_000)]
        assert start_outside_end_outside.required_backfill_ranges == [(13_500_000, 14_000_000), (15_000_000, 15_500_000)]


    def test_start_before_all_end_before_all(self):
        result = _compute_backfill_ranges(from_block=5_000_000, to_block=18_000_000, conflicting_backfills=self.conflict_backfills.copy())

        assert result.required_backfill_ranges == [(5_000_000, 8_000_000), (9_000_000, 14_000_000),(15_000_000, 16_000_000), (17_000_000, 18_000_000)]
        assert result.remove_backfills == self.conflict_backfills
        assert result.add_backfill_range == (5_000_000, 18_000_000)

    def test_start_after_first_end_after_all(self):
        result = _compute_backfill_ranges(from_block=10_500_000, to_block=18_000_000, conflicting_backfills=self.conflict_backfills.copy())

        assert result.required_backfill_ranges == [(10_500_000, 14_000_000), (15_000_000, 16_000_000), (17_000_000, 18_000_000)]
        assert result.remove_backfills == [self.backfill_2, self.backfill_3]
        assert result.add_backfill_range == (10_500_000, 18_000_000)

    def test_start_at_end_of_1_end_at_start_of_2(self):
        result = _compute_backfill_ranges(from_block=9_000_000, to_block=14_000_000, conflicting_backfills=self.conflict_backfills.copy())

        assert result.required_backfill_ranges == [(9_000_000, 14_000_000)]
        assert result.remove_backfills == [self.backfill_1, self.backfill_2]
        assert result.add_backfill_range == (8_000_000, 15_000_000)

    def test_start_at_end_of_2_end_at_start_of_3(self):
        result = _compute_backfill_ranges(from_block=15_000_000, to_block=16_000_000, conflicting_backfills=self.conflict_backfills.copy())

        assert result.required_backfill_ranges == [(15_000_000, 16_000_000)]
        assert result.remove_backfills == [self.backfill_2, self.backfill_3]
        assert result.add_backfill_range == (14_000_000, 17_000_000)

    def test_start_before_all_end_before_last(self):
        result  = _compute_backfill_ranges(from_block=5_000_000, to_block=15_500_000, conflicting_backfills=self.conflict_backfills.copy())

        assert result.required_backfill_ranges == [(5_000_000, 8_000_000), (9_000_000, 14_000_000), (15_000_000, 15_500_000)]
        assert result.remove_backfills == [self.backfill_1, self.backfill_2]
        assert result.add_backfill_range == (5_000_000, 15_500_000)

    def test_extend_second_both_sides(self):
        result = _compute_backfill_ranges(from_block=13_000_000, to_block=15_500_000, conflicting_backfills=self.conflict_backfills.copy())

        assert result.required_backfill_ranges == [(13_000_000, 14_000_000), (15_000_000, 15_500_000)]
        assert result.remove_backfills == [self.backfill_2]
        assert result.add_backfill_range == (13_000_000, 15_500_000)


    def test_extend_first_left_side(self):
        result = _compute_backfill_ranges(from_block=5_000_000, to_block=8_500_000, conflicting_backfills=self.conflict_backfills.copy())
        assert result.required_backfill_ranges == [(5_000_000, 8_000_000)]
        assert result.remove_backfills == [self.backfill_1]
        assert result.add_backfill_range == (5_000_000, 9_000_000)

    def test_extend_first_right_side(self):
        result = _compute_backfill_ranges(from_block=8_500_000, to_block=11_000_000, conflicting_backfills=self.conflict_backfills.copy())

        assert result.required_backfill_ranges == [(9_000_000, 11_000_000)]
        assert result.remove_backfills == [self.backfill_1]
        assert result.add_backfill_range == (8_000_000, 11_000_000)


    def test_start_between_first_and_second(self):
        result = _compute_backfill_ranges(from_block=8_500_000, to_block=14_500_000, conflicting_backfills=self.conflict_backfills.copy())
        assert result.required_backfill_ranges == [(9_000_000, 14_000_000)]
        assert result.remove_backfills == [self.backfill_1, self.backfill_2]
        assert result.add_backfill_range == (8_000_000, 15_000_000)


    def test_start_inside_second_end_at_third(self):
        result = _compute_backfill_ranges(from_block=14_500_000, to_block=16_000_000, conflicting_backfills=self.conflict_backfills.copy())
        assert result.required_backfill_ranges == [(15_000_000, 16_000_000)]
        assert result.remove_backfills == [self.backfill_2, self.backfill_3]
        assert result.add_backfill_range == (14_000_000, 17_000_000)


    def test_start_in_gap_end_in_gap(self):
        result = _compute_backfill_ranges(from_block=10_500_000, to_block=11_500_000, conflicting_backfills=self.conflict_backfills.copy())
        assert result.required_backfill_ranges == [(10_500_000, 11_500_000)]
        assert result.remove_backfills == []
        assert result.add_backfill_range == (10_500_000, 11_500_000)


    def test_start_inside_2_end_after_all(self):
        result = _compute_backfill_ranges(from_block=14_500_000, to_block=18_000_000, conflicting_backfills=self.conflict_backfills.copy())
        assert result.required_backfill_ranges == [(15_000_000, 16_000_000), (17_000_000, 18_000_000)]
        assert result.remove_backfills == [self.backfill_2, self.backfill_3]
        assert result.add_backfill_range == (14_000_000, 18_000_000)

    def test_start_before_all_end_inside_2(self):
        result = _compute_backfill_ranges(from_block=5_000_000, to_block=14_500_000, conflicting_backfills=self.conflict_backfills.copy())

        assert result.required_backfill_ranges == [(5_000_000, 8_000_000), (9_000_000, 14_000_000)]
        assert result.remove_backfills == [self.backfill_1, self.backfill_2]
        assert result.add_backfill_range == (5_000_000, 15_000_000)


    def test_start_at_first_end_after_all(self):
        result = _compute_backfill_ranges(from_block=9_000_000, to_block=18_000_000, conflicting_backfills=self.conflict_backfills.copy())

        assert result.required_backfill_ranges == [(9_000_000, 14_000_000), (15_000_000, 16_000_000), (17_000_000, 18_000_000)]
        assert result.remove_backfills == [self.backfill_1, self.backfill_2, self.backfill_3]
        assert result.add_backfill_range == (8_000_000, 18_000_000)

    def test_start_at_end_of_1_begin_at_start_of_2_only_2_conflicts(self):
        result = _compute_backfill_ranges(from_block=9_000_000, to_block=14_000_000, conflicting_backfills=[self.backfill_1, self.backfill_2])

        assert result.required_backfill_ranges == [(9_000_000, 14_000_000)]
        assert result.remove_backfills == [self.backfill_1, self.backfill_2]
        assert result.add_backfill_range == (8_000_000, 15_000_000)
