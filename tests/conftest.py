import logging
import random
from pathlib import Path

import pytest
from eth_utils import to_checksum_address
from pytest import FixtureRequest


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


@pytest.fixture(scope="function")
def debug_logger(request: FixtureRequest):
    log_filename = (
        request.module.__name__.replace("integration_tests.", "")
        + "."
        + request.function.__name__
    )

    parent_dir = Path(__file__).parent
    log_file = parent_dir / "logs" / f"{log_filename}.log"

    formatter = logging.Formatter(
        "%(levelname)-8s | %(name)-36s | %(asctime)-15s | %(message)s \t\t (%(filename)s --> %(funcName)s)"
    )

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)

    logger = logging.getLogger("python_eth_amm")
    logger.addHandler(file_handler)
    logger.setLevel(logging.DEBUG)

    logger.info("-" * 100)
    logger.info(f"\t\tInitializing New Run for Test: {request.function.__name__}")
    logger.info("-" * 100)

    return logger
