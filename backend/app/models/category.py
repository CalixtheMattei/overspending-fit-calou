from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


def _normalize_category_name(name: str) -> str:
    """Normalize a category name for uniqueness comparison."""
    normalized = re.sub(r"[^a-z0-9]+", " ", name.strip().lower())
    return re.sub(r"\s+", " ", normalized).strip()


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint(
            "parent_id",
            "normalized_name",
            name="uq_categories_parent_normalized_name",
        ),
        Index("ix_categories_parent_normalized_name", "parent_id", "normalized_name"),
        Index("ix_categories_parent_sort_order", "parent_id", "sort_order", "name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str] = mapped_column(Text, nullable=False, default="#9CA3AF", server_default="#9CA3AF")
    icon: Mapped[str] = mapped_column(Text, nullable=False, default="tag", server_default="tag")
    is_custom: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    source: Mapped[str | None] = mapped_column(Text)
    source_ref: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    parent: Mapped["Category | None"] = relationship(remote_side="Category.id", back_populates="children")
    children: Mapped[list["Category"]] = relationship(back_populates="parent")
    splits: Mapped[list["Split"]] = relationship(back_populates="category")
