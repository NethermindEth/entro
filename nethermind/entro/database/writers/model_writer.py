import logging
import time
from typing import Sequence, Type

from sqlalchemy import Connection, Engine, TableClause
from sqlalchemy.orm import DeclarativeBase

from ...exceptions import DatabaseError
from .base_writer import BaseWriter, IntegrityModes
from .utils import model_to_dict

root_logger = logging.getLogger("nethermind")
logger = root_logger.getChild("entro").getChild("db").getChild("model_writer")


class ModelWriter(BaseWriter):
    """
    Utility class for writing data to the database.  This class is used to enforce single model DB writes.
    """

    returning_data: bool = False
    returning_hashes: bool = False
    save_to_db: bool = True

    db_cache: list[DeclarativeBase]
    db_model: Type[DeclarativeBase]
    db_table: TableClause

    """ Database Mode Class that is being saved to DB """
    return_cache: list[DeclarativeBase | str]

    def __init__(
        self,
        db_engine: Engine | Connection,
        db_model: Type[DeclarativeBase],
        integrity_mode: IntegrityModes = "ignore",
        returning_data: bool = False,
        returning_hashes: bool = False,
        save_to_db: bool = True,
    ):
        if returning_data and returning_hashes:
            raise ValueError("Must return either data or hashes, but not both")

        self.db_engine = db_engine
        self.create_session()
        self.integrity_mode = integrity_mode
        self.db_model = db_model

        if isinstance(db_model.__table__, TableClause):
            self.db_table = db_model.__table__
        else:
            raise DatabaseError(f"Invalid DeclarativeBase db model: {db_model}")

        self.returning_data = returning_data
        self.returning_hashes = returning_hashes
        self.save_to_db = save_to_db

        self.db_cache = []
        self.return_cache = []

        self.downloaded_rows = 0
        self.start_time = time.time()

        logger.info(
            f"Initialized Model Writer for {self.db_model.metadata.schema}.{self.db_model.__tablename__} "
            f"with integrity mode '{self.integrity_mode}'"
        )

    def add_backfill_data(self, data: Sequence[DeclarativeBase]):
        """
        Saves a list of ORM models to the database
        :param data: List of ORM models of Type[DeclarativeMeta]
        :return:
        """
        self.downloaded_rows += len(data)
        for row in data:
            if not isinstance(row, self.db_model):
                logger.error(f"Passed model type: {type(row)} to ModelWriter configured for {self.db_model}")

        if self.returning_hashes:
            self.return_cache.extend([self.get_model_hash(d) for d in data])
            return

        if self.returning_data:
            self.return_cache.extend(data)

        if self.save_to_db:
            self.db_cache.extend(data)
            if len(self.db_cache) > 500:
                logger.info(f"Writing {len(self.db_cache)} {self.db_table.name} models to DB")
                logger.debug(
                    f"First Model: {model_to_dict(self.db_cache[0])}\t\t"
                    f"Last Model: {model_to_dict(self.db_cache[-1])}"
                )
                self.save_models(self.db_cache, self.db_table)
                self.db_cache = []

    def finish(self):
        """
        Saves any remaining models in the cache to the database and prints a summary of the total db
        writes performed, and the time since creation.
        """
        self.save_models(self.db_cache, self.db_table)

        self.db_session.commit()
        self.db_session.close()

        minutes, seconds = divmod(time.time() - self.start_time, 60)
        logger.info(
            f"Queried & Wrote {self.downloaded_rows} {self.db_model} Models to DB in "
            f"{int(minutes)} minutes {seconds:.1f} seconds"
        )
