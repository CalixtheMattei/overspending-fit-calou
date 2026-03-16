"""Add normalized_name column and sibling uniqueness constraint to categories.

Revision ID: 0013_cat_norm_unique
Revises: 0012_merge_0011_heads
Create Date: 2026-02-28 00:00:00.000000
"""

from typing import Sequence, Union

import re

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "0013_cat_norm_unique"
down_revision: Union[str, None] = "0012_merge_0011_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _normalize_name(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", name.strip().lower())
    return re.sub(r"\s+", " ", normalized).strip()


def upgrade() -> None:
    # Add the column as nullable first
    op.add_column(
        "categories",
        sa.Column("normalized_name", sa.Text(), nullable=True),
    )

    # Backfill normalized_name from name for all existing rows
    conn = op.get_bind()
    rows = conn.execute(text("SELECT id, name FROM categories")).fetchall()
    for row_id, name in rows:
        normalized = _normalize_name(name)
        conn.execute(
            text("UPDATE categories SET normalized_name = :norm WHERE id = :id"),
            {"norm": normalized, "id": row_id},
        )

    # Add the unique constraint and index
    op.create_unique_constraint(
        "uq_categories_parent_normalized_name",
        "categories",
        ["parent_id", "normalized_name"],
    )
    op.create_index(
        "ix_categories_parent_normalized_name",
        "categories",
        ["parent_id", "normalized_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_categories_parent_normalized_name", table_name="categories")
    op.drop_constraint("uq_categories_parent_normalized_name", "categories", type_="unique")
    op.drop_column("categories", "normalized_name")
