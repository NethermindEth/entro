import uuid

import pytest

from python_eth_amm.backfill.planner import BackfillRangePlan
from python_eth_amm.database.migrations import migrate_up
from python_eth_amm.database.models.python_eth_amm import BackfilledRange
from python_eth_amm.exceptions import BackfillError
from python_eth_amm.types.backfill import BackfillDataType, SupportedNetwork

DEFAULT_KWARGS = {
    "data_type": BackfillDataType.blocks.value,
    "network": SupportedNetwork.ethereum.value,
    "filter_data": {},
    "metadata_dict": {"max_concurrency": 200},
    "decoded_abis": [],
}


@pytest.fixture(name="setup_backfills", scope="function")
def setup_backfills_fixture(
    integration_postgres_db,
    integration_db_session,
):
    def _setup_fixture() -> tuple[list[BackfilledRange], list[str]]:
        backfills = [
            BackfilledRange(
                backfill_id=uuid.uuid4().hex,
                start_block=8_000_000,
                end_block=9_000_000,
                **DEFAULT_KWARGS,
            ),
            BackfilledRange(
                backfill_id=uuid.uuid4().hex,
                start_block=14_000_000,
                end_block=15_000_000,
                **DEFAULT_KWARGS,
            ),
            BackfilledRange(
                backfill_id=uuid.uuid4().hex,
                start_block=16_000_000,
                end_block=17_000_000,
                **DEFAULT_KWARGS,
            ),
        ]
        migrate_up(integration_db_session.get_bind())

        integration_db_session.add_all(backfills)
        integration_db_session.commit()

        return backfills, [str(b.backfill_id) for b in backfills]

    return _setup_fixture


def test_plan_generation_single_conflict(setup_backfills):
    conflicts, _ = setup_backfills()
    start_inside_end_inside = BackfillRangePlan.compute_db_backfills(
        from_block=14_500_000,
        to_block=14_600_000,
        conflicting_backfills=conflicts,
        backfill_kwargs={},
    )
    start_at_end_at = BackfillRangePlan.compute_db_backfills(
        from_block=14_000_000,
        to_block=15_000_000,
        conflicting_backfills=conflicts,
        backfill_kwargs={},
    )
    start_inside_end_outside = BackfillRangePlan.compute_db_backfills(
        from_block=14_500_000,
        to_block=15_500_000,
        conflicting_backfills=conflicts,
        backfill_kwargs={},
    )
    start_outside_end_inside = BackfillRangePlan.compute_db_backfills(
        from_block=13_500_000,
        to_block=14_500_000,
        conflicting_backfills=conflicts,
        backfill_kwargs={},
    )
    start_outside_end_outside = BackfillRangePlan.compute_db_backfills(
        from_block=13_500_000,
        to_block=15_500_000,
        conflicting_backfills=conflicts,
        backfill_kwargs={},
    )

    assert start_inside_end_inside.backfill_ranges == []
    assert start_inside_end_inside.backfill_mode == "empty"

    assert start_at_end_at.backfill_ranges == []
    assert start_at_end_at.backfill_mode == "empty"

    assert start_inside_end_outside.backfill_ranges == [(15_000_000, 15_500_000)]
    assert start_inside_end_outside.backfill_mode == "extend"

    assert start_outside_end_inside.backfill_ranges == [(13_500_000, 14_000_000)]
    assert start_outside_end_inside.backfill_mode == "extend"

    assert start_outside_end_outside.backfill_ranges == [
        (13_500_000, 14_000_000),
        (15_000_000, 15_500_000),
    ]
    assert start_outside_end_outside.backfill_mode == "extend"


def test_start_before_all_end_after_all(setup_backfills, create_debug_logger):
    conflicts, _ = setup_backfills()
    range_plan = BackfillRangePlan.compute_db_backfills(
        from_block=5_000_000,
        to_block=18_000_000,
        conflicting_backfills=conflicts,
        backfill_kwargs=DEFAULT_KWARGS,
    )

    assert range_plan.backfill_ranges == [
        (5_000_000, 8_000_000),
        (9_000_000, 14_000_000),
        (15_000_000, 16_000_000),
        (17_000_000, 18_000_000),
    ]
    assert range_plan.backfill_mode == "join"
    assert range_plan.conflicts == conflicts

    range_plan.mark_finalized(0)
    assert range_plan.add_backfill.start_block == 5_000_000
    assert range_plan.add_backfill.end_block == 9_000_000

    range_plan.mark_finalized(1)
    assert range_plan.add_backfill.start_block == 5_000_000
    assert range_plan.add_backfill.end_block == 15_000_000
    assert len(range_plan.remove_backfills) == 1
    assert range_plan.remove_backfills[0].start_block == 14_000_000
    assert range_plan.remove_backfills[0].end_block == 15_000_000

    range_plan.mark_finalized(2)
    assert range_plan.add_backfill.start_block == 5_000_000
    assert range_plan.add_backfill.end_block == 17_000_000
    assert len(range_plan.remove_backfills) == 2

    assert range_plan.remove_backfills[1].start_block == 16_000_000
    assert range_plan.remove_backfills[1].end_block == 17_000_000

    range_plan.mark_finalized(3)
    assert range_plan.add_backfill.start_block == 5_000_000
    assert range_plan.add_backfill.end_block == 18_000_000
    assert len(range_plan.remove_backfills) == 2


def test_2_sided_extend(setup_backfills, create_debug_logger):
    conflicts, _ = setup_backfills()
    range_plan = BackfillRangePlan.compute_db_backfills(
        from_block=13_500_000,
        to_block=15_500_000,
        conflicting_backfills=conflicts,
        backfill_kwargs=DEFAULT_KWARGS,
    )

    assert range_plan.backfill_ranges == [
        (13_500_000, 14_000_000),
        (15_000_000, 15_500_000),
    ]
    assert range_plan.backfill_mode == "extend"

    range_plan.mark_finalized(0)
    assert range_plan.add_backfill.backfill_id == conflicts[1].backfill_id
    assert range_plan.add_backfill.start_block == 13_500_000
    assert range_plan.add_backfill.end_block == 15_000_000

    range_plan.mark_finalized(1)
    assert range_plan.add_backfill.backfill_id == conflicts[1].backfill_id
    assert range_plan.add_backfill.start_block == 13_500_000
    assert range_plan.add_backfill.end_block == 15_500_000
    assert len(range_plan.remove_backfills) == 0


def test_1_sided_extend(setup_backfills):
    conflicts, _ = setup_backfills()
    range_plan = BackfillRangePlan.compute_db_backfills(
        from_block=14_000_000,
        to_block=15_500_000,
        conflicting_backfills=conflicts,
        backfill_kwargs=DEFAULT_KWARGS,
    )

    assert range_plan.backfill_ranges == [(15_000_000, 15_500_000)]
    assert range_plan.backfill_mode == "extend"

    range_plan.mark_finalized(0)
    assert range_plan.add_backfill.backfill_id == conflicts[1].backfill_id

    assert range_plan.add_backfill.start_block == 14_000_000
    assert range_plan.add_backfill.end_block == 15_500_000
    assert len(range_plan.remove_backfills) == 0

    with pytest.raises(BackfillError) as error:
        range_plan.mark_finalized(1)
        assert str(error) == "Cannot finalize backfill that is not in the plan"


def test_extend_fail_before(setup_backfills):
    conflicts, conflict_ids = setup_backfills()
    range_plan = BackfillRangePlan.compute_db_backfills(
        from_block=13_500_000,
        to_block=15_500_000,
        conflicting_backfills=conflicts,
        backfill_kwargs=DEFAULT_KWARGS,
    )

    range_plan.mark_failed(range_index=0, final_block=13_750_000)
    assert range_plan.add_backfill.backfill_id not in conflict_ids
    assert range_plan.add_backfill.start_block == 13_500_000
    assert range_plan.add_backfill.end_block == 13_750_000
    assert len(range_plan.remove_backfills) == 0


def test_extend_fail_after(setup_backfills):
    conflicts, _ = setup_backfills()
    range_plan = BackfillRangePlan.compute_db_backfills(
        from_block=13_500_000,
        to_block=15_500_000,
        conflicting_backfills=conflicts,
        backfill_kwargs=DEFAULT_KWARGS,
    )

    range_plan.mark_finalized(0)

    range_plan.mark_failed(range_index=1, final_block=15_250_000)

    assert range_plan.add_backfill.backfill_id == conflicts[1].backfill_id
    assert range_plan.add_backfill.start_block == 13_500_000
    assert range_plan.add_backfill.end_block == 15_250_000
    assert len(range_plan.remove_backfills) == 0


def test_extend_fail_after_single(setup_backfills):
    conflicts, _ = setup_backfills()
    extend_plan = BackfillRangePlan.compute_db_backfills(
        from_block=15_000_000,
        to_block=15_500_000,
        conflicting_backfills=conflicts,
        backfill_kwargs=DEFAULT_KWARGS,
    )

    extend_plan.mark_failed(range_index=0, final_block=15_250_000)
    assert extend_plan.add_backfill.backfill_id == conflicts[1].backfill_id
    assert extend_plan.add_backfill.start_block == 14_000_000
    assert extend_plan.add_backfill.end_block == 15_250_000
    assert len(extend_plan.remove_backfills) == 0


def test_join_fail_before(setup_backfills):
    conflicts, conflict_ids = setup_backfills()
    fail_before_plan = BackfillRangePlan.compute_db_backfills(
        from_block=5_000_000,
        to_block=18_000_000,
        conflicting_backfills=conflicts,
        backfill_kwargs=DEFAULT_KWARGS,
    )
    fail_before_plan.mark_failed(range_index=0, final_block=5_500_000)
    assert fail_before_plan.add_backfill.backfill_id not in conflict_ids
    assert fail_before_plan.add_backfill.start_block == 5_000_000
    assert fail_before_plan.add_backfill.end_block == 5_500_000
    assert len(fail_before_plan.remove_backfills) == 0


def test_join_fail_mid_plan(setup_backfills):
    conflicts, _ = setup_backfills()
    fail_mid_plan = BackfillRangePlan.compute_db_backfills(
        from_block=9_500_000,
        to_block=18_000_000,
        conflicting_backfills=conflicts,
        backfill_kwargs=DEFAULT_KWARGS,
    )

    fail_mid_plan.mark_finalized(0)
    fail_mid_plan.mark_failed(range_index=1, final_block=15_500_000)

    assert fail_mid_plan.add_backfill.backfill_id == conflicts[1].backfill_id
    assert fail_mid_plan.add_backfill.start_block == 9_500_000
    assert fail_mid_plan.add_backfill.end_block == 15_500_000
    assert len(fail_mid_plan.remove_backfills) == 0


def test_join_fail_late_plan(setup_backfills):
    conflicts, _ = setup_backfills()
    fail_late_plan = BackfillRangePlan.compute_db_backfills(
        from_block=10_000_000,
        to_block=19_000_000,
        conflicting_backfills=conflicts,
        backfill_kwargs=DEFAULT_KWARGS,
    )

    fail_late_plan.mark_finalized(0)
    fail_late_plan.mark_finalized(1)
    fail_late_plan.mark_failed(range_index=2, final_block=18_500_000)
    assert fail_late_plan.add_backfill.backfill_id == conflicts[1].backfill_id
    assert fail_late_plan.add_backfill.start_block == 10_000_000
    assert fail_late_plan.add_backfill.end_block == 18_500_000

    assert len(fail_late_plan.remove_backfills) == 1
    assert fail_late_plan.remove_backfills[0].start_block == 16_000_000
    assert fail_late_plan.remove_backfills[0].end_block == 17_000_000


def test_start_after_first_end_after_all(setup_backfills):
    conflicts, _ = setup_backfills()
    result = BackfillRangePlan.compute_db_backfills(
        from_block=10_500_000,
        to_block=18_000_000,
        conflicting_backfills=conflicts,
        backfill_kwargs=DEFAULT_KWARGS,
    )

    assert result.backfill_ranges == [
        (10_500_000, 14_000_000),
        (15_000_000, 16_000_000),
        (17_000_000, 18_000_000),
    ]
    assert result.backfill_mode == "join"

    result.mark_finalized(0)
    result.mark_finalized(1)
    result.mark_failed(2, 17_500_000)

    assert result.add_backfill.backfill_id == conflicts[1].backfill_id
    assert result.add_backfill.start_block == 10_500_000
    assert result.add_backfill.end_block == 17_500_000

    assert len(result.remove_backfills) == 1
    assert result.remove_backfills[0].backfill_id == conflicts[2].backfill_id
    assert result.remove_backfills[0].start_block == 16_000_000
    assert result.remove_backfills[0].end_block == 17_000_000


def test_start_at_end_of_1_end_at_start_of_2(setup_backfills):
    conflicts, _ = setup_backfills()
    result = BackfillRangePlan.compute_db_backfills(
        from_block=9_000_000,
        to_block=14_000_000,
        conflicting_backfills=conflicts,
        backfill_kwargs=DEFAULT_KWARGS,
    )

    assert result.backfill_ranges == [(9_000_000, 14_000_000)]
    assert result.backfill_mode == "join"

    result.mark_finalized(0)

    assert result.add_backfill.backfill_id == conflicts[0].backfill_id
    assert result.add_backfill.start_block == 8_000_000
    assert result.add_backfill.end_block == 15_000_000

    assert len(result.remove_backfills) == 1
    assert result.remove_backfills[0].backfill_id == conflicts[1].backfill_id


def test_start_before_all_end_before_last(setup_backfills):
    conflicts, _ = setup_backfills()
    result = BackfillRangePlan.compute_db_backfills(
        from_block=5_000_000,
        to_block=15_500_000,
        conflicting_backfills=conflicts,
        backfill_kwargs=DEFAULT_KWARGS,
    )

    assert result.backfill_ranges == [
        (5_000_000, 8_000_000),
        (9_000_000, 14_000_000),
        (15_000_000, 15_500_000),
    ]

    result.mark_finalized(0)
    result.mark_finalized(1)
    result.mark_finalized(2)

    assert result.add_backfill.backfill_id == conflicts[0].backfill_id
    assert result.add_backfill.start_block == 5_000_000
    assert result.add_backfill.end_block == 15_500_000

    assert len(result.remove_backfills) == 1
    assert result.remove_backfills[0].backfill_id == conflicts[1].backfill_id
    assert result.remove_backfills[0].start_block == 14_000_000
    assert result.remove_backfills[0].end_block == 15_000_000


def test_extend_second_both_sides(setup_backfills):
    conflicts, _ = setup_backfills()
    result = BackfillRangePlan.compute_db_backfills(
        from_block=13_000_000,
        to_block=15_500_000,
        conflicting_backfills=conflicts,
        backfill_kwargs=DEFAULT_KWARGS,
    )

    assert result.backfill_ranges == [
        (13_000_000, 14_000_000),
        (15_000_000, 15_500_000),
    ]

    result.mark_finalized(0)
    result.mark_failed(1, 15_250_000)

    assert result.add_backfill.backfill_id == conflicts[1].backfill_id
    assert result.add_backfill.start_block == 13_000_000
    assert result.add_backfill.end_block == 15_250_000

    assert len(result.remove_backfills) == 0


def test_start_between_first_and_second(setup_backfills):
    conflicts, _ = setup_backfills()
    result = BackfillRangePlan.compute_db_backfills(
        from_block=8_500_000,
        to_block=14_500_000,
        conflicting_backfills=conflicts,
        backfill_kwargs=DEFAULT_KWARGS,
    )

    assert result.backfill_ranges == [(9_000_000, 14_000_000)]
    assert result.backfill_mode == "join"

    result.mark_finalized(0)

    assert len(result.remove_backfills) == 1
    assert result.remove_backfills[0].backfill_id == conflicts[1].backfill_id

    assert result.add_backfill.backfill_id == conflicts[0].backfill_id
    assert result.add_backfill.start_block == 8_000_000
    assert result.add_backfill.end_block == 15_000_000


def test_start_in_gap_end_in_gap(setup_backfills):
    conflicts, conflict_ids = setup_backfills()
    result = BackfillRangePlan.compute_db_backfills(
        from_block=10_500_000,
        to_block=11_500_000,
        conflicting_backfills=conflicts,
        backfill_kwargs=DEFAULT_KWARGS,
    )
    assert result.backfill_ranges == [(10_500_000, 11_500_000)]

    result.mark_failed(0, 11_000_000)
    assert len(result.remove_backfills) == 0

    assert result.add_backfill.backfill_id not in conflict_ids
    assert result.add_backfill.start_block == 10_500_000
    assert result.add_backfill.end_block == 11_000_000
