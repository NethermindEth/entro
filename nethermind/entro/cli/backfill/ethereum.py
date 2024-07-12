import logging

import click

from rich.logging import RichHandler
from rich.console import Console
from rich.prompt import Prompt
from rich.progress import Progress


from nethermind.entro.exceptions import DatabaseError, BackfillError

from nethermind.entro.types import BlockIdentifier
from nethermind.entro.backfill.planner import BackfillPlan
from nethermind.entro.types.backfill import (
    BackfillDataType,
    DataSources,
    SupportedNetwork,
)

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
    network_option,
    api_key_option,
    max_concurrency_option,
    create_cli_session,
    batch_size_option,
    page_size_option,
)
from nethermind.entro.backfill.utils import progress_defaults


# isort: skip_file
# pylint: disable=too-many-arguments,raise-missing-from,import-outside-toplevel,too-many-locals

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
    api_key_option,
    max_concurrency_option,
    batch_size_option,
    page_size_option,
)
def transactions(
    json_rpc: str,
    db_url: str,
    api_key: str | None,
    from_block: BlockIdentifier,
    to_block: BlockIdentifier,
    source: str,
    network: str,
    **kwargs,
):
    """Backfills transaction data"""
    rich_console = cli_logger_config(root_logger)
    db_session = create_cli_session(db_url)

    backfill_plan = BackfillPlan.generate(
        db_session=db_session,
        backfill_type=BackfillDataType.transactions,
        network=SupportedNetwork(network),
        start_block=from_block,
        end_block=to_block,
        **kwargs,
    )

    if backfill_plan is None:
        rich_console.print("Data Range Specified already exists in database.  Exiting...")
        return

    backfill_plan.print_backfill_plan(console=rich_console)

    rich_prompt = Prompt.ask(
        "Execute Backfill? [y/n] ",
        console=rich_console,
        show_choices=True,
        choices=["y", "n"],
    )
    if rich_prompt == "n":
        return

    with Progress(*progress_defaults, console=rich_console) as progress:
        match source:
            case "etherscan":
                from nethermind.entro.backfill.etherscan import (
                    etherscan_backfill_txs,
                )

                etherscan_backfill_txs(
                    backfill_plan=backfill_plan,
                    db_engine=db_session.get_bind(),
                    api_key=api_key,
                    progress=progress,
                )
            case "json_rpc":
                from nethermind.entro.backfill.json_rpc import cli_get_blocks

                cli_get_blocks(
                    backfill_plan=backfill_plan,
                    db_engine=db_session.get_bind(),
                    json_rpc=json_rpc,
                    progress=progress,
                )
            case _:
                raise ValueError("Invalid source")

        progress.console.print("[green]Backfill Complete...  Updating Backfill Status in Database")
        backfill_plan.save_to_db()
        db_session.close()


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
    network_option,
    source_option,
    batch_size_option,
)
def events(
    json_rpc: str,
    db_url: str,
    from_block: BlockIdentifier,
    to_block: BlockIdentifier,
    network: str,
    source: str,
    **kwargs,
):
    """Backfills event data"""
    rich_console = Console()
    root_logger.handlers.clear()

    root_logger.addHandler(RichHandler(show_path=False, console=rich_console))
    root_logger.setLevel(logging.WARNING)

    data_source = DataSources(source)
    db_session = create_cli_session(db_url)

    try:
        backfill_plan = BackfillPlan.generate(
            db_session=db_session,
            backfill_type=BackfillDataType.events,
            network=SupportedNetwork(network),
            start_block=from_block,
            end_block=to_block,
            **kwargs,
        )
    except (DatabaseError, BackfillError) as e:
        rich_console.print(f"[red]Error Occurred Generating Backfill: {e}")
        return

    if backfill_plan is None:
        rich_console.print("Data Range Specified already exists in database.  Exiting...")
        return

    backfill_plan.print_backfill_plan(console=rich_console)

    rich_prompt = Prompt.ask(
        "Execute Backfill? [y/n] ",
        console=rich_console,
        show_choices=True,
        choices=["y", "n"],
    )
    if rich_prompt == "n":
        return

    with Progress(*progress_defaults, console=rich_console) as progress:
        match data_source:
            case DataSources.json_rpc:
                from nethermind.entro.backfill.json_rpc import cli_get_logs

                cli_get_logs(
                    backfill_plan=backfill_plan,
                    db_engine=db_session.get_bind(),
                    json_rpc=json_rpc,
                    progress=progress,
                )

        progress.console.print("[green]Backfill Complete...  Updating Backfill Status in Database")
        backfill_plan.save_to_db()


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
    network_option,
    source_option,
    from_block_option,
    to_block_option,
    batch_size_option,
)
def blocks(
    json_rpc: str,
    db_url: str,
    network: str,
    source: str,
    from_block: BlockIdentifier,
    to_block: BlockIdentifier,
    **kwargs,
):
    """Backfills block data"""

    rich_console = Console()
    logger.handlers.clear()

    root_logger.addHandler(RichHandler(show_path=False, console=rich_console))
    root_logger.setLevel(logging.WARNING)

    db_session = create_cli_session(db_url)

    backfill_plan = BackfillPlan.generate(
        db_session=db_session,
        backfill_type=BackfillDataType.blocks,
        network=SupportedNetwork(network),
        start_block=from_block,
        end_block=to_block,
        **kwargs,
    )

    if backfill_plan is None:
        click.echo("Data Range Specified already exists in database.  Exiting...")
        return

    backfill_plan.print_backfill_plan(console=rich_console)

    rich_prompt = Prompt.ask(
        "Execute Backfill? [y/n] ",
        console=rich_console,
        show_choices=True,
        choices=["y", "n"],
    )
    if rich_prompt == "n":
        return

    with Progress(*progress_defaults, console=rich_console) as progress:
        match source:
            case "etherscan":
                raise NotImplementedError("Etherscan Block Backfill Not Yet Implemented")

            case "json_rpc":
                from nethermind.entro.backfill.json_rpc import cli_get_blocks

                cli_get_blocks(
                    backfill_plan=backfill_plan,
                    db_engine=db_session.get_bind(),
                    json_rpc=json_rpc,
                    progress=progress,
                )
            case _:
                raise ValueError("Invalid source")

        progress.console.print("\n[green]Backfill Complete...  Updating Backfill Status in Database")
        backfill_plan.save_to_db()


@ethereum_group.command()
@group_options(
    json_rpc_option,
    db_url_option,
    network_option,
    source_option,
    from_block_option,
    to_block_option,
    batch_size_option,
)
def full_blocks(
    json_rpc: str,
    db_url: str,
    network: str,
    source: str,
    from_block: BlockIdentifier,
    to_block: BlockIdentifier,
    **kwargs,
):
    """
    Backfill Blocks, Transactions w/ Receipts & Events
    """
