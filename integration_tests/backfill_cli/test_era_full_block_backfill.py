from click.testing import CliRunner

from integration_tests.backfill_cli.utils import printout_error_and_traceback
from python_eth_amm.cli.entry_point import cli_entry_point
from python_eth_amm.database.models.zk_sync import (
    EraBlock,
    EraDefaultEvent,
    EraTransaction,
)
from python_eth_amm.database.writers.utils import model_to_dict
from tests.resources.ABI import (
    ERC20_ABI_JSON,
    ERC721_ABI_JSON,
    SYNC_SWAP_CLASSIC_PAIR_JSON,
    SYNC_SWAP_ROUTER_JSON,
    SYNC_SWAP_STABLE_PAIR_JSON,
)


def test_full_backfill_zk_sync_era(
    integration_postgres_db,
    integration_db_session,
    cli_db_url,
    create_debug_logger,
):
    runner = CliRunner()

    migrate_res = runner.invoke(cli_entry_point, ["migrate-up", *cli_db_url])
    assert migrate_res.exit_code == 0

    with runner.isolated_filesystem():
        with open("SyncSwapRouter.json", "w") as f:
            f.write(SYNC_SWAP_ROUTER_JSON)

        with open("SyncSwapClassicPair.json", "w") as f:
            f.write(SYNC_SWAP_CLASSIC_PAIR_JSON)

        with open("SyncSwapStablePair.json", "w") as f:
            f.write(SYNC_SWAP_STABLE_PAIR_JSON)

        with open("ERC20.json", "w") as f:
            f.write(ERC20_ABI_JSON)

        with open("ERC721.json", "w") as f:
            f.write(ERC721_ABI_JSON)

        erc_20_res = runner.invoke(
            cli_entry_point,
            [
                "add-abi",
                "ERC20",
                "ERC20.json",
                "--priority",
                120,
                *cli_db_url,
            ],
        )
        erc_721_res = runner.invoke(
            cli_entry_point,
            [
                "add-abi",
                "ERC721",
                "ERC721.json",
                "--priority",
                110,
                *cli_db_url,
            ],
        )

        classic_res = runner.invoke(
            cli_entry_point,
            [
                "add-abi",
                "SyncSwapClassicPair",
                "SyncSwapClassicPair.json",
                "--priority",
                100,
                *cli_db_url,
            ],
        )
        stable_res = runner.invoke(
            cli_entry_point,
            [
                "add-abi",
                "SyncSwapStablePair",
                "SyncSwapStablePair.json",
                "--priority",
                90,
                *cli_db_url,
            ],
        )
        router_res = runner.invoke(
            cli_entry_point,
            [
                "add-abi",
                "SyncSwapRouter",
                "SyncSwapRouter.json",
                "--priority",
                80,
                *cli_db_url,
            ],
        )
        assert erc_20_res.exit_code == 0
        assert erc_721_res.exit_code == 0
        assert classic_res.exit_code == 0
        assert stable_res.exit_code == 0
        assert router_res.exit_code == 0

    backfill_res = runner.invoke(
        cli_entry_point,
        [
            "backfill",
            "blocks",
            "--full-blocks",
            "--all-abis",
            "--from-block",
            17570000,
            "--to-block",
            17570100,
            "--network",
            "zk_sync_era",
            "--json-rpc",
            "https://mainnet.era.zksync.io/",
            *cli_db_url,
        ],
        input="y",
    )

    printout_error_and_traceback(backfill_res)
    assert backfill_res.exit_code == 0

    events = integration_db_session.query(EraDefaultEvent).all()

    assert events[0].block_number == 17570000
    assert events[0].transaction_index == 0
    assert events[0].event_name == "Transfer"
    assert events[0].abi_name == "ERC20"
    assert (
        events[0].decoded_event["from"] == "0x31D043dDBE1f798c1B75553cbbE90f98d293CbEC"
    )
    assert events[0].decoded_event["value"] == 218622000000000

    assert len(events) == 5235

    txns = integration_db_session.query(EraTransaction).all()

    assert txns[0].block_number == 17570000
    assert (
        txns[0].transaction_hash.hex()
        == "75a3b863cd5232539bc6802269c9aaaaaec9dc2a54241629591f10512e102933"
    )
    assert txns[0].timestamp == 1698541582
    assert (
        txns[0].decoded_signature
        == "swap(((address,bytes,address,bytes)[],address,uint256)[],uint256,uint256)"
    )
    assert "paths" in txns[0].decoded_input
    assert txns[0].gas_used == 304515

    assert txns[-1].block_number == 17570099
    assert (
        txns[-1].transaction_hash.hex()
        == "72fe1733be6e45a715b71d078358294f08f24c93a1c4c5c80a291f96a7eb4ddc"
    )
    assert txns[-1].gas_used == 538740

    assert len(txns) == 927

    blocks = integration_db_session.query(EraBlock).all()
    assert blocks[0].block_number == 17570000
    assert blocks[0].timestamp == 1698541582
    assert blocks[-1].block_number == 17570099
    assert blocks[-1].timestamp == 1698541685

    assert len(blocks) == 100
