"""Allow null category on splits.

Revision ID: 0005_splits_category_nullable
Revises: 0004_ledger_v2
Create Date: 2026-02-06 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0005_splits_category_nullable"
down_revision: Union[str, None] = "0004_ledger_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("splits", "category_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.alter_column("splits", "category_id", existing_type=sa.Integer(), nullable=False)
