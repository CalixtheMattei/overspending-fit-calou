from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class ImportRowStatus(str, PyEnum):
    created = "created"
    linked = "linked"
    error = "error"


class Import(Base):
    __tablename__ = "imports"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str | None] = mapped_column(Text)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    row_count: Mapped[int] = mapped_column(default=0, nullable=False)
    created_count: Mapped[int] = mapped_column(default=0, nullable=False)
    linked_count: Mapped[int] = mapped_column(default=0, nullable=False)
    duplicate_count: Mapped[int] = mapped_column(default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(default=0, nullable=False)

    account: Mapped["Account"] = relationship(back_populates="imports")
    rows: Mapped[list["ImportRow"]] = relationship(back_populates="import_", cascade="all, delete-orphan")


class ImportRow(Base):
    __tablename__ = "import_rows"
    __table_args__ = (UniqueConstraint("import_id", "row_hash", name="uq_import_rows_import_id_row_hash"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    import_id: Mapped[int] = mapped_column(ForeignKey("imports.id"), nullable=False)
    row_hash: Mapped[str] = mapped_column(Text, nullable=False)
    raw_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    date_op: Mapped[date | None] = mapped_column(Date)
    date_val: Mapped[date | None] = mapped_column(Date)
    label_raw: Mapped[str] = mapped_column(Text, nullable=False)
    supplier_raw: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="EUR")
    category_raw: Mapped[str | None] = mapped_column(Text)
    category_parent_raw: Mapped[str | None] = mapped_column(Text)
    comment_raw: Mapped[str | None] = mapped_column(Text)
    balance_after: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    status: Mapped[ImportRowStatus] = mapped_column(
        Enum(ImportRowStatus, name="import_row_status", native_enum=False),
        nullable=False,
        server_default=ImportRowStatus.created.value,
        default=ImportRowStatus.created,
    )
    error_code: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    import_: Mapped["Import"] = relationship(back_populates="rows")
    link: Mapped["ImportRowLink | None"] = relationship(back_populates="import_row", uselist=False, cascade="all, delete-orphan")


class ImportRowLink(Base):
    __tablename__ = "import_row_links"
    __table_args__ = (Index("ix_import_row_links_transaction_id", "transaction_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    import_row_id: Mapped[int] = mapped_column(ForeignKey("import_rows.id"), nullable=False, unique=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), nullable=False)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    import_row: Mapped["ImportRow"] = relationship(back_populates="link")
    transaction: Mapped["Transaction"] = relationship(back_populates="import_row_links")
