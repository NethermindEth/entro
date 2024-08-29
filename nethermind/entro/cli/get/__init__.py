import click

from .starknet import starknet_group


@click.group()
def get_group():
    """Utilities for Fetching Data from RPC Node"""


get_group.add_command(starknet_group)
