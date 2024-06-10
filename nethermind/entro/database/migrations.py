from sqlalchemy import Engine
from sqlalchemy.schema import CreateSchema


def migrate_up(db_engine: Engine):
    """Create Sqlalchemy DB Tables"""
    # pylint: disable=import-outside-toplevel,unused-import
    import nethermind.entro.database.models.ethereum
    import nethermind.entro.database.models.prices
    import nethermind.entro.database.models.internal
    import nethermind.entro.database.models.starknet
    import nethermind.entro.database.models.uniswap
    import nethermind.entro.database.models.zk_sync

    from .models.base import Base

    # pylint: enable=import-outside-toplevel,unused-import

    schemas = {table.schema for table in Base.metadata.tables.values()}
    with db_engine.connect() as conn:
        for schema_name in schemas:
            conn.execute(CreateSchema(schema_name, if_not_exists=True))

        conn.commit()

    Base.metadata.create_all(bind=db_engine)
