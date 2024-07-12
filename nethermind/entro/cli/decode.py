import json
import logging

import click

from rich.logging import RichHandler
from rich.console import Console

from nethermind.entro.database.readers.internal import get_abis
from nethermind.entro.database.writers.internal import write_abi
from nethermind.entro.database.models.internal import ContractABI, BackfilledRange

from nethermind.entro.exceptions import DecodingError
from nethermind.entro.decoding import DecodingDispatcher


from nethermind.entro.cli.utils import (
    db_url_option,
    group_options,
    create_cli_session,
    json_rpc_option,
)

# isort: skip_file
# pylint: disable=too-many-arguments,raise-missing-from,import-outside-toplevel,too-many-locals

root_logger = logging.getLogger("nethermind")
logger = root_logger.getChild("entro").getChild("backfill")


@click.group("decode", short_help="ABI Decoding & Event Classification")
def decode_group():
    pass


# TODO: Fix DRY betweem add-abi & add-class


@decode_group.command()
@group_options(db_url_option)
@click.argument("abi_name")
@click.argument("abi_json", type=click.File("r"))
@click.option("--priority", type=int, default=0)
def add_abi(db_url: str | None, abi_name: str, abi_json, priority: int):
    """Adds an ABI to the database"""

    rich_console = Console()
    if not root_logger.hasHandlers():
        root_logger.addHandler(RichHandler(show_path=False, console=rich_console))
        root_logger.setLevel(logging.WARNING)

    db_session = create_cli_session(db_url) if db_url else None
    loaded_abis = get_abis(db_session)

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

    write_abi(ContractABI(abi_name=abi_name, abi_json=add_abi_dict, priority=priority, os="EVM"), db_session)

    rich_console.print(f"[green]Successfully Added {abi_name} to Database with Priority {priority}")


@decode_group.command()
@group_options(db_url_option, json_rpc_option)
@click.argument("abi_name")
@click.argument("class_hash")
@click.option("--priority", type=int, default=0)
def add_class(db_url: str | None, json_rpc: str, abi_name: str, class_hash: str, priority: int):
    from nethermind.idealis.utils.starknet.decode import get_parsed_abi_json

    rich_console = Console()
    if not root_logger.hasHandlers():
        root_logger.addHandler(RichHandler(show_path=False, console=rich_console))
        root_logger.setLevel(logging.INFO)

    db_session = create_cli_session(db_url) if db_url else None
    loaded_abis = get_abis(db_session, decoder_os="Cairo")

    rich_console.print(
        f"Attempting to add StarkNet Class {class_hash} to Decoder with priority {priority}.  Checking for "
        f"conflicts with {len(loaded_abis)} existing Decode Classes"
    )

    starknet_class_abi = get_parsed_abi_json(class_hash, json_rpc)

    if starknet_class_abi is None:
        return

    dispatcher = DecodingDispatcher(decoder_os="Cairo")

    for existing_abi in loaded_abis:
        dispatcher.add_abi(
            existing_abi.abi_name,
            json.loads(existing_abi.abi_json) if isinstance(existing_abi.abi_json, str) else existing_abi.abi_json,
            existing_abi.priority,
        )

    try:
        dispatcher.add_abi(abi_name, starknet_class_abi, priority)
    except DecodingError as e:
        logger.error(e)
        return

    write_abi(ContractABI(abi_name=abi_name, abi_json=starknet_class_abi, priority=priority, os="Cairo"), db_session)

    rich_console.print(f"[green]Successfully Added {abi_name} to Database with Priority {priority}")


@decode_group.command()
@group_options(db_url_option)
def list_abis(db_url: str | None):
    """Lists all available ABIs that can be used for classification"""

    # TODO: switch to rich output
    if not root_logger.hasHandlers():
        root_logger.addHandler(RichHandler(show_path=False))
        root_logger.setLevel(logging.WARNING)

    db_session = create_cli_session(db_url) if db_url else None
    evm_abis = get_abis(db_session)
    starknet_abis = get_abis(db_session, decoder_os="Cairo")
    longest_abi_name = max(len(abi.abi_name) for abi in evm_abis + starknet_abis)
    click.echo("  ABI Name" + " " * (longest_abi_name - 4) + "Priority")
    pager_text = [
        "-------- EVM ABIs -------\n",
        *[f"{abi.abi_name} {'-' * (longest_abi_name - len(abi.abi_name) + 2)}> {abi.priority}\n" for abi in evm_abis],
        "------- Cairo ABIs ------\n",
        *[
            f"{abi.abi_name} {'-' * (longest_abi_name - len(abi.abi_name) + 2)}> {abi.priority}\n"
            for abi in starknet_abis
        ],
    ]
    click.echo_via_pager(pager_text)


@decode_group.command()
@click.option("--full-signatures", is_flag=True, default=False)
@group_options(db_url_option)
def list_abi_decoders(db_url, full_signatures):
    """Lists all Available ABIs in Database, along with the function and event signatures each ABI will classify"""
    if not root_logger.hasHandlers():
        root_logger.addHandler(RichHandler(show_path=False))
        root_logger.setLevel(logging.WARNING)

    db_session = create_cli_session(db_url) if db_url else None

    console = Console()

    evm_decoder = DecodingDispatcher.from_abis(classify_abis=[], db_session=db_session, decoder_os="EVM", all_abis=True)
    cairo_decoder = DecodingDispatcher.from_abis(
        classify_abis=[], db_session=db_session, decoder_os="Cairo", all_abis=True
    )

    if len(evm_decoder.loaded_abis):
        console.print(evm_decoder.decoder_table(full_signatures=full_signatures))

    if len(cairo_decoder.loaded_abis):
        console.print(cairo_decoder.decoder_table(full_signatures=full_signatures))
