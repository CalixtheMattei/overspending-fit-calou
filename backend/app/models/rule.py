from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source: Mapped[str | None] = mapped_column(Text)
    source_ref: Mapped[str | None] = mapped_column(Text)
    matcher_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    action_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    runs: Mapped[list["RuleRun"]] = relationship(back_populates="rule", cascade="all, delete-orphan")
    run_effects: Mapped[list["RuleRunEffect"]] = relationship(back_populates="rule", cascade="all, delete-orphan")


class RuleRun(Base):
    __tablename__ = "rule_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), nullable=False)
    rule_id: Mapped[int] = mapped_column(ForeignKey("rules.id"), nullable=False)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    result_json: Mapped[dict] = mapped_column(JSONB, nullable=False)

    transaction: Mapped["Transaction"] = relationship(back_populates="rule_runs")
    rule: Mapped["Rule"] = relationship(back_populates="runs")


class RuleRunBatch(Base):
    __tablename__ = "rule_run_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    trigger_type: Mapped[str] = mapped_column(Text, nullable=False)
    scope_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    allow_overwrite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str | None] = mapped_column(Text)
    summary_json: Mapped[dict | None] = mapped_column(JSONB)

    effects: Mapped[list["RuleRunEffect"]] = relationship(back_populates="batch", cascade="all, delete-orphan")


class RuleRunEffect(Base):
    __tablename__ = "rule_run_effects"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("rule_run_batches.id"), nullable=False)
    rule_id: Mapped[int] = mapped_column(ForeignKey("rules.id"), nullable=False)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    reason_code: Mapped[str | None] = mapped_column(Text)
    before_json: Mapped[dict | None] = mapped_column(JSONB)
    after_json: Mapped[dict | None] = mapped_column(JSONB)
    change_json: Mapped[dict | None] = mapped_column(JSONB)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    batch: Mapped["RuleRunBatch"] = relationship(back_populates="effects")
    rule: Mapped["Rule"] = relationship(back_populates="run_effects")
    transaction: Mapped["Transaction"] = relationship(back_populates="rule_effects")
    split_lineage: Mapped[list["SplitLineage"]] = relationship(back_populates="effect", cascade="all, delete-orphan")


class SplitLineage(Base):
    __tablename__ = "split_lineage"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), nullable=False)
    split_id: Mapped[int | None] = mapped_column(Integer)
    effect_id: Mapped[int] = mapped_column(ForeignKey("rule_run_effects.id"), nullable=False)
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    before_json: Mapped[dict | None] = mapped_column(JSONB)
    after_json: Mapped[dict | None] = mapped_column(JSONB)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    transaction: Mapped["Transaction"] = relationship(back_populates="split_lineage_entries")
    effect: Mapped["RuleRunEffect"] = relationship(back_populates="split_lineage")
