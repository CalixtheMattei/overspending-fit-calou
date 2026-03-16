"""Rules engine lineage and source metadata.

Revision ID: 0007_rules_engine_lineage
Revises: 0006_category_meta_seed
Create Date: 2026-02-06 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0007_rules_engine_lineage"
down_revision: Union[str, None] = "0006_category_meta_seed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("categories", sa.Column("source", sa.Text(), nullable=True))
    op.add_column("categories", sa.Column("source_ref", sa.Text(), nullable=True))
    op.create_unique_constraint(
        "uq_categories_source_source_ref",
        "categories",
        ["source", "source_ref"],
    )

    op.add_column("rules", sa.Column("source", sa.Text(), nullable=True))
    op.add_column("rules", sa.Column("source_ref", sa.Text(), nullable=True))
    op.add_column(
        "rules",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_unique_constraint(
        "uq_rules_source_source_ref",
        "rules",
        ["source", "source_ref"],
    )

    op.create_table(
        "rule_run_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trigger_type", sa.Text(), nullable=False),
        sa.Column("scope_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("allow_overwrite", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "rule_run_effects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.Text(), nullable=True),
        sa.Column("before_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("change_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["rule_run_batches.id"]),
        sa.ForeignKeyConstraint(["rule_id"], ["rules.id"]),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rule_run_effects_batch_id", "rule_run_effects", ["batch_id"])
    op.create_index("ix_rule_run_effects_rule_id", "rule_run_effects", ["rule_id"])
    op.create_index("ix_rule_run_effects_transaction_id", "rule_run_effects", ["transaction_id"])

    op.create_table(
        "split_lineage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("split_id", sa.Integer(), nullable=True),
        sa.Column("effect_id", sa.Integer(), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("before_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["effect_id"], ["rule_run_effects.id"]),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_split_lineage_transaction_id", "split_lineage", ["transaction_id"])
    op.create_index("ix_split_lineage_effect_id", "split_lineage", ["effect_id"])


def downgrade() -> None:
    op.drop_index("ix_split_lineage_effect_id", table_name="split_lineage")
    op.drop_index("ix_split_lineage_transaction_id", table_name="split_lineage")
    op.drop_table("split_lineage")

    op.drop_index("ix_rule_run_effects_transaction_id", table_name="rule_run_effects")
    op.drop_index("ix_rule_run_effects_rule_id", table_name="rule_run_effects")
    op.drop_index("ix_rule_run_effects_batch_id", table_name="rule_run_effects")
    op.drop_table("rule_run_effects")
    op.drop_table("rule_run_batches")

    op.drop_constraint("uq_rules_source_source_ref", "rules", type_="unique")
    op.drop_column("rules", "updated_at")
    op.drop_column("rules", "source_ref")
    op.drop_column("rules", "source")

    op.drop_constraint("uq_categories_source_source_ref", "categories", type_="unique")
    op.drop_column("categories", "source_ref")
    op.drop_column("categories", "source")
