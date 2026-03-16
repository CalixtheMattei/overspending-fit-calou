from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class MomentCandidate(Base):
    __tablename__ = "moment_candidates"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected')",
            name="ck_moment_candidates_status",
        ),
        UniqueConstraint("moment_id", "split_id", name="uq_moment_candidates_moment_id_split_id"),
        Index("ix_moment_candidates_moment_status", "moment_id", "status"),
        Index("ix_moment_candidates_split_id", "split_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    moment_id: Mapped[int] = mapped_column(ForeignKey("moments.id", ondelete="CASCADE"), nullable=False)
    split_id: Mapped[int] = mapped_column(ForeignKey("splits.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending", default="pending")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)

    moment: Mapped["Moment"] = relationship(back_populates="candidates")
    split: Mapped["Split"] = relationship(back_populates="moment_candidates")
