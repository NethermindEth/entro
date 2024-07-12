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

    if "transaction_hash" in dataclass:
        return to_bytes(dataclass.transaction_hash, pad=32)

    if "tx_hash" in dataclass:
        return to_bytes(dataclass.tx_hash, pad=32)

    if "hash" in dataclass:  # Iffy...
        return to_bytes(dataclass.hash, pad=32)

    return None


def get_block_number_for_dataclass(dataclass: Dataclass) -> int | None:
    """Returns the block number for a dataclass"""

    if "block_number" in dataclass:
        return int(dataclass.block_number)

    if "block" in dataclass:
        return int(dataclass.block)

    if "number" in dataclass:
        return int(dataclass.number)

    return None
