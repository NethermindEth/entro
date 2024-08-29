from typing import Annotated

from sqlalchemy import BigInteger, Numeric, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Binary Data is Represented as a String of Hex Digits
# -- If database backend supports binary data, hex strings will be stored as byte arrays.
# -- Since data applications are network & io bound, the performance impact of hex strings over bytes is negligible.

AddressPK = Annotated[str, mapped_column(Text, primary_key=True)]
BlockNumberPK = Annotated[int, mapped_column(BigInteger, primary_key=True)]
Hash32PK = Annotated[str, mapped_column(Text, primary_key=True)]


IndexedAddress = Annotated[str, mapped_column(Text, index=True, nullable=False)]
IndexedNullableAddress = Annotated[str, mapped_column(Text, index=True, nullable=True)]
IndexedBlockNumber = Annotated[int, mapped_column(BigInteger, nullable=False, index=True)]
IndexedHash32 = Annotated[str, mapped_column(Text, index=True, nullable=False)]

UInt256 = Annotated[int, mapped_column(Numeric(78, 0))]
UInt128 = Annotated[int, mapped_column(Numeric(39, 0))]
UInt160 = Annotated[int, mapped_column(Numeric(49, 0))]

Hash32 = Annotated[str, mapped_column(Text)]
Address = Annotated[str, mapped_column(Text)]
CalldataBytes = Annotated[str, mapped_column(Text, nullable=True)]


class Base(DeclarativeBase):
    """Base class for utility tables"""


class AbstractBlock(Base):
    """Abstract base class for block tables"""

    __abstract__ = True

    block_number: Mapped[BlockNumberPK]
    block_hash: Mapped[Hash32]
    timestamp: Mapped[int] = mapped_column(BigInteger, nullable=False)


class AbstractTransaction(Base):
    """Abstract base class for transaction tables"""

    __abstract__ = True

    transaction_hash: Mapped[Hash32PK]
    block_number: Mapped[IndexedBlockNumber]
    transaction_index: Mapped[int]
    timestamp: Mapped[int] = mapped_column(BigInteger)

    gas_used: Mapped[int | None] = mapped_column(Numeric, nullable=True)


class AbstractEvent(Base):
    """Abstract base class for event tables"""

    __abstract__ = True

    block_number: Mapped[IndexedBlockNumber]
    event_index: Mapped[int]
    transaction_index: Mapped[int]
    contract_address: Mapped[IndexedAddress]


class AbstractTrace(Base):
    """
    Abstract base class for trace tables
    """

    __abstract__ = True

    block_number: Mapped[IndexedBlockNumber]
    transaction_hash: Mapped[IndexedHash32]
    transaction_index: Mapped[int]
    trace_address: Mapped[list[int]]

    gas_used: Mapped[int]
    error: Mapped[str]


class AbstractERC20Transfer(Base):
    """
    Abstract base class for transfer tables
    """

    __abstract__ = True

    block_number: Mapped[IndexedBlockNumber]
    transaction_hash: Mapped[Hash32]
    transaction_index: Mapped[int]
    event_index: Mapped[int]

    token_address: Mapped[IndexedAddress]
    from_address: Mapped[IndexedAddress]
    to_address: Mapped[IndexedAddress]
    value: Mapped[UInt256]
