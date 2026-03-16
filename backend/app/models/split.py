from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class Split(Base):
    __tablename__ = "splits"
    __table_args__ = (Index("ix_splits_moment_id", "moment_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    moment_id: Mapped[int | None] = mapped_column(ForeignKey("moments.id"))
    internal_account_id: Mapped[int | None] = mapped_column(ForeignKey("counterparties.id"))
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    transaction: Mapped["Transaction"] = relationship(back_populates="splits")
    category: Mapped["Category | None"] = relationship(back_populates="splits")
    moment: Mapped["Moment | None"] = relationship(back_populates="splits")
    moment_candidates: Mapped[list["MomentCandidate"]] = relationship(back_populates="split")
    internal_account: Mapped["Counterparty | None"] = relationship(
        back_populates="splits",
        foreign_keys=[internal_account_id],
    )
