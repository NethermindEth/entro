import logging

import click
from rich.logging import RichHandler

from python_eth_amm.database.migrations import cli_migrate_up

from .backfill import add_abi, backfill_group, list_abi_decoders, list_abis
from .tokens import tokens_group


@click.group()
def cli_entry_point():
    """CLI for python-eth-amm"""
    logger = logging.getLogger("python_eth_amm")
    if not logger.hasHandlers():
        logger.addHandler(RichHandler(show_path=False))
        logger.setLevel(logging.WARNING)


# Adding Command Groups
cli_entry_point.add_command(tokens_group, name="tokens")
cli_entry_point.add_command(backfill_group, name="backfill")


# Adding Base Commands
cli_entry_point.add_command(add_abi)
cli_entry_point.add_command(list_abis)
cli_entry_point.add_command(list_abi_decoders)
cli_entry_point.add_command(cli_migrate_up)
