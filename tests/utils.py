import logging
import sys
from logging import Formatter, Logger, StreamHandler


def _create_test_logger() -> Logger:
    formatter = Formatter(fmt="%(levelname)-8s %(message)s")
    std = StreamHandler(sys.stdout)
    std.setFormatter(formatter)

    logger = logging.getLogger("python_eth_amm_tests")
    logger.addHandler(std)
    logger.setLevel(logging.DEBUG)
    return logger


TEST_LOGGER = _create_test_logger()


def expand_to_decimals(num: int, decimals: int = 18) -> int:
    return (10**decimals) * num


def uint_max(bits: int) -> int:
    return 2**bits - 1
