import click


@click.command(name="list")
def list_command():
    """List all tokens in the database"""


@click.command()
def add():
    """Add a token to the database"""


@click.group("tokens", short_help="Utilities for ERC Tokens")
def tokens_group():
    """
    Provides utilities for interacting with ERC standard tokens and performing
    queries and anayltics.

    """


tokens_group.add_command(list_command)
tokens_group.add_command(add)
