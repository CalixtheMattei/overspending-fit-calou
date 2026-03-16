"""Add category metadata fields.

Revision ID: 0006_category_meta_seed
Revises: 0005_splits_category_nullable
Create Date: 2026-02-06 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0006_category_meta_seed"
down_revision: Union[str, None] = "0005_splits_category_nullable"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "categories",
        sa.Column("color", sa.Text(), nullable=False, server_default=sa.text("'#9CA3AF'")),
    )
    op.add_column(
        "categories",
        sa.Column("icon", sa.Text(), nullable=False, server_default=sa.text("'tag'")),
    )
    op.add_column(
        "categories",
        sa.Column("is_custom", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_check_constraint(
        "ck_categories_color_hex",
        "categories",
        "color ~ '^#[0-9A-Fa-f]{6}$'",
    )


def downgrade() -> None:
    op.drop_constraint("ck_categories_color_hex", "categories", type_="check")
    op.drop_column("categories", "is_custom")
    op.drop_column("categories", "icon")
    op.drop_column("categories", "color")
