import click

from .ethereum import ethereum_group
from .starknet import starknet_group


@click.group()
def backfill_group():
    """Backfill blockchain data for Blockchain Networks"""


@backfill_group.command(name="list")
def list_backfills():
    """Lists all currently backfilled data in the database"""


# Backfill subcommands
backfill_group.add_command(ethereum_group)
backfill_group.add_command(starknet_group)
