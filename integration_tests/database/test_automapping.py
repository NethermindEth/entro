import pytest

from nethermind.entro.database.migrations import migrate_up
from nethermind.entro.database.models.ethereum import Block, Transaction
from nethermind.entro.database.writers.utils import automap_sqlalchemy_model
from nethermind.entro.exceptions import DatabaseError


def test_automap_ethereum_tables(integration_postgres_db, integration_db_session):
    db_engine = integration_db_session.get_bind()

    migrate_up(db_engine)

    ethereum_models = automap_sqlalchemy_model(db_engine, ["blocks", "transactions"], "ethereum_data")

    assert str(Block.__table__.columns) == str(ethereum_models["blocks"].__table__.columns)
    assert str(Transaction.__table__.columns) == str(ethereum_models["transactions"].__table__.columns)

    assert len(ethereum_models) == 2


def test_automap_invalid_tables(integration_db_session):
    db_engine = integration_db_session.get_bind()

    migrate_up(db_engine)

    with pytest.raises(DatabaseError) as excinfo:
        automap_sqlalchemy_model(db_engine, ["blocks", "transactions"], "ethereum")

        assert "Could not load tables ['blocks', 'transactions'] from \"ethereum\" schema" in str(excinfo.value)
