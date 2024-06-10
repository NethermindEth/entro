from click.testing import CliRunner

from nethermind.entro.cli import entro_cli
from nethermind.entro.database.models.ethereum import Block, DefaultEvent, Transaction
from nethermind.entro.database.writers.utils import db_encode_dict, model_to_dict

from .utils import printout_error_and_traceback


def test_backfill_mainnet_full_block(
    integration_postgres_db,
    integration_db_session,
    cli_db_url,
    eth_rpc_cli_config,
    create_debug_logger,
    add_abis_to_db,
):
    runner = CliRunner()

    mig_result = runner.invoke(entro_cli, ["migrate-up", *cli_db_url])
    assert mig_result.exit_code == 0

    add_abis_to_db(runner)

    backfill_result = runner.invoke(
        entro_cli,
        [
            "backfill",
            "blocks",
            "--full-blocks",
            "--from-block",
            "18_000_000",
            "--to-block",
            "18_000_020",
            "--all-abis",
            *eth_rpc_cli_config,
            *cli_db_url,
        ],
        "y",
    )

    printout_error_and_traceback(backfill_result)

    assert backfill_result.exit_code == 0

    events = integration_db_session.query(DefaultEvent).all()
    txns = integration_db_session.query(Transaction).all()
    blocks = integration_db_session.query(Block).all()

    assert events[-1].block_number == 18000019
    assert events[-1].transaction_index == 146
    assert events[-1].log_index == 408
    assert events[-1].event_name == "Swap"
    assert events[-1].abi_name == "UniswapV2Pair"
    assert events[-1].decoded_event["amount1In"] == 30000000000000000
    assert events[-1].decoded_event["sender"] == "0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD"
    assert events[-1].decoded_event["to"] == "0xb9e4345182bE80E45a5E649367F25ffB0cD9Aed3"

    assert len(events) == 5250

    assert txns[0].block_number == 18000000
    assert txns[0].transaction_hash.hex() == "16e199673891df518e25db2ef5320155da82a3dd71a677e7d84363251885d133"
    assert txns[0].timestamp == 1693066895
    assert txns[0].gas_used == 60440

    assert txns[-1].block_number == 18000019
    assert txns[-1].timestamp == 1693067123
    assert txns[-1].transaction_hash.hex() == "a3b459efcd2b0e906efe05d878d454e6b40699358324d8729c07edcbf06df5bc"
    assert txns[-1].gas_used == 27527

    assert len(txns) == 2696

    assert blocks[0].block_number == 18000000
    assert blocks[0].gas_used == 16_247_211
    assert blocks[0].effective_gas_price == 21_721_091_641
    assert blocks[0].transaction_count == 94

    assert blocks[-1].block_number == 18000019
    assert blocks[-1].gas_used == 14_309_399
    assert blocks[-1].effective_gas_price == 20_117_274_455
    assert blocks[-1].transaction_count == 150

    assert sum([b.transaction_count for b in blocks]) == len(txns)
    assert len(blocks) == 20
