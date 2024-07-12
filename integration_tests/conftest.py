import logging
import os
import time
from pathlib import Path

import docker  # type: ignore
import psycopg2
import pytest
from dotenv import load_dotenv
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from pytest import FixtureRequest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from web3 import Web3


@pytest.fixture(scope="function")
def integration_postgres_db():
    load_dotenv()

    client = docker.from_env()
    container_args = {
        "image": "postgres:14",
        "environment": {
            "POSTGRES_PASSWORD": os.environ["PG_PASS"],
        },
        "name": "entro_testing",
        "ports": {"5432/tcp": ("127.0.0.1", os.environ["PG_PORT"])},
        "detach": True,
    }

    try:
        container = client.containers.run(**container_args)

    except docker.errors.APIError:
        client.containers.get("entro_testing").remove(force=True)
        container = client.containers.run(**container_args)

    while True:
        if b"database system is ready to accept connections" in container.logs():
            time.sleep(0.75)
            break
        time.sleep(0.1)

    connection = psycopg2.connect(
        user="postgres",
        host="127.0.0.1",
        port=os.environ["PG_PORT"],
        password=os.environ["PG_PASS"],
    )
    connection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    connection.cursor().execute("CREATE DATABASE entro;")

    yield

    connection.close()
    container.stop()


@pytest.fixture
def integration_db_url() -> str:
    return f"postgresql+psycopg2://postgres:{os.environ['PG_PASS']}@127.0.0.1:{os.environ['PG_PORT']}/entro"


@pytest.fixture
def integration_db_session(integration_db_url) -> Session:
    return sessionmaker(bind=create_engine(integration_db_url))()


@pytest.fixture(scope="function")
def create_debug_logger(request: FixtureRequest) -> logging.Logger:
    log_filename = request.module.__name__.replace("integration_tests.", "") + "." + request.function.__name__

    parent_dir = Path(__file__).parent
    log_file = parent_dir / "logs" / f"{log_filename}.log"

    formatter = logging.Formatter(
        "%(levelname)-8s | %(name)-36s | %(asctime)-15s | %(message)s \t\t (%(filename)s --> %(funcName)s)"
    )

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)

    logger = logging.getLogger("nethermind")
    logger.addHandler(file_handler)
    logger.setLevel(logging.DEBUG)

    logger.info("-" * 100)
    logger.info(f"\t\tInitializing New Run for Test: {request.function.__name__}")
    logger.info("-" * 100)

    return logger


@pytest.fixture
def eth_rpc_url() -> str:
    load_dotenv()
    return os.environ["ETH_JSON_RPC"]


@pytest.fixture
def starknet_rpc_url() -> str:
    load_dotenv()
    return os.environ["STARKNET_JSON_RPC"]


@pytest.fixture
def eth_archival_w3():
    load_dotenv()
    return Web3(Web3.HTTPProvider(os.environ["ETH_ARCHIVE_JSON_RPC"]))
