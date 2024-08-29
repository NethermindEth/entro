import json

from nethermind.entro.types.backfill import Dataclass
from nethermind.idealis.utils import to_bytes


class HexEnabledJsonEncoder(json.JSONEncoder):
    """JSON Encoder that converts bytes to hex"""

    def default(self, o):
        if isinstance(o, bytes):
            return o.hex()
        return json.JSONEncoder.default(self, o)


def dataclass_to_json(obj):
    """Converts a dataclass to json"""
    return json.dumps(obj.__dict__, cls=HexEnabledJsonEncoder, indent=4)


def json_to_dataclass(json_str, cls):
    """Converts json to a dataclass"""
    return cls(**json.loads(json_str))


def get_transaction_hash_for_dataclass(dataclass: Dataclass) -> bytes | None:
    """Returns the transaction hash for a dataclass"""

    if hasattr(dataclass, "transaction_hash"):
        return to_bytes(getattr(dataclass, "transaction_hash"), pad=32)

    if hasattr(dataclass, "tx_hash"):
        return to_bytes(getattr(dataclass, "tx_hash"), pad=32)

    if hasattr(dataclass, "hash"):
        return to_bytes(getattr(dataclass, "hash"), pad=32)

    return None


def get_block_number_for_dataclass(dataclass: Dataclass) -> int | None:
    """Returns the block number for a dataclass"""

    if hasattr(dataclass, "block_number"):
        return int(getattr(dataclass, "block_number"))

    if hasattr(dataclass, "block"):
        return int(getattr(dataclass, "block"))

    if hasattr(dataclass, "number"):
        return int(getattr(dataclass, "number"))

    return None
