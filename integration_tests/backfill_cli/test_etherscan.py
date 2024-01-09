from click.testing import CliRunner

from integration_tests.backfill_cli.utils import printout_error_and_traceback
from python_eth_amm.cli.entry_point import cli_entry_point
from python_eth_amm.database.models.base import BackfilledRange


def test_backfill_ethereum_transactions(
    integration_postgres_db,
    cli_db_url,
    etherscan_cli_config,
    integration_db_session,
):
    runner = CliRunner()

    weth_9 = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"

    migrate = runner.invoke(cli_entry_point, ["migrate-up", *cli_db_url])
    assert migrate.exit_code == 0

    transaction_backfill = runner.invoke(
        cli_entry_point,
        [
            "backfill",
            "transactions",
            "--for-address",
            weth_9,
            "-from",
            18_000_000,
            "-to",
            18_005_000,
            *cli_db_url,
            *etherscan_cli_config,
        ],
        input="y",
    )

    printout_error_and_traceback(transaction_backfill)

    assert transaction_backfill.exit_code == 0

    backfills = integration_db_session.query(BackfilledRange).all()

    assert len(backfills) == 1
    assert backfills[0].start_block == 18_000_000
    assert backfills[0].end_block == 18_005_000
    assert backfills[0].filter_data == {
        "for_address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
    }


def test_required_parameters_for_etherscan_backfill(
    integration_postgres_db, cli_db_url, etherscan_cli_config
):
    runner = CliRunner()

    migrate = runner.invoke(cli_entry_point, ["migrate-up", *cli_db_url])
    assert migrate.exit_code == 0

    no_api_key = runner.invoke(
        cli_entry_point,
        ["backfill", "transactions", "--source", "etherscan", *cli_db_url],
        input="y",
    )

    invalid_api_key = runner.invoke(
        cli_entry_point,
        [
            "backfill",
            "transactions",
            "--source",
            "etherscan",
            "--api-key",
            "invalid",
            *cli_db_url,
        ],
        input="y",
    )

    printout_error_and_traceback(invalid_api_key)
    assert invalid_api_key.exit_code == 1
    assert no_api_key.exit_code == 1

    assert (
        str(invalid_api_key.exception)
        == "Etherscan API keys are 34 characters long.  Double check --api-key"
    )
    assert str(no_api_key.exception) == "API key is required for Etherscan backfill"


def test_backfill_all_txns_from_etherscan(
    integration_postgres_db, etherscan_cli_config, cli_db_url, create_debug_logger
):
    pass
    # Test rpc proxy functionality
