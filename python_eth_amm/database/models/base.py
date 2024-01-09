from typing import Any

import click
import sqlalchemy
from sqlalchemy import JSON, Engine, MetaData, PrimaryKeyConstraint, Text, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from python_eth_amm.types.backfill import BackfillDataType, SupportedNetwork

from .utils import execute_scalars_query


class PythonETHAMMBase(DeclarativeBase):
    """Base class for utility tables"""

    metadata = MetaData(schema="python_eth_amm")


class ContractABI(PythonETHAMMBase):
    """
    Table for storing contract ABIs to use for decoding events.
    """

    __tablename__ = "contract_abis"

    abi_name: Mapped[str]
    abi_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    priority: Mapped[int]

    __table_args__ = (PrimaryKeyConstraint("abi_name"),)


class BackfilledRange(PythonETHAMMBase):
    """
    Table for storing backfill states.

    This table is used to track the ranges of blocks that have been backfilled for each data type.

    """

    __tablename__ = "backfilled_ranges"

    data_type: Mapped[BackfillDataType] = mapped_column(Text, nullable=False)
    network: Mapped[SupportedNetwork] = mapped_column(Text, nullable=False)
    start_block: Mapped[int]
    end_block: Mapped[int]

    filter_data: Mapped[dict[str, str | int] | None] = mapped_column(JSON)
    metadata_dict: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    decoded_abis: Mapped[list[str] | None] = mapped_column(JSON)

    __table_args__ = (
        PrimaryKeyConstraint("data_type", "network", "start_block", "end_block"),
    )


def migrate_config_tables(db_engine: Engine):
    """
    Migrates the config tables to the database.

    :param db_engine:
    :return:
    """
    conn = db_engine.connect()
    if not conn.dialect.has_schema(conn, "python_eth_amm"):
        click.echo("Creating schema python_eth_amm for config tables")
        conn.execute(sqlalchemy.schema.CreateSchema("python_eth_amm"))
        conn.commit()

    PythonETHAMMBase.metadata.create_all(bind=db_engine)


# pylint: disable=singleton-comparison
def query_abis(
    db_session: Session, abi_names: list[str] | None = None
) -> list[ContractABI]:
    """
    Queries the database for the contract ABIs to use for decoding events.  If abi_names is None, then all ABIs are
    returned.

    :param db_session:
    :param abi_names:
    :return:
    """
    query = (
        select(ContractABI)  # type: ignore
        .filter(
            ContractABI.abi_name.in_(abi_names)
            if abi_names
            else ContractABI.abi_name != None
        )
        .order_by(ContractABI.priority.desc(), ContractABI.abi_name)
    )

    return execute_scalars_query(db_session, query)
