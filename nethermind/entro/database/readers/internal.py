import json
import os
from typing import Any, Literal, Sequence

from click.utils import get_app_dir
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from nethermind.entro.database.models.internal import BackfilledRange, ContractABI
from nethermind.entro.types.backfill import BackfillDataType as BDT
from nethermind.entro.types.backfill import SupportedNetwork as SN

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
        BackfilledRange.backfill_id.in_(backfill_id if isinstance(backfill_id, list) else [backfill_id])
    )
    return db_session.scalars(select_stmt).all()


# pylint: disable=singleton-comparison
def get_abis(
    db_session: Session | None, abi_names: list[str] | None = None, decoder_os: Literal["EVM", "Cairo"] = "EVM"
) -> list[ContractABI]:
    """
    Queries the database for the contract ABIs to use for decoding events.  If abi_names is None, then all ABIs are
    returned.

    :param db_session:
    :param abi_names:
    :param os:
    :return:
    """

    if db_session:
        query = (
            select(ContractABI)  # type: ignore
            .filter(
                and_(
                    ContractABI.abi_name.in_(abi_names) if abi_names else ContractABI.abi_name != None,
                    ContractABI.os == decoder_os,
                )
            )
            .order_by(ContractABI.priority.desc(), ContractABI.abi_name)
        )

        return execute_scalars_query(db_session, query)

    if not os.path.exists(app_dir := get_app_dir("entro")):
        os.mkdir(app_dir)

    if not os.path.exists(os.path.join(app_dir, "contract-abis.json")):
        return []

    with open(contract_path := os.path.join(app_dir, "contract-abis.json"), "rt") as abi_file:
        if os.path.getsize(contract_path) == 0:
            abi_json = []
        else:
            abi_json: list[dict[str, Any]] = json.load(abi_file)

        contract_abis = [ContractABI(**abi) for abi in abi_json]

        if abi_names:
            return [abi for abi in contract_abis if abi.abi_name in abi_names if abi.os == decoder_os]

        return [abi for abi in contract_abis if abi.os == decoder_os]
