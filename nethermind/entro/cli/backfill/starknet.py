import logging

import click
from rich.prompt import Prompt

from entro.types.backfill import BackfillDataType, SupportedNetwork
from nethermind.entro.backfill import BackfillPlan
from nethermind.entro.cli.utils import (
    all_abis_option,
    block_file_option,
    cli_logger_config,
    create_cli_session,
    db_url_option,
    decode_abis_option,
    event_file_option,
    group_options,
    json_rpc_option,
    transaction_file_option,
)

root_logger = logging.getLogger("nethermind")
logger = root_logger.getChild("entro").getChild("cli").getChild("backfill")


@click.group(name="starknet")
def starknet_group():
    """Backfill StarkNet data from RPC"""
    pass


@starknet_group.command()
@group_options(
    json_rpc_option,
    db_url_option,
    block_file_option,
    transaction_file_option,
    event_file_option,
    decode_abis_option,
    all_abis_option,
)
def full_blocks(
    **kwargs,
):
    """Backfill StarkNet Blocks, Transactions, Receipts and Events"""
    console = cli_logger_config(root_logger)

    backfill_plan = BackfillPlan.generate(
        network=SupportedNetwork.starknet,
        backfill_type=BackfillDataType.full_blocks,
        **kwargs,
    )

    if backfill_plan.confirm():
        p = Prompt.ask("Execute Backfill? [y/n] ", console=console, choices=["y", "n"])
        if p == "n":
            return

    backfill_plan.execute(console=console)


@starknet_group.command()
def transactions():
    """Backfill StarkNet Transactions and Blocks"""
    pass


@starknet_group.command()
def events():
    """Backfill StarkNet events & ABI Decode"""
    pass
