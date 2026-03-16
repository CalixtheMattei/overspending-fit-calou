from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class TransactionType(str, PyEnum):
    expense = "expense"
    income = "income"
    transfer = "transfer"
    refund = "refund"
    adjustment = "adjustment"


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (Index("ix_transactions_operation_at", "operation_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    posted_at: Mapped[date] = mapped_column(Date, nullable=False)
    operation_at: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    label_raw: Mapped[str] = mapped_column(Text, nullable=False)
    label_norm: Mapped[str] = mapped_column(Text, nullable=False)
    supplier_raw: Mapped[str | None] = mapped_column(Text)
    payee_id: Mapped[int | None] = mapped_column(ForeignKey("counterparties.id"))
    type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, name="transaction_type", native_enum=False), nullable=False
    )
    fingerprint: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    account: Mapped["Account"] = relationship(back_populates="transactions")
    payee: Mapped["Counterparty | None"] = relationship(
        back_populates="transactions",
        foreign_keys=[payee_id],
    )
    splits: Mapped[list["Split"]] = relationship(back_populates="transaction", cascade="all, delete-orphan")
    import_row_links: Mapped[list["ImportRowLink"]] = relationship(back_populates="transaction")
    rule_runs: Mapped[list["RuleRun"]] = relationship(back_populates="transaction", cascade="all, delete-orphan")
    rule_effects: Mapped[list["RuleRunEffect"]] = relationship(back_populates="transaction", cascade="all, delete-orphan")
    split_lineage_entries: Mapped[list["SplitLineage"]] = relationship(
        back_populates="transaction",
        cascade="all, delete-orphan",
    )
    manual_events: Mapped[list["TransactionManualEvent"]] = relationship(
        back_populates="transaction",
        cascade="all, delete-orphan",
    )
