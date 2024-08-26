import json
import logging
import os.path
import time
from abc import abstractmethod
from enum import Enum
from typing import Any, Type

from sqlalchemy import Connection, Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from nethermind.entro.database.models import (
    block_model_for_network,
    default_event_model_for_network,
    trace_model_for_network,
    transaction_model_for_network,
    transfer_model_for_network,
)
from nethermind.entro.database.models.uniswap import UNI_EVENT_MODELS
from nethermind.entro.database.writers.utils import db_encode_hex
from nethermind.entro.exceptions import BackfillError
from nethermind.entro.types.backfill import (
    BackfillDataType,
    Dataclass,
    ExporterDataType,
    SupportedNetwork,
    dataclass_as_dict,
)
from nethermind.entro.utils import camel_to_snake
from nethermind.idealis.utils import to_hex

root_logger = logging.getLogger("nethermind")
logger = root_logger.getChild("entro").getChild("export")


ALL_EVENT_MODELS: dict[str, Type[DeclarativeBase]] = {
    **UNI_EVENT_MODELS,
}

# pylint: disable=invalid-name


class ExportMode(Enum):
    """Export Mode for writing data to a datastore"""

    db_models = "db_models"
    csv = "csv"
    # json = "json"


class IntegrityMode(Enum):
    """
    Mode for handling conflicting primary keys in the database.

    If set to ignore, rows with conflicting primary keys will be ignored... (ON CONFLICT DO NOTHING)
    If set to overwrite, rows with conflicting primary keys will be overwritten (ON CONFLICT DO UPDATE)
    If set to fail, conflicting primary keys will raise a PrimaryKeyError.
    """

    ignore = "ignore"
    overwrite = "overwrite"
    fail = "fail"


# TODO: Refactor this to not be a steaming pile of primary school garbage :facepalm:
def encode_val(obj: Any, csv_out: bool = False, hex_encode_bytes: bool = False) -> Any:
    """Encode a dataclass dictionary into a format that can be passed to a Sqlalchemy model or written as CSV"""

    def json_encode(data: Any) -> Any:
        """
        Recursively encodes a dictionary or list.  Converts all binary types to hexstrings that can be saved to
        the database in JSON columns.

        :param data:
        :return:
        """
        if isinstance(data, dict):
            return {k: json_encode(v) for k, v in data.items()}

        if isinstance(data, (list, tuple)):
            return [json_encode(d) for d in data]

        if isinstance(data, Enum):
            return data.name

        if isinstance(data, bytes):
            return "0x" + data.hex()

        return data

    if obj is None and csv_out:
        return ""

    if isinstance(obj, (int, float)) and csv_out:
        return str(obj)

    if isinstance(obj, (list, tuple, dict)):
        return json.dumps(json_encode(obj))

    if isinstance(obj, bytes) and hex_encode_bytes:
        return to_hex(obj)

    if isinstance(obj, Enum):
        return obj.name

    return obj


def db_encode_dataclass(dataclass: Dataclass, db_dialect: str) -> dict[str, Any]:
    """
    Encode a dataclass dictionary into a format that can be passed to a Sqlalchemy model
    :param dataclass: Dataclass to encode
    :param db_dialect: Database dialect to determine how to encode bytes
    """
    dataclass_dict = dataclass_as_dict(dataclass)
    hex_encode = db_dialect != "postgresql"

    return {k: encode_val(v, hex_encode_bytes=hex_encode) for k, v in dataclass_dict.items()}


class AbstractResourceExporter:
    """Abstract class for exporting data to a datastore"""

    export_mode: ExportMode
    init_time: float
    resources_saved: int = 0

    def __init__(self):
        self.init_time = time.time()

    @abstractmethod
    def write(self, resources: list[Dataclass]):
        """Write a list of dataclasses to the datastore, performing any necessary encoding"""
        raise NotImplementedError

    def close(self):
        """Perform any necessary cleanup operations & Printout export stats"""
        minutes, seconds = divmod(time.time() - self.init_time, 60)
        logger.info(f"Exported {self.resources_saved} rows in {minutes} minutes {seconds:.1f} seconds")


class FileResourceExporter(AbstractResourceExporter):
    """Export Dataclasses to a CSV File.  Performs Necessary Dataclass -> CSV Encoding"""

    file_name: str
    write_headers: bool = False
    csv_separator: str = "|"

    def __init__(self, file_name: str, append: bool = True):
        super().__init__()

        if not file_name.endswith(".csv"):
            raise ValueError("Export File name must be a .csv file")

        self.export_mode = ExportMode.csv
        self.file_name = file_name
        self.file_handle = open(file_name, "at" if append else "wt")  # pylint: disable=consider-using-with
        file_size = os.path.getsize(file_name)
        if file_size == 0:
            self.write_headers = True

    def _encode_dataclass(self, dataclass: Dataclass) -> tuple[list[str], str]:
        dataclass_dict = dataclass_as_dict(dataclass)

        csv_encoded = [encode_val(val, csv_out=True, hex_encode_bytes=True) for val in dataclass_dict.values()]

        if self.export_mode == ExportMode.csv:
            return list(dataclass_dict.keys()), self.csv_separator.join(csv_encoded)

        raise NotImplementedError(f"Export Mode {self.export_mode} is not implemented")

    def write(self, resources: list[Dataclass]):
        # TODO: Optimize the CSV encoding disaster...
        for resource in resources:
            headers, csv_row = self._encode_dataclass(resource)
            if self.write_headers:
                self.file_handle.write(self.csv_separator.join(headers) + "\n")
                self.write_headers = False

            self.file_handle.write(csv_row + "\n")

        self.resources_saved += len(resources)


class DBResourceExporter(AbstractResourceExporter):
    """Export Dataclasses to a Database.  Performs Necessary Dataclass -> ORM Model Conversion & Encoding"""

    integrity_mode: IntegrityMode
    """ 
        Mode for performing database writes.  If set to ignore, rows with conflicting primary keys will be ignored.
        If set to overwrite, rows with conflicting primary keys will be overwritten (Updated).  
        If set to fail, conflicting primary keys will raise a PrimaryKeyError.
    """
    default_model: Type[DeclarativeBase]

    engine: Engine | Connection
    session: Session
    dialect: str

    def __init__(
        self,
        engine: Engine | Connection,
        default_model: Type[DeclarativeBase],
        integrity_mode: IntegrityMode = IntegrityMode.ignore,
    ):
        super().__init__()

        self.engine = engine
        self.default_model = default_model
        self.integrity_mode = IntegrityMode(integrity_mode)
        self.session = sessionmaker(self.engine)()
        self.dialect = self.engine.dialect.name

    def _insert_models(self, db_models: list[DeclarativeBase]):
        match self.integrity_mode:  # TODO: Clean up this dumpster-fire
            case IntegrityMode.ignore:
                self.session.bulk_save_objects(db_models, update_changed_only=True)
            case IntegrityMode.overwrite:
                self.session.bulk_save_objects(db_models)
            case IntegrityMode.fail:
                self.session.bulk_save_objects(db_models)
            case _:
                raise NotImplementedError

        self.session.commit()

    def write(self, resources: list[Dataclass]):
        """
        Writes a list of dataclasses to the database.  Dataclasses are converted to ORM models, and added to a buffer
        :return:
        """

        db_models = []

        for resource in resources:
            encoded_dataclass = db_encode_dataclass(resource, self.dialect)
            try:
                db_models.append(self.default_model(**encoded_dataclass))
            except BaseException:
                logger.error(f"Error encoding dataclass to {self.default_model}.  Dataclass: {encoded_dataclass}")
                raise BackfillError("Error encoding dataclass to ORM model")

        self._insert_models(db_models)
        self.resources_saved += len(resources)

    def close(self):
        """
        Save remaining data to the database, perform cleanup, and close database Session
        """
        super().close()

        self.session.close()


class EventExporter(DBResourceExporter):
    """
    Database interface for writing decoded events to the database
    """

    db_cache: dict[str, list[DeclarativeBase]]
    event_model_mapping: dict[str, Type[DeclarativeBase]]
    event_model_overrides: dict[str, Type[DeclarativeBase]] | None = None

    def __init__(
        self,
        engine: Engine | Connection,
        event_model: Type[DeclarativeBase],
        event_model_overrides: dict[str, Type[DeclarativeBase]] | None = None,
        integrity_mode: IntegrityMode = IntegrityMode.ignore,
    ):
        super().__init__(engine=engine, integrity_mode=integrity_mode, default_model=event_model)

        self.event_model_mapping = ALL_EVENT_MODELS.copy()

        if event_model_overrides:
            self.event_model_overrides = event_model_overrides
            self.event_model_mapping.update(event_model_overrides)
            self.event_model_mapping.update({"default": self.default_model})

    def _db_encode_event_params(self, decoded_params: dict[str, Any], snake: bool = False) -> dict[str, Any]:
        db_encoded_event = {}
        for name, val in decoded_params.items():
            db_name = camel_to_snake(name) if snake else name
            if isinstance(val, bytes) or (isinstance(val, str) and val.startswith("0x")):
                db_encoded_event.update({db_name: db_encode_hex(val, self.dialect)})
            else:
                db_encoded_event.update({db_name: val})

        return db_encoded_event

    def write(self, resources: list[Dataclass]):
        """Writes an event to the database."""
        write_events = []

        for event in resources:
            encoded_dataclass = db_encode_dataclass(event, self.dialect)

            custom_model = None
            if hasattr(event, "event_signature") and event.event_signature in self.event_model_mapping:
                signature = event.event_signature
                custom_model = self.event_model_mapping[signature]

            if custom_model:
                model_fields = {
                    k: v
                    for k, v in encoded_dataclass.items()
                    if k not in ("event_signature", "event_name", "decoded_params")
                }

                try:
                    write_events.append(
                        custom_model(
                            **model_fields, **self._db_encode_event_params(encoded_dataclass["decoded_params"])
                        )
                    )
                except (AttributeError, TypeError, IntegrityError):
                    logger.warning(f"Error encoding event to Custom Model {custom_model}.  Event: {encoded_dataclass}")
                    write_events.append(self.default_model(**encoded_dataclass))

            else:
                write_events.append(self.default_model(**encoded_dataclass))

        self._insert_models(write_events)
        self.resources_saved += len(resources)


# pylint: disable=too-many-return-statements
def get_file_exporters_for_backfill(
    backfill_type: BackfillDataType, kwargs: dict[str, Any]
) -> dict[ExporterDataType, AbstractResourceExporter]:
    """If Performing a CSV Export, check that all files required for writing the datatype are present"""
    match backfill_type:
        case BackfillDataType.full_blocks:
            if kwargs["block_file"] and kwargs["transaction_file"] and kwargs["event_file"]:
                return {
                    ExporterDataType.blocks: FileResourceExporter(kwargs["block_file"]),
                    ExporterDataType.transactions: FileResourceExporter(kwargs["transaction_file"]),
                    ExporterDataType.events: FileResourceExporter(kwargs["event_file"]),
                }
            raise BackfillError("Block, Transaction, and Event export files required for full block backfill")

        case BackfillDataType.blocks:
            if kwargs["block_file"]:
                return {ExporterDataType.blocks: FileResourceExporter(kwargs["block_file"])}
            raise BackfillError("Block export file required for Block backfill")

        case BackfillDataType.events:
            if kwargs["event_file"]:
                return {ExporterDataType.events: FileResourceExporter(kwargs["event_file"])}
            raise BackfillError("Event export file required for Event backfill")

        case BackfillDataType.transactions:
            if kwargs["transaction_file"]:
                tx_exporter = FileResourceExporter(kwargs["transaction_file"])

                if kwargs["block_file"]:
                    return {
                        ExporterDataType.blocks: FileResourceExporter(kwargs["block_file"]),
                        ExporterDataType.transactions: tx_exporter,
                    }

                logger.warning("No block file provided for transaction backfill...  Not saving Block data")
                return {ExporterDataType.transactions: tx_exporter}

            raise BackfillError("Transaction export file required for Transaction backfill & optional Block file")

        case BackfillDataType.transfers:
            if kwargs["transfer_file"]:
                return {ExporterDataType.transfers: FileResourceExporter(kwargs["transfer_file"])}

            raise BackfillError("Transfer export file required for transfer backfill")

        case BackfillDataType.traces:
            if kwargs["trace_file"]:
                return {ExporterDataType.traces: FileResourceExporter(kwargs["trace_file"])}
            raise BackfillError("Trace export file required")

        case _:
            raise BackfillError(f"Backfill Type {backfill_type} cannot be exported to CSV")


def get_db_exporters_for_backfill(
    backfill_type: BackfillDataType, db_engine: Engine | Connection, network: SupportedNetwork, kwargs: dict[str, Any]
) -> dict[ExporterDataType, AbstractResourceExporter]:
    """Returns a mapping of exporters for the given backfill type"""
    match backfill_type:
        case backfill_type.blocks:
            return {ExporterDataType.blocks: DBResourceExporter(db_engine, block_model_for_network(network))}

        case backfill_type.transactions:
            return {
                ExporterDataType.blocks: DBResourceExporter(db_engine, block_model_for_network(network)),
                ExporterDataType.transactions: DBResourceExporter(db_engine, transaction_model_for_network(network)),
            }
        case backfill_type.transfers:
            return {ExporterDataType.transfers: DBResourceExporter(db_engine, transfer_model_for_network(network))}

        case backfill_type.traces:
            return {ExporterDataType.traces: DBResourceExporter(db_engine, trace_model_for_network(network))}

        case backfill_type.events:
            return {
                ExporterDataType.events: EventExporter(
                    db_engine, default_event_model_for_network(network), kwargs.get("event_model_overrides")
                )
            }

        case backfill_type.full_blocks:
            return {
                ExporterDataType.blocks: DBResourceExporter(db_engine, block_model_for_network(network)),
                ExporterDataType.transactions: DBResourceExporter(db_engine, transaction_model_for_network(network)),
                ExporterDataType.events: EventExporter(
                    db_engine, default_event_model_for_network(network), kwargs.get("event_model_overrides")
                ),
            }
        case _:
            raise NotImplementedError(f"Backfill Type {backfill_type} cannot be exported to DB")
