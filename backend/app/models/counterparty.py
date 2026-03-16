from __future__ import annotations

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, Enum, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class CounterpartyKind(str, PyEnum):
    person = "person"
    merchant = "merchant"
    unknown = "unknown"
    internal = "internal"


class Counterparty(Base):
    __tablename__ = "counterparties"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    kind: Mapped[CounterpartyKind] = mapped_column(
        Enum(CounterpartyKind, name="counterparty_kind", native_enum=False),
        nullable=False,
    )
    type: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="payee")
    splits: Mapped[list["Split"]] = relationship(back_populates="internal_account")
