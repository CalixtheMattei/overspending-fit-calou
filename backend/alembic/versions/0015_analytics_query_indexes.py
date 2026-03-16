"""Add indexes for analytics query performance.

Revision ID: 0015_analytics_indexes
Revises: 0014_cat_sort_order
Create Date: 2026-03-01 00:00:01.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0015_analytics_indexes"
down_revision: Union[str, None] = "0014_cat_sort_order"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_splits_transaction_id", "splits", ["transaction_id"])
    op.create_index("ix_splits_category_id", "splits", ["category_id"])
    op.create_index("ix_transactions_posted_at", "transactions", ["posted_at"])
    op.create_index("ix_transactions_type_posted_at", "transactions", ["type", "posted_at"])


def downgrade() -> None:
    op.drop_index("ix_transactions_type_posted_at", table_name="transactions")
    op.drop_index("ix_transactions_posted_at", table_name="transactions")
    op.drop_index("ix_splits_category_id", table_name="splits")
    op.drop_index("ix_splits_transaction_id", table_name="splits")
