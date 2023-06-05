import os
import random
from logging import Logger

import pytest
from dotenv import load_dotenv
from eth_utils import to_checksum_address
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from web3 import Web3

from .utils import TEST_LOGGER

load_dotenv()


@pytest.fixture(name="get_random_binary_string")
def fixture_get_random_binary():
    def _generate_random_binary_string(length: int, binary_string: str = "") -> str:
        for i in range(length):
            binary_string += str(random.randint(0, 1))
        return binary_string

    return _generate_random_binary_string


@pytest.fixture(name="random_address")
def fixture_random_address():
    def _generate_random_address():
        return to_checksum_address(random.randbytes(20).hex())

    return _generate_random_address


@pytest.fixture
def w3_archive_node():
    return Web3(Web3.HTTPProvider(os.environ["ARCHIVE_NODE_RPC_URL"]))


@pytest.fixture
def db_session() -> Session:
    return sessionmaker(
        bind=create_engine(os.environ.get("SQLALCHEMY_DB_URI", "sqlite:///:memory:"))
    )()


@pytest.fixture
def test_logger() -> Logger:
    return TEST_LOGGER
