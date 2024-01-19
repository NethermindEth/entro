from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from python_eth_amm.database.models.python_eth_amm import BackfilledRange, ContractABI
from python_eth_amm.types.backfill import BackfillDataType as BDT
from python_eth_amm.types.backfill import SupportedNetwork as SN

from .utils import execute_scalars_query


def fetch_backfills_by_datatype(
    db_session: Session,
    data_type: BDT,
    network: SN,
) -> Sequence[BackfilledRange]:
    """Selects ORM models of all backfills in DB matching the network & datatype"""
    select_stmt = (
        select(BackfilledRange)
        .where(
            BackfilledRange.data_type == data_type.value,
            BackfilledRange.network == network.value,
        )
        .order_by(BackfilledRange.start_block)  # type: ignore
    )
    return db_session.scalars(select_stmt).all()


def fetch_backfills_by_id(
    db_session: Session,
    backfill_id: str | list[str],
) -> Sequence[BackfilledRange]:
    """Fetches all existing backfills from the database"""
    select_stmt = select(BackfilledRange).where(
        BackfilledRange.backfill_id.in_(
            backfill_id if isinstance(backfill_id, list) else [backfill_id]
        )
    )
    return db_session.scalars(select_stmt).all()


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
