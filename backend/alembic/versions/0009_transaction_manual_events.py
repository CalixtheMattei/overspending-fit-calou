"""Add transaction manual events table for split edit provenance.

Revision ID: 0009_transaction_manual_events
Revises: 0008_refund_category_backfill
Create Date: 2026-02-17 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0009_transaction_manual_events"
down_revision: Union[str, None] = "0008_refund_category_backfill"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "transaction_manual_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_transaction_manual_events_transaction_id_id",
        "transaction_manual_events",
        ["transaction_id", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_transaction_manual_events_transaction_id_id", table_name="transaction_manual_events")
    op.drop_table("transaction_manual_events")
