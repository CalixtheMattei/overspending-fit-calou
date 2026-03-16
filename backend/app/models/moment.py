from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class Moment(Base):
    __tablename__ = "moments"
    __table_args__ = (CheckConstraint("start_date <= end_date", name="ck_moments_valid_date_range"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    cover_image_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    splits: Mapped[list["Split"]] = relationship(back_populates="moment")
    candidates: Mapped[list["MomentCandidate"]] = relationship(back_populates="moment")
