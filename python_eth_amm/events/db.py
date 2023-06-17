from sqlalchemy import VARCHAR, Column, Integer, PrimaryKeyConstraint
from sqlalchemy.orm import DeclarativeBase


class EventBase(DeclarativeBase):
    __abstract__ = True
    block_number = Column(Integer, nullable=False)
    log_index = Column(Integer, nullable=False)
    transaction_hash = Column(VARCHAR(66), nullable=False)
    contract_address = Column(VARCHAR(42), index=True, nullable=False)

    __table_args__ = (PrimaryKeyConstraint("block_number", "log_index"),)
