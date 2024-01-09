import pytest
from click.testing import CliRunner

from python_eth_amm.backfill.planner import BackfillPlan
from python_eth_amm.cli.entry_point import cli_entry_point
from python_eth_amm.database.models.base import BackfilledRange
from python_eth_amm.database.models.migrations import migrate_up
from python_eth_amm.database.writers.utils import model_to_dict
from python_eth_amm.types.backfill import BackfillDataType, SupportedNetwork

from .utils import printout_error_and_traceback


@pytest.fixture(scope="function")
def setup_backfills(integration_postgres_db, integration_db_session, cli_db_url):
    runner = CliRunner()
    backfills = [
        BackfilledRange(
            start_block=18_000_000,
            end_block=18_000_020,
            data_type="blocks",
            network="ethereum",
        ),
        BackfilledRange(
            start_block=18_000_060,
            end_block=18_000_080,
            data_type="blocks",
            network="ethereum",
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
    runner = CliRunner()

    backfill_plan = BackfillPlan.generate(
        db_session=integration_db_session,
        backfill_type=BackfillDataType.blocks,
        network=SupportedNetwork.ethereum,
        start_block=18_000_020,
        end_block=18_000_060,
    )

    assert backfill_plan.block_ranges == [(18_000_020, 18_000_060)]

    assert len(backfill_plan.remove_backfills) == 2

    assert backfill_plan.add_backfill.start_block == 18_000_000
    assert backfill_plan.add_backfill.end_block == 18_000_080

    assert backfill_plan.total_blocks() == 40

    backfill = runner.invoke(
        cli_entry_point,
        [
            "backfill",
            "blocks",
            "-from",
            18_000_020,
            "-to",
            18_000_060,
            *eth_rpc_cli_config,
            *cli_db_url,
        ],
        input="y",
    )

    printout_error_and_traceback(backfill)

    assert backfill.exit_code == 0

    backfills = integration_db_session.query(BackfilledRange).all()
    for b in backfills:
        print(model_to_dict(b))

    assert len(backfills) == 1

    assert backfills[0].start_block == 18_000_000
    assert backfills[0].end_block == 18_000_080
    assert backfills[0].filter_data == {}


def test_start_inside_end_inside(
    integration_postgres_db,
    integration_db_session,
    cli_db_url,
    eth_rpc_cli_config,
    setup_backfills,
):
    runner = CliRunner()

    backfill_result = runner.invoke(
        cli_entry_point,
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


def test_extending_range_failed_backfill(
    integration_postgres_db, integration_db_session
):
    migrate_up(integration_db_session.get_bind())

    integration_db_session.add(
        BackfilledRange(
            start_block=12_000_000,
            end_block=14_000_000,
            data_type="blocks",
            network="ethereum",
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

    assert len(extension_backfill.remove_backfills) == 1
    assert extension_backfill.remove_backfills[0].start_block == 12_000_000
    assert extension_backfill.remove_backfills[0].end_block == 14_000_000

    assert extension_backfill.add_backfill.start_block == 12_000_000
    assert extension_backfill.add_backfill.end_block == 16_000_000


def test_single_range_failed_backfills(integration_postgres_db, integration_db_session):
    migrate_up(integration_db_session.get_bind())

    backfill_plan = BackfillPlan.generate(
        db_session=integration_db_session,
        backfill_type=BackfillDataType.blocks,
        network=SupportedNetwork.ethereum,
        start_block=18_000_000,
        end_block=18_200_000,
    )

    backfill_plan.process_failed_backfill(18_100_000)

    assert len(backfill_plan.remove_backfills) == 0
    assert backfill_plan.add_backfill.start_block == 18_000_000
    assert backfill_plan.add_backfill.end_block == 18_100_000


def test_multi_range_failed_backfills(integration_postgres_db, integration_db_session):
    migrate_up(integration_db_session.get_bind())
    integration_db_session.add(
        BackfilledRange(
            start_block=12_000_000,
            end_block=14_000_000,
            data_type="blocks",
            network="ethereum",
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
    dual_range_fail_plan.process_failed_backfill(17_000_000)

    assert len(single_range_fail_plan.remove_backfills) == 0
    assert single_range_fail_plan.add_backfill.start_block == 10_000_000
    assert single_range_fail_plan.add_backfill.end_block == 11_000_000

    assert len(dual_range_fail_plan.remove_backfills) == 1
    assert dual_range_fail_plan.remove_backfills[0].start_block == 12_000_000
    assert dual_range_fail_plan.remove_backfills[0].end_block == 14_000_000

    assert dual_range_fail_plan.add_backfill.start_block == 10_000_000
    assert dual_range_fail_plan.add_backfill.end_block == 17_000_000
