import datetime
import json
import logging
import os
from dataclasses import asdict
from typing import Any, Literal

import click.utils
from sqlalchemy.orm import Session

from nethermind.entro.database.models.internal import ContractABI
from nethermind.entro.types.backfill import BlockTimestamp, SupportedNetwork

from .utils import model_to_dict

logger = logging.getLogger("nethermind").getChild("entro").getChild("caching")


def write_abi(abi: ContractABI, db_session: Session | None):
    """
    Writes a ContractABI model to the datastore.  If a db_session is supplied, writes to the DB, otherwise,
    caches to a file in the default app directory for the given OS
    """

    if db_session:
        db_session.add(abi)
        db_session.commit()
    else:
        if not os.path.exists(app_dir := click.utils.get_app_dir("entro")):
            os.mkdir(app_dir)

        if os.path.exists(contract_path := os.path.join(app_dir, "contract-abis.json")):
            with open(contract_path := os.path.join(app_dir, "contract-abis.json"), "rt") as abi_file:
                if os.path.getsize(contract_path) == 0:
                    abi_json: list[dict[str, Any]] = []
                else:
                    abi_json = json.load(abi_file)
        else:
            abi_json = []

        # TODO: Clean this up & Add better error handling.  A ^C in this block could corrupt stored ABIs...

        abi_json.append(model_to_dict(abi))

        with open(contract_path, "wt") as abi_file:
            json.dump(abi_json, abi_file)


def delete_abi(abi_name: str, db_session: Session | None, decoder_os: Literal["EVM", "Cairo"] = "EVM"):
    if db_session:
        logger.info("Running DB Query to Delete ABI")
        db_session.query(ContractABI).filter(
            ContractABI.abi_name == abi_name, ContractABI.decoder_os == decoder_os
        ).delete()
        db_session.commit()

    else:
        if not os.path.exists(app_dir := click.utils.get_app_dir("entro")):
            os.mkdir(app_dir)
            logger.info("Application Directory Not Yet Created...  Cannot Delete ABI")
            return

        if not os.path.exists(os.path.join(app_dir, "contract-abis.json")):
            logger.info("ABI File does not exist... No ABIs to delete")
            return

        with open(contract_path := os.path.join(app_dir, "contract-abis.json"), "rt") as abi_file:
            if os.path.getsize(contract_path) == 0:
                logger.info("ABI File is empty... No ABIs to delete")
            else:
                abi_json = json.load(abi_file)

            contract_abis = [ContractABI(**abi) for abi in abi_json]

        if any(abi.abi_name == abi_name and abi.decoder_os == decoder_os for abi in contract_abis):
            logger.info("ABI Found... Deleting from File Cache")
            updated_abis = [
                model_to_dict(abi)
                for abi in contract_abis
                if not (abi.abi_name == abi_name and abi.decoder_os == decoder_os)
            ]

            with open(contract_path, "wt") as abi_file:
                json.dump(updated_abis, abi_file)

            logger.info("ABI Cache Updated")
        else:
            logger.info("ABI Not Found in Cache... No Deletion Necessary")


def write_block_timestamps(
    timestamps: list[BlockTimestamp],
    network: SupportedNetwork,
):
    """
    Writes block timestamps to timestamp file if DB is not being used
    """

    if not os.path.exists(app_dir := click.utils.get_app_dir("entro")):
        os.mkdir(app_dir)

    if os.path.exists(file_path := os.path.join(app_dir, f"{network.name}-timestamps.json")):
        with open(file_path, "rt") as timestamp_file:
            if os.path.getsize(file_path) == 0:
                timestamp_json: list[dict[str, Any]] = []
            else:
                timestamp_json = json.load(timestamp_file)
    else:
        timestamp_json = []

    existing_timestamps = [
        BlockTimestamp(block_number=t["block_number"], timestamp=datetime.datetime.fromisoformat(t["timestamp"]))
        for t in timestamp_json
    ]

    existing_blocks = {t.block_number for t in existing_timestamps}
    existing_timestamps.extend([t for t in timestamps if t.block_number not in existing_blocks])

    dataclass_dicts = [asdict(t) for t in existing_timestamps]
    for t in dataclass_dicts:
        t["timestamp"] = t["timestamp"].isoformat()

    with open(file_path, "wt") as timestamp_file:
        json.dump(dataclass_dicts, timestamp_file)
