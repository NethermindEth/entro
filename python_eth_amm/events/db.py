from sqlalchemy import VARCHAR, Column, Integer, PrimaryKeyConstraint
from sqlalchemy.orm import DeclarativeBase


class EventBase(DeclarativeBase):
    """
    Base Class for Events.  Contains the following columns:

        * block_number
        * log_index
        * transaction_hash
        * contract_address

    The EventBase abstract class also contains a primary key from block_number -> log_index
    """

    __abstract__ = True
    block_number = Column(Integer, nullable=False)
    log_index = Column(Integer, nullable=False)
    transaction_hash = Column(VARCHAR(66), nullable=False)
    contract_address = Column(VARCHAR(42), index=True, nullable=False)

    __table_args__ = (PrimaryKeyConstraint("block_number", "log_index"),)
