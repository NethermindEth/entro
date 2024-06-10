import click

from sqlalchemy import create_engine

from nethermind.entro.cli.utils import group_options, db_url_option
from nethermind.entro.database.migrations import migrate_up
from nethermind.entro.cli.decoding import decoding_group
from nethermind.entro.cli.backfill import backfill_group
from nethermind.entro.cli.prices import prices_group
from nethermind.entro.cli.tokens import tokens_group


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
entro_cli.add_command(decoding_group, name="decoding")
