"""Add sort_order column and index to categories.

Revision ID: 0014_cat_sort_order
Revises: 0013_cat_norm_unique
Create Date: 2026-02-28 00:00:01.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0014_cat_sort_order"
down_revision: Union[str, None] = "0013_cat_norm_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "categories",
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.create_index(
        "ix_categories_parent_sort_order",
        "categories",
        ["parent_id", "sort_order", "name"],
    )


def downgrade() -> None:
    op.drop_index("ix_categories_parent_sort_order", table_name="categories")
    op.drop_column("categories", "sort_order")
