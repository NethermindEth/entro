import logging
import os

import click
from rich.progress import (
    BarColumn,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from python_eth_amm.types.backfill import DataSources, SupportedNetwork

package_logger = logging.getLogger("python_eth_amm")
logger = package_logger.getChild("cli")


progress_defaults = [
    TextColumn("[progress.description]{task.description}"),
    SpinnerColumn(),
    BarColumn(),
    TaskProgressColumn(),
    TimeElapsedColumn(),
    TimeRemainingColumn(),
    TextColumn("[green]Blocks Searched: {task.completed}/{task.total}"),
    TextColumn(
        "[magenta]Searching Block: {task.fields[searching_block]}", justify="right"
    ),
]


def group_options(*options):
    """Decorator to group multiple click options together"""

    def wrapper(function):
        for option in reversed(options):
            function = option(function)
        return function

    return wrapper


# -------------------------------------------------------
#    CLI Secrets, Connections, and Configurations
# -------------------------------------------------------
json_rpc_option = click.option(
    "--json-rpc",
    "-rpc",
    "json_rpc",
    default=os.environ.get("JSON_RPC", "http://localhost:8545"),
    help="JSONRPC URL to use for backfilling.  If not provided, will use the JSON_RPC environment variable",
)
db_url_option = click.option(
    "--db-url",
    "-db",
    "db_url",
    default=os.environ.get("DB_URL"),
    help="SQLAlchemy DB URL to use for backfilling.  If not provided, will use the DB_URL environment variable",
)

api_key_option = click.option(
    "--api-key",
    "api_key",
    default=os.environ.get("API_KEY"),
    help="API key if using centralized APIs as a data source",
)


# -------------------------------------------------------
#    Required Parameters as Option Flag
# -------------------------------------------------------
network_option = click.option(
    "--network",
    "-n",
    "network",
    type=click.Choice(list(SupportedNetwork.__members__.keys())),
    default="ethereum",
    show_default=True,
    help="Specify the network to backfill",
)
source_option = click.option(
    "--source",
    "source",
    type=click.Choice(list(DataSources.__members__.keys())),
    default="json_rpc",
    show_default=True,
    help="Datasource for backfill.",
)
from_block_option = click.option(
    "--from-block",
    "-from",
    "from_block",
    default="earliest",
    type=str,
    show_default=True,
    help="Start block for backfill. Can be an integer, or a block identifier string like 'earliest'",
)
to_block_option = click.option(
    "--to-block",
    "-to",
    "to_block",
    default="latest",
    type=str,
    show_default=True,
    help="End block for backfill. Can be an integer, or a block identifier string like 'pending'",
)


# -------------------------------------------------------
#    Backfill Filter Parameters
# -------------------------------------------------------

from_address_option = click.option(
    "--from-address",
    help="Address to filter by.  If not provided, will not filter by address.",
)
to_address_option = click.option(
    "--to-address",
    help="Filter by address",
)
for_address_option = click.option(
    "--for-address",
    help="Filters records To and From an address.  Equivalent to setting both "
    "--from-address and --to-address filters to the same address.",
)

event_name_option = click.option(
    "--event-name",
    "-e",
    "event_names",
    type=str,
    multiple=True,
    help="Event name for event/log backfills.  Can be input multiple times.  If not provided, will backfill "
    "all events present in contract-abi",
)
# -------------------------------------------------------
#    Backfill Configuration Parameters
# -------------------------------------------------------

decode_abis_option = click.option(
    "--decode_abis",
    "-abi",
    "decode_abis",
    multiple=True,
    help="Names of ABIs to use for Decoding.  To view available ABIs, run `python-eth-amm list-abis`"
    "ABIs can be added to the database using `python-eth-amm add-abi`",
)
batch_size_option = click.option(
    "--batch-size",
    "batch_size",
    type=int,
    default=None,
    show_default=True,
    help="Batch size to use for query.  When querying an API, the batch is usually the page size. "
    "For JSON RPC calls, the batch size is the number of blocks each query will cover.",
)
page_size_option = click.option(
    "--page-size",
    "page_size",
    type=int,
    default=None,
    help="Page size to use for API queries",
)


max_concurrency_option = click.option(
    "--max-concurrency",
    "max_concurrency",
    type=int,
    default=None,
    help="Maximum number of concurrent async requests to make to the API or RPC Server",
)
overwrite_db_records_option = click.option(
    "--overwrite-db-records",
    is_flag=True,
    default=None,
    help="Whether to overwrite existing database Records when performing backfill.",
)
contract_address_option = click.option(
    "--contract-address",
    "-addr",
    "contract_address",
    type=str,
    required=True,
    help="Contract address for event/log backfills",
)
all_abis_option = click.option(
    "--all-abis",
    is_flag=True,
    default=None,
    help="If provided, will use all ABIs present in the database for classification",
)


def create_cli_session(db_url: str) -> Session:
    """Creates a new database session"""

    if db_url is None:
        logger.error(
            "Database URL not specified... Set with '--db-url' option or 'DB_URL' environment variable"
        )
        raise SystemExit(1)

    engine = create_engine(db_url)
    return sessionmaker(bind=engine)()