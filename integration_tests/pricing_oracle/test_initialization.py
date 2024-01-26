import pytest
from click.testing import CliRunner

from python_eth_amm.cli.entry_point import cli_entry_point


def test_backfills_pool_creations(
    integration_postgres_db,
    integration_db_session,
    create_debug_logger,
    eth_rpc_cli_config,
    cli_db_url,
):
    runner = CliRunner()

    assert runner.invoke(cli_entry_point, ["migrate-up", *cli_db_url]).exit_code == 0

    oracle_init_result = runner.invoke(
        cli_entry_point,
        [
            "prices",
            "initialize",
            *cli_db_url,
            "--json-rpc",
            eth_rpc_cli_config.json_rpc,
        ],
    )
