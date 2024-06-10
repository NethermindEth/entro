import pytest
from sqlalchemy.exc import IntegrityError

from nethermind.entro.database.models import ContractABI
from tests.resources.ABI import ERC20_ABI_JSON


@pytest.fixture
def add_erc20_abi(db_session):
    erc_20 = ContractABI(
        abi_name="ERC20",
        abi_json=ERC20_ABI_JSON,
    )
    try:
        db_session.add(erc_20)
        db_session.commit()
    except IntegrityError:
        db_session.rollback()

    yield

    db_session.query(ContractABI).filter(ContractABI.abi_name == "ERC20").delete()
    db_session.commit()
    db_session.close()
