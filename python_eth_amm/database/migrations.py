import click
from sqlalchemy import Engine, create_engine
from sqlalchemy.schema import CreateSchema

from python_eth_amm.cli.utils import db_url_option, group_options


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
    # pylint: disable=import-outside-toplevel,unused-import
    import python_eth_amm.database.models.ethereum
    import python_eth_amm.database.models.polygon
    import python_eth_amm.database.models.prices
    import python_eth_amm.database.models.python_eth_amm
    import python_eth_amm.database.models.starknet
    import python_eth_amm.database.models.uniswap
    import python_eth_amm.database.models.zk_sync

    from .models.base import Base

    # pylint: enable=import-outside-toplevel,unused-import

    schemas = {table.schema for table in Base.metadata.tables.values()}
    with db_engine.connect() as conn:
        for schema_name in schemas:
            conn.execute(CreateSchema(schema_name, if_not_exists=True))

        conn.commit()

    Base.metadata.create_all(bind=db_engine)
