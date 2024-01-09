import logging

import click

from rich.console import Console
from rich.prompt import Prompt
from rich.progress import Progress


from python_eth_amm.exceptions import DecodingError, DatabaseError, BackfillError

from python_eth_amm.abi_decoder import DecodingDispatcher

from python_eth_amm.types import BlockIdentifier
from python_eth_amm.backfill.planner import BackfillPlan
from python_eth_amm.types.backfill import (
    BackfillDataType,
    DataSources,
    SupportedNetwork,
)

from .utils import (
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
    progress_defaults,
    batch_size_option,
    page_size_option,
)


# isort: skip_file
# pylint: disable=too-many-arguments,raise-missing-from,import-outside-toplevel,too-many-locals

package_logger = logging.getLogger("python_eth_amm")
logger = package_logger.getChild("backfill")


@click.command()
@group_options(db_url_option)
@click.argument("abi_name")
@click.argument("abi_json", type=click.File("r"))
@click.option("--priority", type=int, default=0)
def add_abi(db_url, abi_name, abi_json, priority):
    """Adds an ABI to the database"""

    import json
    from python_eth_amm.database.models.base import ContractABI, query_abis

    console = Console()
    db_session = create_cli_session(db_url)
    loaded_abis = query_abis(db_session)

    console.print(
        f"Attempting to add ABI {abi_name} to Decoder with priority {priority}.  Checking for "
        f"conflicts with {len(loaded_abis)} existing ABIs"
    )

    add_abi_dict = json.loads(abi_json.read())

    dispatcher = DecodingDispatcher()

    # These ABIs have already been verified and added to DB
    for existing_abi in loaded_abis:
        dispatcher.add_abi(
            existing_abi.abi_name,
            json.loads(existing_abi.abi_json)
            if isinstance(existing_abi.abi_json, str)
            else existing_abi.abi_json,
            existing_abi.priority,
        )

    try:
        dispatcher.add_abi(abi_name, add_abi_dict, priority)
    except DecodingError as e:
        logger.error(e)
        return

    db_session.add(
        ContractABI(
            abi_name=abi_name,
            abi_json=add_abi_dict,
            priority=priority,
        )
    )
    db_session.commit()

    click.echo(
        f"[green]Successfully Added {abi_name} to Database with Priority {priority}"
    )


@click.command()
@group_options(db_url_option)
def list_abis(db_url):
    """Lists all available ABIs that can be used for classification"""
    from python_eth_amm.database.models.base import query_abis

    db_session = create_cli_session(db_url)
    abis = query_abis(db_session)
    longest_abi_name = max(len(abi.abi_name) for abi in abis)
    click.echo("  ABI Name" + " " * (longest_abi_name - 4) + "Priority")
    click.echo_via_pager(
        f"\t{abi.abi_name} {'-' * (longest_abi_name - len(abi.abi_name) + 2)}> {abi.priority}\n"
        for abi in abis
    )


@click.command()
@click.option("--full-signatures", is_flag=True, default=False)
@group_options(db_url_option)
def list_abi_decoders(db_url, full_signatures):
    """Lists all Available ABIs in Database, along with the function and event signatures each ABI will classify"""

    db_session = create_cli_session(db_url)
    decoder = DecodingDispatcher.from_database(
        classify_abis=[], db_session=db_session, all_abis=True
    )
    console = Console()

    console.print(decoder.decoder_table(full_signatures=full_signatures))


@click.group(short_help="Backfill data from RPC nodes or APIs")
def backfill_group():
    """
    Provides utilities for backfilling blockchain data.

    Can be used for downloading event data from Full nodes, trace data from archive
    nodes, or base transaction data from Etherscan.
    """


@backfill_group.command(name="list")
def list_backfills():
    """Lists all currently backfilled data in the database"""


@backfill_group.command()
@group_options(
    json_rpc_option,
    db_url_option,
    from_block_option,
    to_block_option,
    for_address_option,
    decode_abis_option,
    all_abis_option,
    source_option,
    network_option,
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
    db_session = create_cli_session(db_url)
    rich_console = Console()

    try:
        backfill_plan = BackfillPlan.generate(
            db_session=db_session,
            backfill_type=BackfillDataType.transactions,
            network=SupportedNetwork(network),
            start_block=from_block,
            end_block=to_block,
            **kwargs,
        )
    except (DatabaseError, ValueError) as e:
        rich_console.print(f"[red]Error Occurred Computing Backfill: {e}")
        return

    if backfill_plan is None:
        rich_console.print(
            "Data Range Specified already exists in database.  Exiting..."
        )
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
                from python_eth_amm.backfill.etherscan import (
                    etherscan_backfill_txs,
                )

                etherscan_backfill_txs(
                    backfill_plan=backfill_plan,
                    db_engine=db_session.get_bind(),
                    api_key=api_key,
                    progress=progress,
                )
            case "json_rpc":
                from python_eth_amm.backfill.json_rpc import cli_get_blocks

                cli_get_blocks(
                    backfill_plan=backfill_plan,
                    db_engine=db_session.get_bind(),
                    json_rpc=json_rpc,
                    progress=progress,
                )
            case _:
                raise ValueError("Invalid source")

        progress.console.print(
            "[green]Backfill Complete...  Updating Backfill Status in Database"
        )
        backfill_plan.save_to_db(db_session)
        db_session.close()


@backfill_group.command()
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
    data_source = DataSources(source)
    db_session = create_cli_session(db_url)
    rich_console = Console()

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
        rich_console.print(
            "Data Range Specified already exists in database.  Exiting..."
        )
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
                from python_eth_amm.backfill.json_rpc import cli_get_logs

                cli_get_logs(
                    backfill_plan=backfill_plan,
                    db_engine=db_session.get_bind(),
                    json_rpc=json_rpc,
                    progress=progress,
                )

        progress.console.print(
            "[green]Backfill Complete...  Updating Backfill Status in Database"
        )
        backfill_plan.save_to_db(db_session)


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


@backfill_group.command()
@click.option(
    "--full-blocks",
    is_flag=True,
    default=None,
    help="Backfill Transactions, Receipts, and Logs",
)
@group_options(
    json_rpc_option,
    db_url_option,
    network_option,
    source_option,
    from_block_option,
    to_block_option,
    api_key_option,
    decode_abis_option,
    all_abis_option,
    batch_size_option,
)
def blocks(
    json_rpc: str,
    db_url: str,
    network: str,
    source: str,
    from_block: BlockIdentifier,
    to_block: BlockIdentifier,
    api_key: str | None,
    **kwargs,
):
    """Backfills block data"""

    full_blocks = kwargs.get("full_blocks", False)
    rich_console = Console()

    db_session = create_cli_session(db_url)

    backfill_plan = BackfillPlan.generate(
        db_session=db_session,
        backfill_type=BackfillDataType.full_blocks
        if full_blocks
        else BackfillDataType.blocks,
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
                from python_eth_amm.backfill.etherscan import (
                    etherscan_backfill_blocks,
                )

                etherscan_backfill_blocks(
                    backfill_plan=backfill_plan,
                    db_engine=db_session.get_bind(),
                    api_key=api_key,
                    progress=progress,
                )

            case "json_rpc":
                if full_blocks:
                    from python_eth_amm.backfill.json_rpc import (
                        cli_get_full_blocks,
                    )

                    cli_get_full_blocks(
                        backfill_plan=backfill_plan,
                        db_engine=db_session.get_bind(),
                        json_rpc=json_rpc,
                        progress=progress,
                    )

                else:
                    from python_eth_amm.backfill.json_rpc import cli_get_blocks

                    cli_get_blocks(
                        backfill_plan=backfill_plan,
                        db_engine=db_session.get_bind(),
                        json_rpc=json_rpc,
                        progress=progress,
                    )
            case _:
                raise ValueError("Invalid source")

        progress.console.print(
            "\n[green]Backfill Complete...  Updating Backfill Status in Database"
        )
        backfill_plan.save_to_db(db_session)
