import os
from decimal import getcontext
from typing import Optional, Tuple

import pytest
from dotenv import load_dotenv
from eth_typing import ChecksumAddress
from eth_utils import to_checksum_address
from sqlalchemy import create_engine

from python_eth_amm import PoolFactory
from python_eth_amm.uniswap_v3 import UniswapV3Pool

from .utils import MAX_TICK, MIN_TICK, encode_sqrt_price


@pytest.fixture(scope="module", autouse=True)
def migrate_sqlalchemy_db():
    getcontext().prec = 78
    load_dotenv()
    engine = create_engine(os.environ.get("SQLALCHEMY_DB_URI", "sqlite:///:memory:"))
    UniswapV3Pool.migrate_up(engine)


@pytest.fixture(name="exact_math_factory")
def exact_math_factory(w3_archive_node, test_logger):
    pool_factory = PoolFactory(
        exact_math=True,
        logger=test_logger,
        sqlalchemy_uri=os.environ["SQLALCHEMY_DB_URI"],
        w3=w3_archive_node,
    )
    return pool_factory


@pytest.fixture(name="initialize_empty_pool")
def fixture_initialize_empty_pool(test_logger):
    def _initialize_empty_pool(
        tick_spacing: Optional[int] = 60,
        fee: Optional[int] = 3_000,
        pool_factory: Optional = None,
        **kwargs,
    ):
        if pool_factory is None:
            pool_factory = PoolFactory(
                exact_math=True,
                logger=test_logger,
                sqlalchemy_uri=os.environ["SQLALCHEMY_DB_URI"],
            )
        return pool_factory.initialize_empty_pool(
            pool_type="uniswap_v3",
            initialization_args={
                "tick_spacing": tick_spacing,
                "initial_block": 10_000_000,
                "fee": fee,
                **kwargs,
            },
        )

    return _initialize_empty_pool


@pytest.fixture(name="initialize_mint_test_pool")
def fixture_initialize_mint_test_pool(test_logger, random_address):
    def _initialize_mint_test_pool(
        tick_spacing: int, pool_factory: Optional = None, **kwargs
    ) -> Tuple[UniswapV3Pool, ChecksumAddress]:
        minter_address = random_address()

        if pool_factory is None:
            pool_factory = PoolFactory(
                exact_math=True,
                logger=test_logger,
                sqlalchemy_uri=os.environ["SQLALCHEMY_DB_URI"],
            )
        mint_test_pool = pool_factory.initialize_empty_pool(
            pool_type="uniswap_v3",
            initialization_args={
                "tick_spacing": tick_spacing,
                "initial_price": encode_sqrt_price(1, 10),
                "initial_block": 10_000_000,
                **kwargs,
            },
        )

        mint_test_pool.mint(
            minter_address, MIN_TICK[tick_spacing], MAX_TICK[tick_spacing], 3161
        )
        return mint_test_pool, minter_address

    return _initialize_mint_test_pool


@pytest.fixture(name="initialize_burn_test_pool")
def fixture_initialize_burn_test_pool(test_logger):
    def _initialize_burn_test_pool(pool_factory: Optional = None, **kwargs):
        if pool_factory is None:
            pool_factory = PoolFactory(
                exact_math=True,
                logger=test_logger,
                sqlalchemy_uri=os.environ["SQLALCHEMY_DB_URI"],
            )

        return pool_factory.initialize_empty_pool(
            pool_type="uniswap_v3",
            initialization_args={
                "tick_spacing": 60,
                "initial_price": encode_sqrt_price(1, 10),
                "initial_block": 10_000_000,
                **kwargs,
            },
        )

    return _initialize_burn_test_pool


@pytest.fixture
def usdc_weth_contract(w3_archive_node):  # 0.05%  tick_spacing: 10
    return w3_archive_node.eth.contract(
        address=to_checksum_address("0x8ad599c3a0ff1de082011efddc58f1908eb6e6d8"),
        abi=UniswapV3Pool.get_abi(),
    )


@pytest.fixture
def wbtc_weth_contract(w3_archive_node):  # 0.3%  tick_spacing: 60
    return w3_archive_node.eth.contract(
        address=to_checksum_address("0xcbcdf9626bc03e24f779434178a73a0b4bad62ed"),
        abi=UniswapV3Pool.get_abi(),
    )


@pytest.fixture
def usdt_weth_contract(w3_archive_node):  # 1%  tick_spacing: 200
    return w3_archive_node.eth.contract(
        address=to_checksum_address("0xc5af84701f98fa483ece78af83f11b6c38aca71d"),
        abi=UniswapV3Pool.get_abi(),
    )
