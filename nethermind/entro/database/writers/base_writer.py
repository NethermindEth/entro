import logging
import time
from abc import abstractmethod
from typing import Literal, Sequence

from sqlalchemy import Connection, Engine, TableClause
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .utils import model_to_dict

root_logger = logging.getLogger("nethermind")
logger = root_logger.getChild("entro").getChild("db").getChild("base_writer")

IntegrityModes = Literal["ignore", "overwrite", "fail"]


class BaseWriter:
    """
    Base class for database writers.  Handles database connections, and provides utility methods for writing data to
    the database.
    """

    integrity_mode: IntegrityModes
    """ 
        Mode for perfomring database writes.  If set to ignore, rows with conflicting primary keys will be ignored.
        If set to overwrite, rows with conflicting primary keys will be overwritten (Updated).  
        If set to fail, conficting primary keys will raise a PrimaryKeyError.
    """

    db_engine: Engine | Connection
    db_session: Session
    db_dialect: str

    def create_session(self):
        """Creates a new db_session"""
        self.db_session = sessionmaker(self.db_engine)()
        self.db_dialect = self.db_engine.dialect.name

    def save_models(self, model_data: Sequence[DeclarativeBase], insert_table: TableClause):
        """
        Saves the models in the cache to the database.

        Handles integrity errors and conflicts based on the database dialect, and the overwrite mode
        # TODO: Add overwrite when CLI flags are set

        :return:
        """
        if len(model_data) == 0:
            return

        if self.db_dialect == "postgresql":
            statement = postgresql.insert(insert_table).values([model_to_dict(row) for row in model_data])
            match self.integrity_mode:
                case "ignore":
                    statement = statement.on_conflict_do_nothing(  # type: ignore
                        index_elements=list(insert_table.primary_key.columns.keys())  # type: ignore
                    )
                case "overwrite":
                    raise NotImplementedError("Overwrite mode not yet implemented")

                case "fail":
                    pass  # Dont add any conflict statement

            self.db_session.execute(statement)
            self.db_session.commit()

        else:
            try:
                self.db_session.bulk_save_objects(model_data)
                self.db_session.commit()
            except IntegrityError as exc:
                # Create Intermediary table to select conflicting keys
                raise NotImplementedError() from exc

    def retry_enabled_execute(self, statement, retry_count: int = 3):
        """
        Executes a statement, retrying on OperationalError up to retry_count times.  Used to gracefully handling
        database errors.

        :param statement:
        :param retry_count:
        :return:
        """
        for retry in range(retry_count):
            try:
                self.db_session.execute(statement)
                self.db_session.commit()
                break
            except OperationalError as exc:
                logger.error(f"Operational Error while Writing to DB: {exc}")
                logger.warning(f"Retrying {retry}/{retry_count} in 60 seconds")
                self.db_session.rollback()
                self.db_session.close()
                time.sleep(60)
                self.create_session()
                continue
            except Exception as exc:
                logger.error(f"Error while Writing to DB: {exc}")
                self.db_session.rollback()
                self.db_session.close()
                raise exc

    def get_model_block_number(self, model: DeclarativeBase) -> int:
        """
        Returns the block number of a db model.  Checks the following keys in order, returning the first one found:
            - block_number
            - block
            - number

        Raises ValueError if no block number is found for db model.
        :param model: sqlachemy.orm.DeclarativeBase
        :return: value of block number
        """
        if hasattr(model, "block_number"):
            return model.block_number
        if hasattr(model, "block"):
            return model.block
        raise ValueError(f"Block number not found in model: {model}")

    def get_model_hash(self, model: DeclarativeBase) -> str:
        """
        Returns the hash of a db model.  Checks the following keys in order, returning the first one found:
            - hash
            - transaction_hash
            - block_hash

        Raises ValueError if no hash is found for db model.

        :param model: sqlachemy.orm.DeclarativeBase
        :return: value of hash
        """
        if hasattr(model, "hash"):
            return model.hash
        if hasattr(model, "transaction_hash"):
            return model.transaction_hash
        if hasattr(model, "block_hash"):
            return model.block_hash
        raise ValueError(f"Hash not found in model: {model}")

    @abstractmethod
    def finish(self):
        """
        Save remaining data to the database, perform cleanup, and close out databse Sessions
        """
