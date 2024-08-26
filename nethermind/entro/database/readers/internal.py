import datetime
import json
import os
from typing import Any, Literal, Sequence

import click.utils
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from nethermind.entro.database.models.base import AbstractBlock
from nethermind.entro.database.models import block_model_for_network
from nethermind.entro.database.models.internal import BackfilledRange, ContractABI
from nethermind.entro.types.backfill import BackfillDataType as BDT
from nethermind.entro.types.backfill import BlockTimestamp, SupportedNetwork

from .utils import execute_scalars_query


def fetch_backfills_by_datatype(
    db_session: Session,
    data_type: BDT,
    network: SupportedNetwork,
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
    db_session: Session | None,
    abi_names: list[str] | None = None,
    decoder_os: Literal["EVM", "Cairo"] = "EVM",
) -> list[ContractABI]:
    """
    Queries the database for the contract ABIs to use for decoding events.  If abi_names is None, then all ABIs are
    returned.

    :param db_session:
    :param abi_names:
    :param decoder_os:
    :return:
    """

    if db_session:
        query = (
            select(ContractABI)  # type: ignore
            .filter(
                and_(
                    ContractABI.abi_name.in_(abi_names) if abi_names else ContractABI.abi_name != None,
                    ContractABI.decoder_os == decoder_os,
                )
            )
            .order_by(ContractABI.priority.desc(), ContractABI.abi_name)
        )

        return execute_scalars_query(db_session, query)

    if not os.path.exists(app_dir := click.utils.get_app_dir("entro")):
        os.mkdir(app_dir)

    if not os.path.exists(os.path.join(app_dir, "contract-abis.json")):
        return []

    with open(contract_path := os.path.join(app_dir, "contract-abis.json"), "rt") as abi_file:
        if os.path.getsize(contract_path) == 0:
            abi_json: list[dict[str, Any]] = []
        else:
            abi_json = json.load(abi_file)

        contract_abis = [ContractABI(**abi) for abi in abi_json]

        if abi_names:
            return [abi for abi in contract_abis if abi.abi_name in abi_names if abi.decoder_os == decoder_os]

        return [abi for abi in contract_abis if abi.decoder_os == decoder_os]


def first_block_timestamp(network: SupportedNetwork) -> datetime.datetime:
    """Returns the first block timestamp for a given network"""
    match network:
        case SupportedNetwork.ethereum:
            # Thursday, July 30, 2015 3:26:28 PM
            return datetime.datetime(2015, 7, 30, 15, 26, 28, tzinfo=datetime.timezone.utc)
        case SupportedNetwork.starknet:
            # Tuesday, November 16, 2021 1:24:08 PM
            return datetime.datetime(2021, 11, 16, 13, 24, 8, tzinfo=datetime.timezone.utc)
        case _:
            raise ValueError(f"Cannot fetch Initial Block Time for Network: {network}")


def get_block_timestamps(
    db_session: Session | None,
    network: SupportedNetwork,
    resolution: int,
    from_block: int = 0,
) -> list[BlockTimestamp]:
    """
    Gets block timestamps from the database for a given network and resolution.

    :param db_session: Database session
    :param network: Network to get timestamps for
    :param resolution: Resolution of timestamps
    :param from_block: Inclusive Block number to search from
    :return: List of BlockTimestamps
    """

    if db_session:
        network_block: AbstractBlock = block_model_for_network(network)  # type: ignore
        select_stmt = (
            select(network_block.block_number, network_block.timestamp)  # type: ignore
            .filter(
                network_block.block_number % resolution == 0,
                network_block.block_number >= from_block,
            )
            .order_by(network_block.block_number)  # type: ignore
        )
        return [
            BlockTimestamp(
                block_number=row[0],
                timestamp=(
                    datetime.datetime.fromtimestamp(row[1], tz=datetime.timezone.utc)
                    if row[0] != 0
                    else first_block_timestamp(network)
                ),
            )
            for row in db_session.execute(select_stmt).all()
        ]

    # TODO: Fix dry and messy file handling
    if not os.path.exists(app_dir := click.utils.get_app_dir("entro")):
        os.mkdir(app_dir)

    if not os.path.exists(file_path := os.path.join(app_dir, f"{network.name}-timestamps.json")):
        return []

    with open(file_path, "rt") as timestamp_file:
        if os.path.getsize(file_path) != 0:
            timestamp_json: list[dict[str, Any]] = json.load(timestamp_file)
        else:
            timestamp_json = []

        timestamps = [
            BlockTimestamp(
                block_number=t["block_number"],
                timestamp=datetime.datetime.fromisoformat(t["timestamp"]),
            )
            for t in timestamp_json
        ]

        filtered_timestamps = [t for t in timestamps if t.block_number % resolution == 0]
        return sorted(filtered_timestamps, key=lambda t: t.block_number)
