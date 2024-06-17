import atexit
import logging
import queue
import threading
import time
from abc import abstractmethod
from dataclasses import asdict
from enum import Enum
from typing import Any, Protocol, Type, TypeVar

from sqlalchemy import Connection, Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from entro.exceptions import BackfillError
from entro.types.backfill import BackfillDataType, SupportedNetwork
from nethermind.entro.database.models.uniswap import UNI_EVENT_MODELS
from nethermind.entro.database.writers.utils import db_encode_hex
from nethermind.entro.utils import camel_to_snake
from nethermind.idealis.utils import to_hex

root_logger = logging.getLogger("nethermind")
logger = root_logger.getChild("entro").getChild("export")


ALL_EVENT_MODELS: dict[str, Type[DeclarativeBase]] = {
    **UNI_EVENT_MODELS,
}


# This allows type-checkers to enforce dataclass type checks
class DataclassType(Protocol):
    __dataclass_fields__: dict[str, Any]


Dataclass = TypeVar("Dataclass", bound=DataclassType)


class ExportMode(Enum):
    db_models = "db_models"
    csv = "csv"
    # json = "json"


class IntegrityMode(Enum):
    ignore = "ignore"
    overwrite = "overwrite"
    fail = "fail"


class AbstractResourceExporter:
    export_mode: ExportMode
    init_time: float
    resources_saved: int = 0

    def _encode_dataclass_as_dict(self, dataclass: Dataclass) -> dict[str, Any]:
        dataclass_dict = asdict(dataclass)
        encoded_dataclass_dict = {}

        for key, value in dataclass_dict.items():
            if isinstance(value, bytes) or (isinstance(value, str) and value.startswith("0x")):
                encoded_dataclass_dict.update({key: to_hex(value)})
            else:
                encoded_dataclass_dict.update({key: value})

        return encoded_dataclass_dict

    def __init__(self):
        self.init_time = time.time()

    @abstractmethod
    def write(self, resources: list[Dataclass]):
        raise NotImplementedError

    def close(self):
        minutes, seconds = divmod(time.time() - self.init_time, 60)
        logger.info(f"Exported {self.resources_saved} rows in {minutes} minutes {seconds:.1f} seconds")


class FileResourceExporter(AbstractResourceExporter):
    file_name: str

    def __init__(self, file_name: str, append: bool = True):
        super().__init__()

        if not file_name.endswith(".csv"):
            raise ValueError("Export File name must be a .csv file")

        self.export_mode = ExportMode.csv
        self.file_name = file_name
        self.file_handle = open(file_name, "at" if append else "wt")

    def _encode_dataclass(self, dataclass: Dataclass) -> str:
        encoded_dict = self._encode_dataclass_as_dict(dataclass)

        if self.export_mode == ExportMode.csv:
            return ",".join(encoded_dict.values())
        else:
            raise NotImplementedError(f"Export Mode {self.export_mode} is not implemented")

    def write(self, resources: list[Dataclass]):
        for resource in resources:
            csv_row = self._encode_dataclass(resource)
            self.file_handle.write(csv_row + "\n")

        self.resources_saved += len(resources)


class DBResourceExporter(AbstractResourceExporter):
    integrity_mode: IntegrityMode
    """ 
        Mode for performing database writes.  If set to ignore, rows with conflicting primary keys will be ignored.
        If set to overwrite, rows with conflicting primary keys will be overwritten (Updated).  
        If set to fail, conflicting primary keys will raise a PrimaryKeyError.
    """
    default_model: Type[DeclarativeBase]

    write_delay: int = 30  # seconds between writing DB Models
    engine: Engine | Connection
    session: Session
    dialect: str

    _buffer: queue.Queue[DeclarativeBase]

    def __init__(
        self,
        engine: Engine | Connection,
        default_model: Type[DeclarativeBase],
        integrity_mode: IntegrityMode = "ignore",
    ):
        super().__init__()

        self.engine = engine
        self.default_model = default_model
        self.integrity_mode = IntegrityMode(integrity_mode)
        self.session = sessionmaker(self.engine)()
        self.dialect = self.engine.dialect.name

        self._buffer = queue.Queue()

        self._flush_thread = threading.Thread(target=self._flush, daemon=True)
        self._flush_thread.start()

    def _encode_dataclass_as_dict(self, dataclass: Dataclass) -> dict[str, Any]:
        dataclass_dict = asdict(dataclass)
        encoded_dataclass_dict = {}

        for key, value in dataclass_dict.items():
            if isinstance(value, bytes) or (isinstance(value, str) and value.startswith("0x")):
                encoded_dataclass_dict.update({key: db_encode_hex(value, self.dialect)})
            else:
                encoded_dataclass_dict.update({key: value})

        return encoded_dataclass_dict

    def _dataclass_to_model(self, dc: Dataclass) -> DeclarativeBase:
        encoded_dataclass = self._encode_dataclass_as_dict(dc)

        return self.default_model(**encoded_dataclass)

    def _insert_models(self):
        models = []
        while not self._buffer.empty():
            models.append(self._buffer.get())

        match self.integrity_mode:  # TODO: Clean up this dumpster-fire
            case IntegrityMode.ignore:
                self.session.bulk_save_objects(models, update_changed_only=True)
            case IntegrityMode.overwrite:
                self.session.bulk_save_objects(models)
            case IntegrityMode.fail:
                self.session.bulk_save_objects(models)
            case _:
                raise NotImplementedError

        self.session.commit()

    def _flush(self):
        atexit.register(self._insert_models)

        flushing = False
        while True:
            if not flushing and not self._buffer.empty():
                flushing = True
                self._insert_models()
                flushing = False
            else:
                time.sleep(self.write_delay)

    def write(self, resources: list[Dataclass]):
        """
        Writes a list of dataclasses to the database.  Dataclasses are converted to ORM models, and added to a buffer
        :return:
        """

        for resource in resources:
            self._buffer.put(self._dataclass_to_model(resource))

        self.resources_saved += len(resources)

    def close(self):
        """
        Save remaining data to the database, perform cleanup, and close database Session
        """
        self._flush()

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
        integrity_mode: IntegrityMode = "ignore",
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

        for event in resources:
            dataclass_dict = self._encode_dataclass_as_dict(event)

            custom_model = None
            if hasattr(event, "event_signature") and event.event_signature in self.event_model_mapping:
                signature = event.event_signature
                custom_model = self.event_model_mapping[signature]

            if custom_model:
                model_fields = {
                    k: v
                    for k, v in dataclass_dict.items()
                    if k not in ("event_signature", "event_name", "decoded_params")
                }

                try:
                    self._buffer.put(
                        custom_model(**model_fields, **self._db_encode_event_params(dataclass_dict["decoded_params"]))
                    )
                except (AttributeError, TypeError, IntegrityError):
                    self._buffer.put(self.default_model(**dataclass_dict))

            else:
                self._buffer.put(self.default_model(**dataclass_dict))

        self.resources_saved += len(resources)


def get_file_exporters_for_backfill(backfill_type: BackfillDataType, kwargs: dict[str, Any]):
    """If Performing a CSV Export, check that all files required for writing the datatype are present"""
    match backfill_type:
        case BackfillDataType.full_blocks:
            if "block_file" in kwargs and "transaction_file" in kwargs and "event_file" in kwargs:
                return {
                    "blocks": FileResourceExporter(kwargs["block_file"]),
                    "transactions": FileResourceExporter(kwargs["transaction_file"]),
                    "events": FileResourceExporter(kwargs["event_file"]),
                }
            raise BackfillError("block, transaction, and event export files required for full block backfill")

        case BackfillDataType.blocks:
            if "block_file" in kwargs:
                return {"blocks": FileResourceExporter(kwargs["block_file"])}
            raise BackfillError("block export file required for block backfill")

        case BackfillDataType.transactions:
            if "transaction_file" in kwargs and "block_file" in kwargs:
                return {
                    "blocks": FileResourceExporter(kwargs["block_file"]),
                    "transactions": FileResourceExporter(kwargs["transaction_file"]),
                }
            raise BackfillError("block and transaction export file required for transaction backfill")

        case BackfillDataType.transfers:
            if "transfer_file" in kwargs:
                return {"transfers": FileResourceExporter(kwargs["transfer_file"])}

            raise BackfillError("transfer export file required for transfer backfill")

        case BackfillDataType.traces:
            if "trace_file" in kwargs:
                return {"traces": FileResourceExporter(kwargs["trace_file"])}
            raise BackfillError("trace export file required")

        case _:
            raise BackfillError(f"Backfill Type {backfill_type} cannot be exported to CSV")


def get_db_exporters_for_backfill(
    backfill_type: BackfillDataType, db_engine: Engine | Connection, network: SupportedNetwork, kwargs: dict[str, Any]
):
    match backfill_type:
        case backfill_type.blocks:
            return {"blocks": DBResourceExporter(db_engine, block_model_for_network(network))}

        case backfill_type.transactions:
            return {
                "blocks": DBResourceExporter(db_engine, block_model_for_network(network)),
                "transactions": DBResourceExporter(db_engine, transaction_model_for_network(network)),
            }
        case backfill_type.transfers:
            return {"transfers": DBResourceExporter(db_engine, transfer_model_for_network(network))}

        case backfill_type.traces:
            return {"traces": DBResourceExporter(db_engine, trace_model_for_network(network))}

        case backfill_type.events:
            return {
                "events": EventExporter(
                    db_engine, event_model_for_network(network), kwargs.get("event_model_overrides")
                )
            }

        case backfill_type.full_blocks:
            return {
                "blocks": DBResourceExporter(db_engine, block_model_for_network(network)),
                "transactions": DBResourceExporter(db_engine, transaction_model_for_network(network)),
                "events": EventExporter(
                    db_engine, event_model_for_network(network), kwargs.get("event_model_overrides")
                ),
            }
        case _:
            raise NotImplementedError(f"Backfill Type {backfill_type} cannot be exported to DB")
