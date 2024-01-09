import logging

from sqlalchemy import Select, create_engine
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session, sessionmaker

from python_eth_amm.exceptions import DatabaseError

package_logger = logging.getLogger("python_eth_amm")
logger = package_logger.getChild("db")


def create_session(db_url: str) -> Session:
    """Creates a new database session"""
    engine = create_engine(db_url)
    return sessionmaker(bind=engine)()


def execute_scalars_query(db_session: Session, query: Select):
    """
    Executes a query and returns the results as a list of scalars.  If errors occur during execution, will
    handle different errors raise a more specific DatabaseError if possible.

    :param db_session:
    :param query:
    :return:
    """
    try:
        results = db_session.execute(query).scalars().all()
    except ProgrammingError as programming_error:
        error_str = str(programming_error)

        if "psycopg2.errors.UndefinedTable" in error_str:
            undef = [
                f"{from_.schema}.{from_.description}"
                for from_ in query.get_final_froms()
            ]
            raise DatabaseError(
                f"Database Tables do not exist...  One of the following tables is missing: {undef}"
            ) from programming_error
        raise programming_error

    return results
