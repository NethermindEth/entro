import datetime
import json
import os
from dataclasses import asdict
from typing import Any

import click.utils
from sqlalchemy.orm import Session

from nethermind.entro.database.models.internal import ContractABI
from nethermind.entro.types.backfill import BlockTimestamp, SupportedNetwork

from .utils import model_to_dict


def write_abi(abi: ContractABI, db_session: Session | None):
    if db_session:
        db_session.add(abi)
        db_session.commit()
    else:
        if not os.path.exists(app_dir := click.utils.get_app_dir("entro")):
            os.mkdir(app_dir)

        if os.path.exists(contract_path := os.path.join(app_dir, "contract-abis.json")):
            with open(contract_path := os.path.join(app_dir, "contract-abis.json"), "rt") as abi_file:
                if os.path.getsize(contract_path) == 0:
                    abi_json = []
                else:
                    abi_json: list[dict[str, Any]] = json.load(abi_file)
        else:
            abi_json = []

        # TODO: Clean this up & Add better error handling.  A ^C in this block could corrupt stored ABIs...

        abi_json.append(model_to_dict(abi))

        with open(contract_path, "wt") as abi_file:
            json.dump(abi_json, abi_file)


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
                timestamp_json = []
            else:
                timestamp_json: list[dict[str, Any]] = json.load(timestamp_file)
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
