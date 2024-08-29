import pytest
from click.testing import CliRunner

from integration_tests.backfill_cli.utils import printout_error_and_traceback
from nethermind.entro.cli import entro_cli
from nethermind.entro.database.models import BackfilledRange

WETH_9 = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"


def test_backfill_ethereum_transactions(
    integration_postgres_db,
    cli_db_url,
    etherscan_cli_config,
    integration_db_session,
):
    runner = CliRunner()

    migrate = runner.invoke(entro_cli, ["migrate-up", *cli_db_url])
    assert migrate.exit_code == 0

    transaction_backfill = runner.invoke(
        entro_cli,
        [
            "backfill",
            "ethereum",
            "transactions",
            "--for-address",
            WETH_9,
            "-from",
            18_000_000,
            "-to",
            18_005_000,
            "--batch-size",
            500,
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
    assert backfills[0].filter_data == {"for_address": WETH_9}


@pytest.mark.skip("Non-Critical")
def test_required_parameters_for_etherscan_backfill(integration_postgres_db, cli_db_url, etherscan_cli_config):
    runner = CliRunner()

    migrate = runner.invoke(entro_cli, ["migrate-up", *cli_db_url])
    assert migrate.exit_code == 0

    no_api_key = runner.invoke(
        entro_cli,
        ["backfill", "ethereum", "transactions", "--for-address", WETH_9, *cli_db_url],
        input="y",
    )

    invalid_api_key = runner.invoke(
        entro_cli,
        [
            "backfill",
            "ethereum",
            "transactions",
            "--etherscan-api-key",
            "something",
            *cli_db_url,
        ],
        input="y",
    )

    printout_error_and_traceback(invalid_api_key)
    assert invalid_api_key.exit_code == 1
    assert no_api_key.exit_code == 1

    assert str(invalid_api_key.exception) == "Etherscan API keys are 34 characters long.  Double check --api-key"
    assert str(no_api_key.exception) == "API key is required for Etherscan backfill"


def test_backfill_all_txns_from_etherscan(
    integration_postgres_db, etherscan_cli_config, cli_db_url, create_debug_logger
):
    pass
    # Test rpc proxy functionality
