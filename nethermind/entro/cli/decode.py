import logging
from typing import Literal

import click


from nethermind.entro.cli.utils import (
    db_url_option,
    group_options,
    json_rpc_option,
)

# isort: skip_file
# pylint: disable=too-many-arguments,import-outside-toplevel,too-many-locals

root_logger = logging.getLogger("nethermind")
logger = root_logger.getChild("entro").getChild("backfill")


@click.group("decode", short_help="ABI Decoding & Event Classification")
def decode_group():
    """ABI Decoding & Event Classification"""


# TODO: Fix DRY betweem add-abi & add-class


@decode_group.command()
@group_options(db_url_option)
@click.argument("abi_name")
@click.argument("abi_json", type=click.File("r"))
@click.option("--priority", type=int, default=0)
def add_abi(db_url: str | None, abi_name: str, abi_json, priority: int):
    """Adds an ABI to the database"""

    import json
    from nethermind.entro.cli.utils import cli_logger_config, create_cli_session
    from nethermind.entro.database.readers.internal import get_abis
    from nethermind.entro.database.writers.internal import write_abi
    from nethermind.entro.database.models.internal import ContractABI
    from nethermind.entro.exceptions import DecodingError
    from nethermind.entro.decoding import DecodingDispatcher

    console = cli_logger_config(root_logger)
    root_logger.setLevel(logging.WARNING)

    db_session = create_cli_session(db_url) if db_url else None
    loaded_abis = get_abis(db_session)

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
            json.loads(existing_abi.abi_json) if isinstance(existing_abi.abi_json, str) else existing_abi.abi_json,
            existing_abi.priority,
        )

    try:
        dispatcher.add_abi(abi_name, add_abi_dict, priority)
    except DecodingError as e:
        logger.error(e)
        return

    write_abi(ContractABI(abi_name=abi_name, abi_json=add_abi_dict, priority=priority, decoder_os="EVM"), db_session)
    if db_session:
        db_session.close()

    console.print(f"[green]Successfully Added {abi_name} to Database with Priority {priority}")


@decode_group.command()
@group_options(db_url_option, json_rpc_option)
@click.argument("abi_name")
@click.argument("class_hash")
@click.option("--priority", type=int, default=0)
def add_class(db_url: str | None, json_rpc: str, abi_name: str, class_hash: str, priority: int):
    """Add a StarkNet Class to the Decoder"""
    import json
    from nethermind.entro.cli.utils import cli_logger_config, create_cli_session
    from nethermind.idealis.utils.starknet.decode import get_parsed_abi_json
    from nethermind.entro.database.readers.internal import get_abis
    from nethermind.entro.database.writers.internal import write_abi
    from nethermind.entro.database.models.internal import ContractABI
    from nethermind.entro.decoding import DecodingDispatcher
    from nethermind.entro.exceptions import DecodingError

    console = cli_logger_config(root_logger)
    root_logger.setLevel(logging.WARNING)

    db_session = create_cli_session(db_url) if db_url else None
    loaded_abis = get_abis(db_session, decoder_os="Cairo")

    console.print(
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

    write_abi(
        ContractABI(abi_name=abi_name, abi_json=starknet_class_abi, priority=priority, decoder_os="Cairo"), db_session
    )
    if db_session:
        db_session.close()

    console.print(f"[green]Successfully Added {abi_name} to Database with Priority {priority}")


@decode_group.command()
@group_options(db_url_option)
def list_abis(db_url: str | None):
    """Lists all available ABIs that can be used for classification"""
    from rich.panel import Panel
    from rich.table import Table
    from nethermind.entro.cli.utils import cli_logger_config, create_cli_session
    from nethermind.entro.database.readers.internal import get_abis

    console = cli_logger_config(root_logger)

    db_session = create_cli_session(db_url) if db_url else None
    evm_abis = sorted(get_abis(db_session), key=lambda x: x.priority, reverse=True)
    starknet_abis = sorted(get_abis(db_session, decoder_os="Cairo"), key=lambda x: x.priority, reverse=True)

    if db_session:
        db_session.close()

    if len(evm_abis):
        evm_table = Table(box=None)
        evm_table.add_column("ABI Name", style="bold")
        evm_table.add_column("Priority")
        for abi in evm_abis:
            evm_table.add_row(abi.abi_name, str(abi.priority))

        console.print(Panel("-- EVM ABIs --", width=40))
        console.print(evm_table)

    if len(starknet_abis):
        cairo_table = Table(box=None)
        cairo_table.add_column("ABI Name", style="bold")
        cairo_table.add_column("Priority")
        for abi in starknet_abis:
            cairo_table.add_row(abi.abi_name, str(abi.priority))

        console.print(Panel("-- Cairo ABIs --", width=40))
        console.print(cairo_table)


@decode_group.command()
@click.argument("decoder_type", type=click.Choice(["EVM", "Cairo"]))
@click.option("--full-signatures", is_flag=True, default=False)
@group_options(db_url_option)
def list_abi_decoders(decoder_type, db_url, full_signatures):
    """Lists all Available ABIs in Database, along with the function and event signatures each ABI will classify"""
    from nethermind.entro.cli.utils import cli_logger_config, create_cli_session
    from nethermind.entro.decoding import DecodingDispatcher

    console = cli_logger_config(root_logger)
    root_logger.setLevel(logging.WARNING)

    db_session = create_cli_session(db_url) if db_url else None

    decoder = DecodingDispatcher.from_cache(
        classify_abis=[], db_session=db_session, decoder_os=decoder_type, all_abis=True
    )

    if decoder.loaded_abis:
        console.print(decoder.decoder_table(full_signatures=full_signatures))


@decode_group.command()
@group_options(db_url_option)
@click.argument("abi_name")
@click.argument("decoder_type", type=click.Choice(["EVM", "Cairo"]))
def delete_abi(abi_name: str, decoder_type: Literal["EVM", "Cairo"], db_url: str | None):
    """Deletes an ABI from the data cache"""
    from nethermind.entro.cli.utils import cli_logger_config, create_cli_session
    from nethermind.entro.database.writers.internal import delete_abi

    cli_logger_config(root_logger)

    db_session = create_cli_session(db_url) if db_url else None

    delete_abi(abi_name, db_session, decoder_type)

    if db_session:
        db_session.close()
