from sqlalchemy import select
from sqlalchemy.orm import Session

from python_eth_amm.database.models.python_eth_amm import ContractABI

from .utils import execute_scalars_query


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
