import logging
from typing import Any, Type

from hexbytes import HexBytes
from sqlalchemy import Connection, Engine, MetaData
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import DeclarativeBase

from python_eth_amm.exceptions import DatabaseError

package_logger = logging.getLogger("python_eth_amm")
database_logger = package_logger.getChild("db")
logger = database_logger.getChild("utils")


def model_to_dict(model) -> dict[str, Any]:
    """Converts a SQLAlchemy model to a dictionary"""
    return {c.name: getattr(model, c.name) for c in model.__table__.columns}


def db_encode_dict(data: Any) -> Any:
    """
    Recursively encodes a dictionary.  Converts all binary types to hexstrings that can be saved to the database
    in JSON columns.

    :param data:
    :return:
    """
    if isinstance(data, dict):
        return {k: db_encode_dict(v) for k, v in data.items()}

    if isinstance(data, (list, tuple)):
        return [db_encode_dict(d) for d in data]

    if isinstance(data, bytes):
        return "0x" + data.hex()

    return data


def db_encode_hex(data: str | HexBytes | bytes, db_dialect: str) -> str | bytes:
    """
    Encodes data to a hex string or bytes depending on the database dialect

    :param data: Hex data to encode
    :param db_dialect: current database dialect
    :return:
    """
    match db_dialect:
        case "postgresql":
            if isinstance(data, str):
                return bytes.fromhex(data[2:])
            if isinstance(data, bytes | HexBytes):
                return data
            raise ValueError(f"Invalid data type: {type(data)}")

        case _:
            if isinstance(data, str):
                return data if data[:2] == "0x" else "0x" + data
            if isinstance(data, bytes):
                return "0x" + data.hex()
            if isinstance(data, HexBytes):
                return data.hex()
            raise ValueError(f"Invalid data type: {type(data)}")


def trace_address_to_string(trace_address: list[int]) -> str:
    """
    Converts a trace address to a string representation that can be used in a primary key

    >>> trace_address_to_string([0, 1, 2])
    '[0,1,2]'

    :param trace_address:
    :return:
    """
    return f"[{','.join([str(i) for i in trace_address])}]"


def string_to_trace_address(trace_address_string: str) -> list[int]:
    """
    Converts a trace address string to a list of integers

    >>> string_to_trace_address('[0,1,2]')
    [0, 1, 2]

    :param trace_address_string:
    :return:
    """
    return [int(i) for i in trace_address_string[1:-1].split(",")]


def automap_sqlalchemy_model(
    db_engine: Engine | Connection,
    table_names: list[str],
    schema: str = "public",
) -> dict[str, Type[DeclarativeBase]]:
    """
    Automaps a list of tables from a database schema and returns a dictionary of table names to SQLAlchemy models.
    Used for generalized event backfills to enable lookups of tables, and generating DeclarativeBase objects
    from the DB.

    Can only introspect one schema at a time, so if you need to automap tables from multiple schemas, you will need
    to call this function multiple times.

    :param db_engine: SqlAlchemy Engine object
    :param table_names: list of table names to automap
    :param schema: schema to use for automapping  [default: "public"]
    :return:
    """

    logger.info(f"Automapping tables {table_names} from schema {schema}")

    metadata = MetaData(
        schema=schema,
    )

    try:
        metadata.reflect(db_engine, only=table_names)
    except InvalidRequestError as e:
        raise DatabaseError(
            f'Could not load tables {table_names} from "{schema}" schema'
        ) from e

    Base = automap_base(metadata=metadata)  # pylint: disable=invalid-name

    Base.prepare()

    return_dict = {}
    for table_name in table_names:
        if table_name not in Base.classes:
            raise DatabaseError(f"Table {table_name} not found in database")

        return_dict.update({table_name: Base.classes[table_name]})

    return return_dict
