import click
from sqlalchemy import create_engine

from nethermind.entro.cli.backfill import backfill_group
from nethermind.entro.cli.decode import decode_group
from nethermind.entro.cli.get import get_group
from nethermind.entro.cli.prices import prices_group
from nethermind.entro.cli.tokens import tokens_group
from nethermind.entro.cli.utils import db_url_option, group_options
from nethermind.entro.database.migrations import migrate_up


@click.group()
def entro_cli():
    """Command Line Interface for Nethermind Entro"""


@entro_cli.command(name="migrate-up")
@group_options(db_url_option)
def cli_migrate_up(db_url):
    """
    Migrate DB Tables to Latest Version
    """
    db_engine = create_engine(db_url)
    click.echo("Starting Database Migrations")

    migrate_up(db_engine)

    click.echo("Database Migration Complete")


# Adding Command Groups
entro_cli.add_command(tokens_group, name="tokens")
entro_cli.add_command(backfill_group, name="backfill")
entro_cli.add_command(prices_group, name="prices")
entro_cli.add_command(decode_group, name="decode")
entro_cli.add_command(get_group, name="get")
