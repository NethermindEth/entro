import logging

import click

from nethermind.entro.cli.utils import (
    cli_logger_config,
    db_url_option,
    group_options,
    json_rpc_option,
    from_block_option,
    to_block_option,
    for_address_option,
    decode_abis_option,
    all_abis_option,
    contract_address_option,
    event_name_option,
    source_option,
    etherscan_api_key_option,
    max_concurrency_option,
    batch_size_option,
    page_size_option,
    block_file_option,
    transaction_file_option,
    resolution_option,
)

# isort: skip_file
# pylint: disable=too-many-arguments,import-outside-toplevel,too-many-locals

root_logger = logging.getLogger("nethermind")
logger = root_logger.getChild("entro").getChild("backfill")


@click.group(name="ethereum", short_help="Backfill data from RPC nodes or APIs")
def ethereum_group():
    """
    Provides utilities for backfilling blockchain data.

    Can be used for downloading event data from Full nodes, trace data from archive
    nodes, or base transaction data from Etherscan.
    """


@ethereum_group.command()
@group_options(
    json_rpc_option,
    db_url_option,
    from_block_option,
    to_block_option,
    for_address_option,
    decode_abis_option,
    all_abis_option,
    etherscan_api_key_option,
    max_concurrency_option,
    batch_size_option,
    page_size_option,
    block_file_option,
    transaction_file_option,
)
def transactions(
    **kwargs,
):
    """Backfills transaction data"""
    from rich.prompt import Prompt
    from nethermind.entro.types.backfill import BackfillDataType, SupportedNetwork
    from nethermind.entro.backfill.planner import BackfillPlan
    from nethermind.entro.backfill.utils import GracefulKiller

    console = cli_logger_config(root_logger)

    try:
        backfill_plan = BackfillPlan.from_cli(
            network=SupportedNetwork.ethereum,
            backfill_type=BackfillDataType.transactions,
            supported_datasources=["json_rpc", "etherscan_api_key"],
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


@ethereum_group.command()
@click.option(
    "--db-model",
    "db_models",
    nargs=2,
    type=(str, str),
    multiple=True,
    help="Database Models to use for backfill.  First argument is the name of the Event, second argument is the name "
    "of the database table to save that event to.  ie. --db_models (Swap, uniswap.v3_swap_events)",
)
@group_options(
    json_rpc_option,
    db_url_option,
    from_block_option,
    to_block_option,
    contract_address_option,
    decode_abis_option,
    event_name_option,
    source_option,
    batch_size_option,
)
def events(
    **kwargs,
):
    """Backfills event data"""
    from rich.prompt import Prompt
    from nethermind.entro.types.backfill import BackfillDataType, SupportedNetwork
    from nethermind.entro.backfill.planner import BackfillPlan
    from nethermind.entro.backfill.utils import GracefulKiller

    console = cli_logger_config(root_logger)

    try:
        backfill_plan = BackfillPlan.from_cli(
            backfill_type=BackfillDataType.events,
            network=SupportedNetwork.ethereum,
            supported_datasources=["json_rpc"],
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


# @backfill_group.command()
# @group_options(
#     json_rpc_option,
#     db_url_option,
#     from_block_option,
#     to_block_option,
#     classify_abis_option,
# )
# @click.argument("from-address")
# @click.argument("etherscan-api-key")
# def traces(
#     json_rpc: str,
#     db_url: str,
#     from_block: int,
#     to_block: int,
#     from_address: str,
#     etherscan_api_key,
#     decode_abis: list[str],
# ):
#     """Backfills trace data"""
#
#     # Step 1: Clean up inputs & Validate Data
#     # Step 2: Search for existing backfills
#     # Step 3: Compute Required Backfills
#     # Step 4: Send Backfill Plan to User for Confirmation
#     # Step 5: Execute Backfill
#     # Step 6: Send Performance Data to User
#     pass


@ethereum_group.command()
@group_options(
    json_rpc_option,
    db_url_option,
    source_option,
    from_block_option,
    to_block_option,
    batch_size_option,
    block_file_option,
)
def blocks(
    **kwargs,
):
    """Backfills Ethereum block data"""

    from rich.prompt import Prompt
    from nethermind.entro.types.backfill import BackfillDataType, SupportedNetwork
    from nethermind.entro.backfill.planner import BackfillPlan
    from nethermind.entro.backfill.utils import GracefulKiller

    console = cli_logger_config(root_logger)

    try:
        backfill_plan = BackfillPlan.from_cli(
            backfill_type=BackfillDataType.blocks,
            network=SupportedNetwork.ethereum,
            supported_datasources=["json_rpc"],
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


@ethereum_group.command()
@group_options(
    json_rpc_option,
    db_url_option,
    source_option,
    from_block_option,
    to_block_option,
    batch_size_option,
)
def full_blocks(
    **kwargs,
):
    """
    Backfill Blocks, Transactions w/ Receipts & Events
    """

    from rich.prompt import Prompt
    from nethermind.entro.types.backfill import BackfillDataType, SupportedNetwork
    from nethermind.entro.backfill.planner import BackfillPlan
    from nethermind.entro.backfill.utils import GracefulKiller

    console = cli_logger_config(root_logger)

    try:
        backfill_plan = BackfillPlan.from_cli(
            backfill_type=BackfillDataType.full_blocks,
            network=SupportedNetwork.ethereum,
            supported_datasources=["json_rpc"],
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


@ethereum_group.command()
@group_options(
    json_rpc_option,
    db_url_option,
    resolution_option,
)
def timestamps(
    json_rpc: str | None,
    db_url: str | None,
    resolution: int | None,
):
    """Backfills Ethereum Block Timestamps for the TimestampConverter utility"""
    from rich.progress import Progress

    from nethermind.entro.backfill.timestamps import TimestampConverter
    from nethermind.entro.backfill.utils import progress_defaults
    from nethermind.entro.types.backfill import SupportedNetwork

    console = cli_logger_config(root_logger)

    timestamp_converter = TimestampConverter(
        network=SupportedNetwork.ethereum,
        db_url=db_url,
        json_rpc=json_rpc,
        resolution=resolution,
        auto_update=False,
    )

    logger.info(f"Backfilling Ethereum timestamps with {timestamp_converter.timestamp_resolution} block resolution")

    with Progress(*progress_defaults, console=console) as progress:
        timestamp_converter.update_timestamps(progress)

    logger.info("Timestamp Backfill Complete")
