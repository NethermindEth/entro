import os

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine

from python_eth_amm.uniswap_v3 import UniswapV3Pool

# from python_eth_amm import ERC20Token


@pytest.fixture(scope="module", autouse=True)
def migrate_sqlalchemy_db():
    load_dotenv()
    engine = create_engine(os.environ.get("SQLALCHEMY_DB_URI", "sqlite:///:memory:"))
    UniswapV3Pool.migrate_up(engine)
    # ERC20Token.migrate_up(engine)
