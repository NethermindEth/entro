import logging

import click

from rich.logging import RichHandler
from rich.console import Console


from nethermind.entro.exceptions import DecodingError
from nethermind.entro.decoding import DecodingDispatcher


from nethermind.entro.cli.utils import (
    db_url_option,
    group_options,
    create_cli_session,
)

# isort: skip_file
# pylint: disable=too-many-arguments,raise-missing-from,import-outside-toplevel,too-many-locals

root_logger = logging.getLogger("nethermind")
logger = root_logger.getChild("entro").getChild("backfill")


@click.group("decoding", short_help="ABI Decoding & Event Classification")
def decoding_group():
    pass


@decoding_group.command()
@group_options(db_url_option)
@click.argument("abi_name")
@click.argument("abi_json", type=click.File("r"))
@click.option("--priority", type=int, default=0)
def add_abi(db_url, abi_name, abi_json, priority):
    """Adds an ABI to the database"""

    import json
    from nethermind.entro.database.models.internal import ContractABI
    from nethermind.entro.database.readers.internal import query_abis

    rich_console = Console()
    if not root_logger.hasHandlers():
        root_logger.addHandler(RichHandler(show_path=False, console=rich_console))
        root_logger.setLevel(logging.WARNING)

    db_session = create_cli_session(db_url)
    loaded_abis = query_abis(db_session)

    rich_console.print(
        f"Attempting to add ABI {abi_name} to Decoder with priority {priority}.  Checking for "
        f"conflicts with {len(loaded_abis)} existing ABIs"
    )

    add_abi_dict = json.loads(abi_json.read())

    dispatcher = DecodingDispatcher()

    # These ABIs have already been verified and added to DB
    for existing_abi in loaded_abis:
        dispatcher.add_abi(
            existing_abi.abi_name,
            json.loads(existing_abi.abi_json) if isinstance(existing_abi.abi_json, str) else existing_abi.abi_json,
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

    rich_console.print(f"[green]Successfully Added {abi_name} to Database with Priority {priority}")


@decoding_group.command()
@group_options(db_url_option)
def list_abis(db_url):
    """Lists all available ABIs that can be used for classification"""
    from nethermind.entro.database.readers.internal import query_abis

    if not root_logger.hasHandlers():
        root_logger.addHandler(RichHandler(show_path=False))
        root_logger.setLevel(logging.WARNING)

    db_session = create_cli_session(db_url)
    abis = query_abis(db_session)
    longest_abi_name = max(len(abi.abi_name) for abi in abis)
    click.echo("  ABI Name" + " " * (longest_abi_name - 4) + "Priority")
    click.echo_via_pager(
        f"\t{abi.abi_name} {'-' * (longest_abi_name - len(abi.abi_name) + 2)}> {abi.priority}\n" for abi in abis
    )


@decoding_group.command()
@click.option("--full-signatures", is_flag=True, default=False)
@group_options(db_url_option)
def list_abi_decoders(db_url, full_signatures):
    """Lists all Available ABIs in Database, along with the function and event signatures each ABI will classify"""
    if not root_logger.hasHandlers():
        root_logger.addHandler(RichHandler(show_path=False))
        root_logger.setLevel(logging.WARNING)

    db_session = create_cli_session(db_url)
    decoder = DecodingDispatcher.from_database(classify_abis=[], db_session=db_session, all_abis=True)
    console = Console()

    console.print(decoder.decoder_table(full_signatures=full_signatures))
