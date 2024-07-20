import logging
import time
from typing import Any, Type

from sqlalchemy import Connection, Engine, TableClause
from sqlalchemy.orm import DeclarativeBase

from nethermind.entro.database.models import default_event_model_for_network
from nethermind.entro.database.models.uniswap import UNI_EVENT_MODELS
from nethermind.entro.database.writers.utils import db_encode_dict
from nethermind.entro.decoding import DecodedEvent
from nethermind.entro.decoding.utils import signature_to_name
from nethermind.entro.types.backfill import SupportedNetwork
from nethermind.entro.utils import camel_to_snake
from nethermind.idealis.utils import hex_to_int

from .base_writer import BaseWriter, IntegrityModes
from .utils import db_encode_hex

ALL_EVENT_MODELS: dict[str, Type[DeclarativeBase]] = {
    **UNI_EVENT_MODELS,
}

root_logger = logging.getLogger("nethermind")
logger = root_logger.getChild("entro").getChild("db").getChild("event_writer")


class EventWriter(BaseWriter):
    """
    Database interface for writing decoded events to the database
    """

    db_cache: dict[str, list[DeclarativeBase]]
    event_model_mapping: dict[str, Type[DeclarativeBase]]
    event_model_overrides: dict[str, Type[DeclarativeBase]] | None = None

    def __init__(
        self,
        db_engine: Engine | Connection,
        network: SupportedNetwork,
        integrity_mode: IntegrityModes = "ignore",
        event_model_overrides: dict[str, Type[DeclarativeBase]] | None = None,
    ):
        self.db_engine = db_engine
        self.create_session()
        self.integrity_mode = integrity_mode

        self.db_cache = {}

        self.default_event_model = default_event_model_for_network(network)
        self.event_model_mapping = ALL_EVENT_MODELS.copy()

        if event_model_overrides:
            self.event_model_overrides = event_model_overrides
            self.event_model_mapping.update(event_model_overrides)
            self.event_model_mapping.update({"default": self.default_event_model})

        self.start_time = time.time()
        self.total_rows_written = 0

    def add_to_cache(self, event_signature: str, model: DeclarativeBase):
        """
        Adds a model to the cache for a given event signature.  If the cache is full, the cache is
        written to the database. And then cleared for the given event signature.

        :param event_signature:
        :param model:
        :return:
        """
        try:
            event_cache = self.db_cache[event_signature]
        except KeyError:
            self.db_cache.update({event_signature: [model]})
            return
        event_cache.append(model)

        if len(event_cache) >= 500:
            self.total_rows_written += len(event_cache)
            self.save_models(
                model_data=event_cache,
                insert_table=self._table_for_event(event_signature),
            )
            self.db_cache[event_signature] = []

    def _table_for_event(self, event_signature: str) -> TableClause:
        if event_signature == "default":
            return self.default_event_model.__table__  # type: ignore

        return self.event_model_mapping[event_signature].__table__  # type: ignore

    def _db_encode_event(self, decoded_event: dict[str, Any], snake: bool = False) -> dict[str, Any]:
        db_encoded_event = {}
        for name, val in decoded_event.items():
            db_name = camel_to_snake(name) if snake else name
            if isinstance(val, str) and val.startswith("0x"):
                db_encoded_event.update({db_name: db_encode_hex(val, self.db_dialect)})
            else:
                db_encoded_event.update({db_name: val})

        return db_encoded_event

    def write_event(
        self,
        decoding_result: DecodedEvent,
        raw_log: dict[str, Any],
    ):
        """Writes an event to the database."""

        shared_params = {
            "block_number": hex_to_int(raw_log["blockNumber"]),
            "log_index": hex_to_int(raw_log["logIndex"]),
            "transaction_index": hex_to_int(raw_log["transactionIndex"]),
            "contract_address": db_encode_hex(raw_log["address"], self.db_dialect),
        }

        event_name = signature_to_name(decoding_result.event_signature)
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

    def finish(self):
        for event_signature, cache_data in self.db_cache.items():
            self.total_rows_written += len(cache_data)
            self.save_models(
                model_data=cache_data,
                insert_table=self._table_for_event(event_signature),
            )
        self.db_session.commit()
        self.db_session.close()

        minutes, seconds = divmod(time.time() - self.start_time, 60)

        logger.info(f"Wrote {self.total_rows_written} Events to database in {minutes} minutes {seconds:.1f} seconds")
