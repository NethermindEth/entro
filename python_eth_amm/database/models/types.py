from typing import Annotated

from sqlalchemy import BigInteger, Numeric, Text
from sqlalchemy.dialects.postgresql import BYTEA
from sqlalchemy.orm import mapped_column

# Binary Data is Represented as a String of Hex Digits
# -- If database backend supports binary data, hex strings will be stored as byte arrays.
# -- Since data applications are network & io bound, the performance impact of hex strings over bytes is negligible.

AddressPK = Annotated[
    str, mapped_column(Text(42).with_variant(BYTEA, "postgresql"), primary_key=True)
]
BlockNumberPK = Annotated[int, mapped_column(BigInteger, primary_key=True)]
Hash32PK = Annotated[
    str, mapped_column(Text(66).with_variant(BYTEA, "postgresql"), primary_key=True)
]


IndexedAddress = Annotated[
    str,
    mapped_column(
        Text(42).with_variant(BYTEA, "postgresql"), index=True, nullable=False
    ),
]
IndexedNullableAddress = Annotated[
    str,
    mapped_column(
        Text(42).with_variant(BYTEA, "postgresql"), index=True, nullable=True
    ),
]
IndexedBlockNumber = Annotated[
    int, mapped_column(BigInteger, nullable=False, index=True)
]
IndexedHash32 = Annotated[
    str,
    mapped_column(
        Text(66).with_variant(BYTEA, "postgresql"), index=True, nullable=False
    ),
]

UInt256 = Annotated[int, mapped_column(Numeric(78, 0))]
UInt128 = Annotated[int, mapped_column(Numeric(39, 0))]
UInt160 = Annotated[int, mapped_column(Numeric(49, 0))]

Hash32 = Annotated[str, mapped_column(Text(66).with_variant(BYTEA, "postgresql"))]
Address = Annotated[str, mapped_column(Text(42).with_variant(BYTEA, "postgresql"))]
CalldataBytes = Annotated[
    str, mapped_column(Text().with_variant(BYTEA, "postgresql"), nullable=True)
]
