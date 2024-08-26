import logging

import click

from .utils import (
    batch_size_option,
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

# isort: skip_file
# pylint: disable=too-many-arguments,import-outside-toplevel,too-many-locals


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
    from nethermind.entro.cli.utils import cli_logger_config, create_cli_session
    from nethermind.entro.backfill.prices.get_prices import cli_download_pool_creations

    console = cli_logger_config(root_logger)

    db_session = create_cli_session(db_url)

    cli_download_pool_creations(console, db_session, json_rpc)


@prices_group.command(name="list")
@group_options(
    db_url_option,
)
def list_command(
    db_url: str,
):
    """List backfilled prices & ranges in database"""
    from nethermind.entro.cli.utils import cli_logger_config, create_cli_session

    console = cli_logger_config(root_logger)

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

    from nethermind.entro.cli.utils import cli_logger_config, create_cli_session

    console = cli_logger_config(root_logger)

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
    from_block,
    to_block,
    **kwargs,
):
    """
    Backfill prices for a given token
    """
    from nethermind.entro.cli.utils import cli_logger_config, create_cli_session

    console = cli_logger_config(root_logger)
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
    from_block,
    to_block,
    **kwargs,
):
    from nethermind.entro.cli.utils import cli_logger_config, create_cli_session

    console = cli_logger_config(root_logger)

    db_session = create_cli_session(db_url)
