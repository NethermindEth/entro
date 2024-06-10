import json


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
