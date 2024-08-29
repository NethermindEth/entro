import logging
import os

import click

from nethermind.entro.cli.utils import (
    all_abis_option,
    batch_size_option,
    block_file_option,
    cli_logger_config,
    contract_address_option,
    db_url_option,
    decode_abis_option,
    event_file_option,
    event_name_option,
    from_block_option,
    group_options,
    json_rpc_option,
    no_interaction_option,
    to_block_option,
    transaction_file_option,
    resolution_option,
)

root_logger = logging.getLogger("nethermind")
logger = root_logger.getChild("entro").getChild("cli").getChild("backfill")

# isort: skip_file
# pylint: disable=too-many-arguments,import-outside-toplevel,too-many-locals


@click.group(name="starknet")
def starknet_group():
    """Backfill StarkNet data from RPC"""


@starknet_group.command()
@group_options(
    json_rpc_option,
    db_url_option,
    from_block_option,
    to_block_option,
    block_file_option,
    transaction_file_option,
    event_file_option,
    decode_abis_option,
    all_abis_option,
    no_interaction_option,
)
def full_blocks(**kwargs):
    """Backfill StarkNet Blocks, Transactions, Receipts and Events"""

    from rich.prompt import Prompt
    from nethermind.entro.backfill import BackfillPlan
    from nethermind.entro.backfill.utils import GracefulKiller
    from nethermind.entro.types.backfill import BackfillDataType, SupportedNetwork

    console = cli_logger_config(root_logger)

    try:
        backfill_plan = BackfillPlan.from_cli(
            network=SupportedNetwork.starknet,
            backfill_type=BackfillDataType.full_blocks,
            supported_datasources=["json_rpc"],  # Add api_key for nethermind data apis
            **kwargs,
        )
    except BaseException as e:  # pylint: disable=broad-except
        logger.error(e)
        return

    if not backfill_plan.no_interaction:
        backfill_plan.print_backfill_plan(console)
        p = Prompt.ask("Execute Backfill? [y/n] ", console=console, choices=["y", "n"])
        if p == "n":
            return

    killer = GracefulKiller(console)

    backfill_plan.execute_backfill(console=console, killer=killer)

    killer.finalize(backfill_plan)


@starknet_group.command()
@group_options(
    json_rpc_option,
    db_url_option,
    from_block_option,
    to_block_option,
    block_file_option,
    transaction_file_option,
    decode_abis_option,
    all_abis_option,
    no_interaction_option,
)
def transactions(**kwargs):
    """Backfill StarkNet Transactions and Blocks"""

    from rich.prompt import Prompt
    from nethermind.entro.backfill import BackfillPlan
    from nethermind.entro.backfill.utils import GracefulKiller
    from nethermind.entro.types.backfill import BackfillDataType, SupportedNetwork

    console = cli_logger_config(root_logger)

    try:
        backfill_plan = BackfillPlan.from_cli(
            network=SupportedNetwork.starknet,
            backfill_type=BackfillDataType.transactions,
            supported_datasources=["json_rpc"],  # Add api_key for nethermind data apis
            **kwargs,
        )
    except BaseException as e:  # pylint: disable=broad-except
        logger.error(e)
        return

    if not backfill_plan.no_interaction:
        backfill_plan.print_backfill_plan(console)
        p = Prompt.ask("Execute Backfill? [y/n] ", console=console, choices=["y", "n"])
        if p == "n":
            return

    killer = GracefulKiller(console)

    backfill_plan.execute_backfill(console=console, killer=killer)

    killer.finalize(backfill_plan)


@starknet_group.command()
@group_options(
    json_rpc_option,
    db_url_option,
    from_block_option,
    to_block_option,
    contract_address_option,
    decode_abis_option,
    event_name_option,
    batch_size_option,
    event_file_option,
    no_interaction_option,
)
def events(**kwargs):
    """Backfill & ABI Decode StarkNet Events for a Contract"""

    from rich.prompt import Prompt
    from nethermind.entro.backfill import BackfillPlan
    from nethermind.entro.backfill.utils import GracefulKiller
    from nethermind.entro.types.backfill import BackfillDataType, SupportedNetwork

    console = cli_logger_config(root_logger)

    try:
        backfill_plan = BackfillPlan.from_cli(
            network=SupportedNetwork.starknet,
            backfill_type=BackfillDataType.events,
            supported_datasources=["json_rpc"],  # Add api_key for nethermind data apis
            **kwargs,
        )
    except BaseException as e:  # pylint: disable=broad-except
        logger.error(e)
        return

    if not backfill_plan.no_interaction:
        backfill_plan.print_backfill_plan(console)
        p = Prompt.ask("Execute Backfill? [y/n] ", console=console, choices=["y", "n"])
        if p == "n":
            return

    killer = GracefulKiller(console)

    backfill_plan.execute_backfill(console=console, killer=killer)

    killer.finalize(backfill_plan)


@starknet_group.command()
@group_options(
    json_rpc_option,
    db_url_option,
    resolution_option,
)
def timestamps(
    json_rpc,
    db_url,
    resolution,
):
    """Backfill & Load BlockTimestamps for Block <-> Time conversion"""

    from rich.progress import Progress
    from nethermind.entro.backfill.utils import progress_defaults
    from nethermind.entro.backfill.timestamps import TimestampConverter
    from nethermind.entro.types.backfill import SupportedNetwork

    console = cli_logger_config(root_logger)

    converter = TimestampConverter(
        network=SupportedNetwork.starknet, db_url=db_url, json_rpc=json_rpc, resolution=resolution, auto_update=False
    )

    logger.info(f"Backfilling Starknet timestamps with {converter.timestamp_resolution} block resolution")

    with Progress(*progress_defaults, console=console) as progress:
        converter.update_timestamps(progress_bar=progress)

    logger.info("Timestamps Backfilled & Up to Date")
