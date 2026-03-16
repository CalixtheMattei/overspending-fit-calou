"""PRD-005 Moments v2 schema foundation.

Revision ID: 0011_moments_v2_schema
Revises: 0010_counterparty_merge_phase_d
Create Date: 2026-02-21 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0011_moments_v2_schema"
down_revision: Union[str, None] = "0010_counterparty_merge_phase_d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("moments", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(sa.text("UPDATE moments SET updated_at = now() WHERE updated_at IS NULL"))
    op.alter_column(
        "moments",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    op.create_check_constraint("ck_moments_valid_date_range", "moments", "start_date <= end_date")

    op.create_table(
        "moment_candidates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("moment_id", sa.Integer(), nullable=False),
        sa.Column("split_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected')",
            name="ck_moment_candidates_status",
        ),
        sa.ForeignKeyConstraint(["moment_id"], ["moments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["split_id"], ["splits.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("moment_id", "split_id", name="uq_moment_candidates_moment_id_split_id"),
    )
    op.create_index("ix_moment_candidates_moment_status", "moment_candidates", ["moment_id", "status"])
    op.create_index("ix_moment_candidates_split_id", "moment_candidates", ["split_id"])

    op.create_index("ix_splits_moment_id", "splits", ["moment_id"])
    op.create_index("ix_transactions_operation_at", "transactions", ["operation_at"])


def downgrade() -> None:
    op.drop_index("ix_transactions_operation_at", table_name="transactions")
    op.drop_index("ix_splits_moment_id", table_name="splits")

    op.drop_index("ix_moment_candidates_split_id", table_name="moment_candidates")
    op.drop_index("ix_moment_candidates_moment_status", table_name="moment_candidates")
    op.drop_table("moment_candidates")

    op.drop_constraint("ck_moments_valid_date_range", "moments", type_="check")
    op.alter_column(
        "moments",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        server_default=None,
    )
    op.drop_column("moments", "updated_at")
