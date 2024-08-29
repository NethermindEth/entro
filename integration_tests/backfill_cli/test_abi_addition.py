from click.testing import CliRunner

from nethermind.entro.cli import entro_cli
from nethermind.entro.database.models.ethereum import Transaction
from tests.resources.ABI import (
    ERC20_ABI_JSON,
    UNISWAP_V2_PAIR_JSON,
    UNISWAP_V3_POOL_JSON,
)

from .utils import printout_error_and_traceback


def test_add_ERC_20_ABI(integration_postgres_db, cli_db_url):
    runner = CliRunner()

    with runner.isolated_filesystem():
        migrate = runner.invoke(entro_cli, ["migrate-up", *cli_db_url])

        assert migrate.exit_code == 0

        with open("ERC20.json", "w") as f:
            f.write(ERC20_ABI_JSON)

        result = runner.invoke(entro_cli, ["decode", "add-abi", "ERC20", "ERC20.json", *cli_db_url])

    assert result.exit_code == 0
    assert "Successfully Added ERC20 to Database with Priority 0" in result.output


def test_add_duplicate_abis(integration_postgres_db, cli_db_url, caplog):
    runner = CliRunner()

    with runner.isolated_filesystem():
        migration = runner.invoke(entro_cli, ["migrate-up", *cli_db_url])

        assert migration.exit_code == 0

        with open("ERC20.json", "w") as f:
            f.write(ERC20_ABI_JSON)

        abi_1_result = runner.invoke(entro_cli, ["decode", "add-abi", "ERC20", "ERC20.json", *cli_db_url])

        assert abi_1_result.exit_code == 0
        assert "Successfully Added ERC20 to Database with Priority 0" in abi_1_result.output

        abi_2_result = runner.invoke(entro_cli, ["decode", "add-abi", "ERC20", "ERC20.json", *cli_db_url])

        assert abi_2_result.exit_code == 0
        assert "ERC20 ABI already loaded into dispatcher" in caplog.text


def test_add_nonexistent_file(cli_db_url):
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(
            entro_cli,
            ["decode", "add-abi", "UniswapV3Pool", "UniswapV3Pool.json", *cli_db_url],
        )

        assert result.exit_code == 2
        assert "Error: Invalid value for 'ABI_JSON': 'UniswapV3Pool.json': No such file or directory" in result.output


def test_abi_decoding(
    integration_postgres_db,
    cli_db_url,
    etherscan_cli_config,
    integration_db_session,
):
    runner = CliRunner()

    weth_9 = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"

    with runner.isolated_filesystem():
        with open("ERC20.json", "w") as f:
            f.write(ERC20_ABI_JSON)

        runner.invoke(entro_cli, ["migrate-up", *cli_db_url])
        runner.invoke(entro_cli, ["decode", "add-abi", "ERC20", "ERC20.json", *cli_db_url])

        backfill_result = runner.invoke(
            entro_cli,
            [
                "backfill",
                "ethereum",
                "transactions",
                "--for-address",
                weth_9,
                "-from",
                18_000_000,
                "-to",
                18_000_100,
                "-abi",
                "ERC20",
                *cli_db_url,
                *etherscan_cli_config,
            ],
            input="y",
        )

        printout_error_and_traceback(backfill_result)

        assert backfill_result.exit_code == 0

        transactions = integration_db_session.query(Transaction).all()

        assert len(transactions) == 113

        for transaction in transactions:
            assert transaction.to_address == weth_9

            if transaction.function_name in ["transfer", "approve"]:
                assert transaction.decoded_input is not None

            else:
                assert transaction.decoded_input is None


def test_list_abis(integration_postgres_db, cli_db_url):
    runner = CliRunner()

    with runner.isolated_filesystem():
        with open("ERC20.json", "w") as f:
            f.write(ERC20_ABI_JSON)

        with open("UniswapV2Pair.json", "w") as f:
            f.write(UNISWAP_V2_PAIR_JSON)

        with open("UniswapV3Pool.json", "w") as f:
            f.write(UNISWAP_V3_POOL_JSON)

        migrate_res = runner.invoke(entro_cli, ["migrate-up", *cli_db_url])
        erc_res = runner.invoke(
            entro_cli,
            ["decode", "add-abi", "ERC20", "ERC20.json", "--priority", "10", *cli_db_url],
        )
        v2_res = runner.invoke(
            entro_cli,
            [
                "decode",
                "add-abi",
                "UniswapV2Pair",
                "UniswapV2Pair.json",
                "--priority",
                "9",
                *cli_db_url,
            ],
        )
        v3_res = runner.invoke(
            entro_cli,
            [
                "decode",
                "add-abi",
                "UniswapV3Pool",
                "UniswapV3Pool.json",
                "--priority",
                "8",
                *cli_db_url,
            ],
        )

        assert migrate_res.exit_code == 0
        assert erc_res.exit_code == 0
        assert v2_res.exit_code == 0
        assert v3_res.exit_code == 0

        list_result = runner.invoke(entro_cli, ["decode", "list-abis", *cli_db_url])

        assert list_result.exit_code == 0

        expected_text = [
            "-- EVM ABIs --",
            "ERC20",
            "UniswapV2Pair",
        ]

        for text in expected_text:
            assert text in list_result.output

        list_decoders_result = runner.invoke(entro_cli, ["decode", "list-abi-decoders", "EVM", *cli_db_url])

        assert "'Approval'," in list_decoders_result.output
        assert "'Transfer'," in list_decoders_result.output
        assert "'burn'," in list_decoders_result.output
        assert "'collect'," in list_decoders_result.output
        assert list_decoders_result.exit_code == 0


def test_abi_priority_raises(integration_postgres_db, cli_db_url, caplog):
    runner = CliRunner()

    with runner.isolated_filesystem():
        with open("ERC20.json", "w") as f:
            f.write(ERC20_ABI_JSON)

        with open("UniswapV2Pair.json", "w") as f:
            f.write(UNISWAP_V2_PAIR_JSON)

        runner.invoke(entro_cli, ["migrate-up", *cli_db_url])

        add_erc_result = runner.invoke(entro_cli, ["decode", "add-abi", "ERC20", "ERC20.json", *cli_db_url])
        add_uni_v2_result = runner.invoke(
            entro_cli,
            ["decode", "add-abi", "UniswapV2Pair", "UniswapV2Pair.json", *cli_db_url],
        )

        assert add_erc_result.exit_code == 0
        assert add_uni_v2_result.exit_code == 0

        assert (
            "ABI UniswapV2Pair and ERC20 share the decoder for the function decimals, and both are set to priority 0"
            in caplog.text
        )
