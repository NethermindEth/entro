import csv
import json
import os
from decimal import Decimal

from click.testing import CliRunner
from eth_utils import to_checksum_address
from sqlalchemy import select

from nethermind.entro.cli import entro_cli
from nethermind.entro.database.models.uniswap import (
    UniV3BurnEvent,
    UniV3CollectEvent,
    UniV3MintEvent,
)
from tests.resources.ABI import UNISWAP_V3_POOL_JSON

from .utils import printout_error_and_traceback


def test_backfill_mint_events_for_weth_wbtc_pool(
    integration_postgres_db,
    integration_db_session,
    cli_db_url,
    eth_rpc_cli_config,
    create_debug_logger,
):
    runner = CliRunner()
    migrate_res = runner.invoke(entro_cli, ["migrate-up", *cli_db_url])
    assert migrate_res.exit_code == 0

    with runner.isolated_filesystem():
        with open("UniswapV3Pool.json", "w") as f:
            f.write(UNISWAP_V3_POOL_JSON)

        result = runner.invoke(
            entro_cli,
            [
                "decode",
                "add-abi",
                "UniswapV3Pool",
                "UniswapV3Pool.json",
                *cli_db_url,
            ],
        )

        assert result.exit_code == 0

    mint_backfill_result = runner.invoke(
        entro_cli,
        [
            "backfill",
            "ethereum",
            "events",
            "-from",
            17_800_000,
            "-to",
            17_900_000,
            "--contract-address",
            to_checksum_address("0xcbcdf9626bc03e24f779434178a73a0b4bad62ed"),
            "-abi",
            "UniswapV3Pool",
            "--event-name",
            "Mint",
            *cli_db_url,
            *eth_rpc_cli_config,
        ],
        input="y",
    )

    assert mint_backfill_result.exit_code == 0

    expected_output = [
        "Backfill Block Ranges",
        "┌─────────────────────────┬────────────────────────┬──────────────────────────┐",
        "│ Start Block             │ End Block              │             Total Blocks │",
        "├─────────────────────────┼────────────────────────┼──────────────────────────┤",
        "│ 17,800,000              │ 17,900,000             │                  100,000 │",
        "└─────────────────────────┴────────────────────────┴──────────────────────────┘",
        "contract_address │ 0xCBCdF9626bC03E24f779434178A73a0B4bad62eD",
        "event_names      │ ['Mint']",
        "abi_name         │ UniswapV3Pool",
    ]

    for line in expected_output:
        assert line in mint_backfill_result.output

    mint_events = integration_db_session.execute(select(UniV3MintEvent)).scalars().all()
    assert mint_events[0].sender == "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"

    assert mint_events[0].amount == 32500065523907
    assert mint_events[0].tickLower == 254220
    assert mint_events[0].tickUpper == 258060

    assert mint_events[-1].amount == 5108528917685
    assert mint_events[-1].tickLower == 255480
    assert mint_events[-1].tickUpper == 258900

    assert len(mint_events) == 95


def test_cli_backfill_multiple_events(
    integration_postgres_db,
    integration_db_session,
    cli_db_url,
    eth_rpc_cli_config,
    create_debug_logger,
):
    runner = CliRunner()
    runner.invoke(entro_cli, ["migrate-up", *cli_db_url])

    with runner.isolated_filesystem():
        with open("UniswapV3Pool.json", "w") as f:
            f.write(UNISWAP_V3_POOL_JSON)

        result = runner.invoke(
            entro_cli,
            ["decode", "add-abi", "UniswapV3Pool", "UniswapV3Pool.json", *cli_db_url],
        )

        assert result.exit_code == 0

    event_backfill_res = runner.invoke(
        entro_cli,
        [
            "backfill",
            "ethereum",
            "events",
            "-from",
            18_000_000,
            "-to",
            18_005_000,
            "--contract-address",
            to_checksum_address("0xcbcdf9626bc03e24f779434178a73a0b4bad62ed"),
            "-abi",
            "UniswapV3Pool",
            "--event-name",
            "Mint",
            "--event-name",
            "Burn",
            "--event-name",
            "Collect",
            *cli_db_url,
            *eth_rpc_cli_config,
        ],
        input="y",
    )

    printout_error_and_traceback(event_backfill_res)

    expected_out = [
        "18,000,000",
        "18,005,000",
        "['Mint', 'Burn', 'Collect']",
    ]

    for out in expected_out:
        assert out in event_backfill_res.output

    mint_events = integration_db_session.execute(select(UniV3MintEvent)).scalars().all()
    burn_events = integration_db_session.execute(select(UniV3BurnEvent)).scalars().all()
    collect_events = integration_db_session.execute(select(UniV3CollectEvent)).scalars().all()

    assert event_backfill_res.exit_code == 0

    assert len(mint_events) == 6
    assert len(burn_events) == 7
    assert len(collect_events) == 8

    assert mint_events[0].tickLower == 250920
    assert mint_events[0].tickUpper == 264780

    assert mint_events[-1].tickLower == 251280
    assert mint_events[-1].tickUpper == 264360

    assert burn_events[0].tickLower == 255960
    assert burn_events[0].tickUpper == 258300

    assert burn_events[-1].tickLower == collect_events[-1].tickLower == 251280
    assert burn_events[-1].tickUpper == collect_events[-1].tickUpper == 264360

    assert burn_events[-1].amount0 == collect_events[-1].amount0 == Decimal("398206")
    assert burn_events[-1].amount1 == collect_events[-1].amount1 == Decimal("63404179018897713")


def test_event_cli_required_params(integration_postgres_db, integration_db_session, cli_db_url):
    runner = CliRunner()

    runner.invoke(entro_cli, ["migrate-up", *cli_db_url])

    missing_contract_address = runner.invoke(
        entro_cli,
        [
            "backfill",
            "ethereum",
            "events",
            "-abi",
            "UniswapV3Pool",
            "--event-name",
            "Mint",
            *cli_db_url,
        ],
    )

    missing_abi_name = runner.invoke(
        entro_cli,
        [
            "backfill",
            "ethereum",
            "events",
            "--contract-address",
            to_checksum_address("0xcbcdf9626bc03e24f779434178a73a0b4bad62ed"),
            "--event-name",
            "Mint",
            *cli_db_url,
        ],
    )

    invalid_abi = runner.invoke(
        entro_cli,
        [
            "backfill",
            "ethereum",
            "events",
            "--contract-address",
            to_checksum_address("0xcbcdf9626bc03e24f779434178a73a0b4bad62ed"),
            "-abi",
            "InvalidABI",
            "--event-name",
            "Mint",
            *cli_db_url,
        ],
    )

    assert missing_contract_address.exit_code == 2
    assert "Error: Missing option '--contract-address'" in missing_contract_address.output

    assert missing_abi_name.exit_code == 0
    assert "Must provide Valid ABI for Event Backfill" in missing_abi_name.output

    assert invalid_abi.exit_code == 0
    assert "not present in Cache: InvalidABI" in invalid_abi.output


def test_backfill_starknet_swaps(starknet_rpc_url):
    runner = CliRunner()

    with runner.isolated_filesystem():
        abi_result = runner.invoke(
            entro_cli,
            [
                "decode",
                "add-class",
                "AVNU-Exchange",
                "0x07b33a07ec099c227130ddffc9d74ad813fbcb8e0ff1c0f3ce097958e3dfc70b",
                "--priority=40",
                f"--json-rpc={starknet_rpc_url}",
            ],
        )

        assert abi_result.exit_code == 0

        backfill_result = runner.invoke(
            entro_cli,
            [
                "backfill",
                "starknet",
                "events",
                "--contract-address=0x04270219d365d6b017231b52e92b3fb5d7c8378b05e9abc97724537a80e93b0f",
                "--event-name=Swap",
                "-abi=AVNU-Exchange",
                f"--json-rpc={starknet_rpc_url}",
                "--from-block=600000",
                "--to-block=601000",
                "--event-file=swap_events.csv",
            ],
            input="y",
        )

        printout_error_and_traceback(backfill_result)

        assert backfill_result.exit_code == 0

        with open("swap_events.csv", "rt") as read_file:
            csv_reader = csv.reader(read_file, delimiter="|")

            swap_events = list(csv_reader)

        assert len(swap_events) == 8389

        assert swap_events[1][0] == "600000"
        assert swap_events[1][7] == "Swap"
        assert json.loads(swap_events[1][8])["buy_amount"] == 6953719595

        assert swap_events[-1][0] == "600990"
        assert swap_events[-1][7] == "Swap"
        assert json.loads(swap_events[-1][8])["buy_amount"] == 4546691991
