import logging

import click
from rich.console import Console
from rich.logging import RichHandler

from nethermind.entro.backfill.prices import download_pool_creations

from ..types import BlockIdentifier
from .utils import (
    batch_size_option,
    create_cli_session,
    db_url_option,
    from_block_option,
    group_options,
    json_rpc_option,
    max_concurrency_option,
    to_block_option,
    token_address_option,
)

root_logger = logging.getLogger("nethermind")
logger = root_logger.getChild("entro").getChild("prices")


@click.group("prices", short_help="Backfill ERC20 Token Prices")
def prices_group():
    """
    Generating ERC20 pricing data & analytics`
    """


@prices_group.command()
@group_options(db_url_option, json_rpc_option)
def initialize(
    db_url: str,
    json_rpc: str,
):
    """
    Initialize the pricing oracle, backfilling Pool Cretaion events & allowing pricing
    oracle to compute ERC20 prices from onchain events
    """
    db_session = create_cli_session(db_url)

    download_pool_creations(db_session=db_session, json_rpc=json_rpc)


@prices_group.command(name="list")
@group_options(
    db_url_option,
)
def list_command(
    db_url: str,
):
    """List backfilled prices & ranges in database"""

    db_session = create_cli_session(db_url)


@prices_group.command()
@group_options(db_url_option, json_rpc_option)
def update(
    db_url: str,
    json_rpc: str,
):
    """
    Update the prices currently stored in the database to the latest block number
    """

    db_session = create_cli_session(db_url)


@prices_group.command()
@group_options(
    db_url_option,
    json_rpc_option,
    token_address_option,
    from_block_option,
    to_block_option,
    token_address_option,
    max_concurrency_option,
    batch_size_option,
)
def backfill(
    db_url: str,
    json_rpc: str,
    token_address: str,
    from_block: BlockIdentifier,
    to_block: BlockIdentifier,
    **kwargs,
):
    """
    Backfill prices for a given token
    """
    rich_console = Console()
    if not package_logger.hasHandlers():
        package_logger.addHandler(RichHandler(show_path=False, console=rich_console))
        package_logger.setLevel(logging.WARNING)

    db_session = create_cli_session(db_url)


@prices_group.command()
@group_options(
    db_url_option,
    json_rpc_option,
    from_block_option,
    to_block_option,
    max_concurrency_option,
    batch_size_option,
)
def backfill_eth_price(
    db_url: str,
    json_rpc: str,
    from_block: BlockIdentifier,
    to_block: BlockIdentifier,
    **kwargs,
):
    rich_console = Console()
    if not package_logger.hasHandlers():
        package_logger.addHandler(RichHandler(show_path=False, console=rich_console))
        package_logger.setLevel(logging.WARNING)

    db_session = create_cli_session(db_url)
