import json
import os
from typing import Any

from click.utils import get_app_dir
from sqlalchemy.orm import Session

from nethermind.entro.database.models.internal import ContractABI

from .utils import model_to_dict


def write_abi(abi: ContractABI, db_session: Session | None):
    if db_session:
        db_session.add(abi)
        db_session.commit()
    else:
        if not os.path.exists(app_dir := get_app_dir("entro")):
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
