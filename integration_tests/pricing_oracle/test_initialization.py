from click.testing import CliRunner

from nethermind.entro.cli import entro_cli


def test_backfills_pool_creations(
    integration_postgres_db,
    integration_db_session,
    create_debug_logger,
    eth_rpc_cli_config,
    cli_db_url,
):
    runner = CliRunner()

    assert runner.invoke(entro_cli, ["migrate-up", *cli_db_url]).exit_code == 0

    oracle_init_result = runner.invoke(
        entro_cli,
        [
            "prices",
            "initialize",
            *cli_db_url,
            "--json-rpc",
            eth_rpc_cli_config.json_rpc,
        ],
    )
