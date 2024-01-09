import traceback

import pytest
from click.testing import CliRunner

from python_eth_amm.cli.entry_point import cli_entry_point
from python_eth_amm.database.models.base import BackfilledRange
from python_eth_amm.database.models.starknet import Block


@pytest.mark.skip(reason="Voyager API Wrapper is in Beta and Not yet Complete")
def test_backfill_voyager_blocks(
    integration_postgres_db,
    integration_db_session,
    cli_db_url,
    voyager_cli_config,
    create_debug_logger,
):
    runner = CliRunner()

    migrate = runner.invoke(cli_entry_point, ["migrate-up", *cli_db_url])

    assert migrate.exit_code == 0

    block_backfill = runner.invoke(
        cli_entry_point,
        [
            "backfill",
            "blocks",
            "-from",
            290_000,
            "-to",
            290_200,
            "--network",
            "starknet",
            *voyager_cli_config,
            *cli_db_url,
        ],
        input="y",
    )

    if block_backfill.exit_code != 0:
        print("Error During Block Backfill: ", block_backfill.exc_info)
        print(traceback.print_exception(block_backfill.exc_info[1]))

    assert block_backfill.exit_code == 0

    blocks = integration_db_session.query(Block).order_by(Block.block_number).all()

    assert len(blocks) == 200

    assert blocks[0].block_number == 290_000
    assert blocks[-1].block_number == 290_199

    backfilled_ranges = integration_db_session.query(BackfilledRange).all()

    assert len(backfilled_ranges) == 1
    assert backfilled_ranges[0].start_block == 290_000
    assert backfilled_ranges[0].end_block == 290_200
    assert backfilled_ranges[0].filter_data is None
    assert backfilled_ranges[0].network == "starknet"
    assert backfilled_ranges[0].data_type == "blocks"
