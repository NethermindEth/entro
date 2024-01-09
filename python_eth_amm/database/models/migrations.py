import click
from sqlalchemy import Engine, create_engine

from python_eth_amm.cli.utils import db_url_option, group_options

# pylint: disable=import-outside-toplevel


@click.command(name="migrate-up")
@group_options(db_url_option)
def cli_migrate_up(db_url):
    """Migrate the database to the latest version"""
    db_engine = create_engine(db_url)
    click.echo("Starting Database Migrations")

    migrate_up(db_engine)

    click.echo("Database Migration Complete")


def migrate_up(db_engine: Engine):
    """Create Sqlalchemy DB Tables"""
    from .base import migrate_config_tables
    from .ethereum import migrate_ethereum_tables
    from .polygon import migrate_polygon_tables
    from .prices import migrate_price_tables
    from .starknet import migrate_starknet_tables
    from .uniswap import migrate_uniswap_tables
    from .zk_sync import migrate_zk_sync_tables

    migrate_config_tables(db_engine)
    migrate_ethereum_tables(db_engine)
    migrate_polygon_tables(db_engine)
    migrate_price_tables(db_engine)
    migrate_starknet_tables(db_engine)
    migrate_uniswap_tables(db_engine)
    migrate_zk_sync_tables(db_engine)


def drop_all_tables(db_engine: Engine):
    """Drop all tables from the database"""
    from .base import PythonETHAMMBase
    from .ethereum import EthereumDataBase
    from .polygon import PolygonDataBase
    from .prices import PriceDataBase
    from .starknet import StarknetDataBase
    from .uniswap import UniswapBase
    from .zk_sync import ZKSyncDataBase

    EthereumDataBase.metadata.drop_all(db_engine)
    PolygonDataBase.metadata.drop_all(db_engine)
    PriceDataBase.metadata.drop_all(db_engine)
    PythonETHAMMBase.metadata.drop_all(db_engine)
    StarknetDataBase.metadata.drop_all(db_engine)
    UniswapBase.metadata.drop_all(db_engine)
    ZKSyncDataBase.metadata.drop_all(db_engine)
