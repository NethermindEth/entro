import uuid

import pytest
from click.testing import CliRunner

from nethermind.entro.backfill.planner import BackfillPlan
from nethermind.entro.cli import entro_cli
from nethermind.entro.database.migrations import migrate_up
from nethermind.entro.database.models import BackfilledRange
from nethermind.entro.types.backfill import BackfillDataType, SupportedNetwork

DEFAULT_KWARGS = {
    "data_type": BackfillDataType.blocks.value,
    "network": SupportedNetwork.ethereum.value,
    "filter_data": {},
    "metadata_dict": {"max_concurrency": 200},
    "decoded_abis": [],
}


@pytest.fixture(scope="function")
def setup_backfills(integration_postgres_db, integration_db_session, cli_db_url):
    backfills = [
        BackfilledRange(
            backfill_id=uuid.uuid4().hex,
            start_block=18_000_000,
            end_block=18_000_020,
            **DEFAULT_KWARGS,
        ),
        BackfilledRange(
            backfill_id=uuid.uuid4().hex,
            start_block=18_000_060,
            end_block=18_000_080,
            **DEFAULT_KWARGS,
        ),
    ]
    migrate_up(integration_db_session.get_bind())

    integration_db_session.add_all(backfills)
    integration_db_session.commit()


def test_backfilling_start_at_end_at(
    integration_postgres_db,
    cli_db_url,
    eth_rpc_cli_config,
    integration_db_session,
    setup_backfills,
    create_debug_logger,
):
    backfill_plan = BackfillPlan.generate(
        db_session=integration_db_session,
        backfill_type=BackfillDataType.blocks,
        network=SupportedNetwork.ethereum,
        start_block=18_000_020,
        end_block=18_000_060,
    )

    assert backfill_plan.range_plan.backfill_ranges == [(18_000_020, 18_000_060)]
    assert backfill_plan.total_blocks() == 40

    backfill_plan.range_plan.mark_finalized(0)

    backfill_plan.save_to_db()

    bfills = integration_db_session.query(BackfilledRange).all()
    assert len(bfills) == 1

    assert bfills[0].start_block == 18_000_000
    assert bfills[0].end_block == 18_000_080


def test_start_inside_end_inside(
    integration_postgres_db,
    integration_db_session,
    cli_db_url,
    eth_rpc_cli_config,
    setup_backfills,
):
    runner = CliRunner()

    backfill_result = runner.invoke(
        entro_cli,
        [
            "backfill",
            "blocks",
            "-from",
            18_000_010,
            "-to",
            18_000_070,
            *eth_rpc_cli_config,
            *cli_db_url,
        ],
        input="y",
    )

    assert backfill_result.exit_code == 0
    assert "18,000,020" in backfill_result.output
    assert "18,000,060" in backfill_result.output

    backfills = integration_db_session.query(BackfilledRange).all()

    assert len(backfills) == 1
    assert backfills[0].start_block == 18_000_000
    assert backfills[0].end_block == 18_000_080


def test_extending_range_failed_backfill(integration_postgres_db, integration_db_session):
    migrate_up(integration_db_session.get_bind())

    extend_id = uuid.uuid4().hex
    integration_db_session.add(
        BackfilledRange(
            backfill_id=extend_id,
            start_block=12_000_000,
            end_block=14_000_000,
            **DEFAULT_KWARGS,
        ),
    )
    integration_db_session.commit()

    extension_backfill = BackfillPlan.generate(
        db_session=integration_db_session,
        backfill_type=BackfillDataType.blocks,
        network=SupportedNetwork.ethereum,
        start_block=14_000_000,
        end_block=18_000_000,
    )

    extension_backfill.process_failed_backfill(16_000_000)

    assert len(extension_backfill.range_plan.remove_backfills) == 0

    extension_backfill.save_to_db()

    bfills = integration_db_session.query(BackfilledRange).all()
    assert len(bfills) == 1
    assert bfills[0].backfill_id == extend_id
    assert bfills[0].start_block == 12_000_000
    assert bfills[0].end_block == 16_000_000


def test_multi_range_failed_backfills(integration_postgres_db, integration_db_session):
    migrate_up(integration_db_session.get_bind())
    conflict_id = uuid.uuid4().hex
    integration_db_session.add(
        BackfilledRange(
            backfill_id=conflict_id,
            start_block=12_000_000,
            end_block=14_000_000,
            **DEFAULT_KWARGS,
        ),
    )
    integration_db_session.commit()

    single_range_fail_plan = BackfillPlan.generate(
        db_session=integration_db_session,
        backfill_type=BackfillDataType.blocks,
        network=SupportedNetwork.ethereum,
        start_block=10_000_000,
        end_block=18_000_000,
    )

    dual_range_fail_plan = BackfillPlan.generate(
        db_session=integration_db_session,
        backfill_type=BackfillDataType.blocks,
        network=SupportedNetwork.ethereum,
        start_block=10_000_000,
        end_block=18_000_000,
    )

    single_range_fail_plan.process_failed_backfill(11_000_000)

    dual_range_fail_plan.range_plan.mark_finalized(0)
    dual_range_fail_plan.range_plan.mark_failed(1, 17_000_000)

    assert len(single_range_fail_plan.range_plan.remove_backfills) == 0
    assert single_range_fail_plan.range_plan.add_backfill.start_block == 10_000_000
    assert single_range_fail_plan.range_plan.add_backfill.end_block == 11_000_000
    assert single_range_fail_plan.range_plan.add_backfill.backfill_id != conflict_id

    assert len(dual_range_fail_plan.range_plan.remove_backfills) == 0
    assert dual_range_fail_plan.range_plan.add_backfill.start_block == 10_000_000
    assert dual_range_fail_plan.range_plan.add_backfill.end_block == 17_000_000
