import atexit
import queue
import threading
from enum import Enum
from dataclasses import asdict
from typing import Protocol, Any, TypeVar, Type, Literal, Sequence

import logging
import time

from nethermind.entro.database.models.uniswap import UNI_EVENT_MODELS
from nethermind.entro.database.writers.utils import db_encode_dict
from nethermind.entro.utils import camel_to_snake, maybe_hex_to_int
from nethermind.entro.database.writers.utils import db_encode_hex

from abc import abstractmethod

from sqlalchemy import Connection, Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

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
    json = "json"


class IntegrityMode(Enum):
    ignore = "ignore"
    overwrite = "overwrite"
    fail = "fail"


class BaseResourceExporter:
    export_mode: ExportMode
    init_time: float
    resources_saved: int = 0

    def __init__(self):
        self.init_time = time.time()

    @abstractmethod
    def write(self, resources: list[Dataclass]):
        raise NotImplementedError

    def close(self):
        minutes, seconds = divmod(time.time() - self.init_time, 60)
        logger.info(f"Exported {self.resources_saved} rows in {minutes} minutes {seconds:.1f} seconds")


class FileResourceExporter(BaseResourceExporter):
    file_name: str

    def __init__(self, file_name: str, append: bool = True):
        super().__init__()

        if not file_name.endswith((".csv", ".json")):
            raise ValueError("Export File name must be a .csv or .json file")

        self.export_mode = ExportMode.csv if file_name.endswith(".csv") else ExportMode.json
        self.file_name = file_name
        self.file_handle = open(file_name, "at" if append else "wt")

    def _encode_dataclass(self, dataclass: Dataclass) -> str:
        if self.export_mode == ExportMode.csv:
            return ",".join(asdict(dataclass).values())
        elif self.export_mode == ExportMode.json:
            return db_encode_dict(asdict(dataclass))
        else:
            raise NotImplementedError(f"Export Mode {self.export_mode} is not implemented")

    def write(self, resources: list[Dataclass]):
        for resource in resources:
            self.file_handle.write(resource + "\n")

        self.resources_saved += len(resources)


class DBResourceExporter(BaseResourceExporter):
    integrity_mode: IntegrityMode
    """ 
        Mode for performing database writes.  If set to ignore, rows with conflicting primary keys will be ignored.
        If set to overwrite, rows with conflicting primary keys will be overwritten (Updated).  
        If set to fail, conflicting primary keys will raise a PrimaryKeyError.
    """
    write_delay: int = 30  # seconds between writing DB Models
    engine: Engine | Connection
    session: Session
    dialect: str

    _buffer: queue.Queue[DeclarativeBase]

    def __init__(
        self,
        engine: Engine | Connection,
        integrity_mode: IntegrityMode = "ignore"
    ):
        super().__init__()

        self.engine = engine
        self.integrity_mode = IntegrityMode(integrity_mode)
        self.session = sessionmaker(self.engine)()
        self.dialect = self.engine.dialect.name

        self._buffer = queue.Queue()

        self._flush_thread = threading.Thread(target=self._flush, daemon=True)
        self._flush_thread.start()

    def _dataclass_to_model(self, dc: Dataclass) -> DeclarativeBase:
        if "event" in dc.__class__.__name__.lower():
            raise NotImplementedError("Event Dataclasses cannot be converted")

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
        if len(resources) == 0:
            return

        for resource in resources:
            model = self._dataclass_to_model(resource)
            self._buffer.put(model)

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
        default_event_model: Type[DeclarativeBase],
        event_model_overrides: dict[str, Type[DeclarativeBase]] | None = None,
        integrity_mode: IntegrityMode = "ignore",
    ):
        super().__init__(engine=engine, integrity_mode=integrity_mode)

        self.default_event_model = default_event_model
        self.event_model_mapping = ALL_EVENT_MODELS.copy()

        if event_model_overrides:
            self.event_model_overrides = event_model_overrides
            self.event_model_mapping.update(event_model_overrides)
            self.event_model_mapping.update({"default": self.default_event_model})

    def write(self, resources: list[Dataclass]):
        """Writes an event to the database."""

        for event in resources:
            custom_model = None
            if hasattr(event, "event_signature") and event.event_signature in self.event_model_mapping:
                signature = event.event_signature
                custom_model = self.event_model_mapping[signature]







            dataclass_dict = asdict(event)


            def _db_encode_event(self, decoded_event: dict[str, Any], snake: bool = False) -> dict[str, Any]:
                db_encoded_event = {}
                for name, val in decoded_event.items():
                    db_name = camel_to_snake(name) if snake else name
                    if isinstance(val, str) and val.startswith("0x"):
                        db_encoded_event.update({db_name: db_encode_hex(val, self.db_dialect)})
                    else:
                        db_encoded_event.update({db_name: val})

                return db_encoded_event

            dedicated_model = self.event_model_mapping.get(decoding_result.event_signature)

            if dedicated_model:
                try:
                    model = dedicated_model(
                        **shared_params,
                        **self._db_encode_event(decoding_result.event_data, snake=True),
                    )
                    self.add_to_cache(decoding_result.event_signature, model)

                except TypeError:  # Invalid kwarg is passed to wrong model
                    self.add_to_cache(
                        "default",
                        self.default_event_model(
                            **shared_params,
                            event_name=event_name,
                            abi_name=decoding_result.abi_name,
                            decoded_event=db_encode_dict(decoding_result.event_data),
                        ),
                    )
                else:
                    self.add_to_cache(
                        "default",
                        self.default_event_model(
                            **shared_params,
                            event_name=event_name,
                            abi_name=decoding_result.abi_name,
                            decoded_event=db_encode_dict(decoding_result.event_data),
                        ),
                    )

        self.resources_saved += len(resources)
