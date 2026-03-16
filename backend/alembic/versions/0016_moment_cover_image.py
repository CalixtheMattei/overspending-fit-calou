"""Add cover_image_url column to moments.

Revision ID: 0016_moment_cover_image
Revises: 0015_analytics_indexes
Create Date: 2026-03-05 00:00:01.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016_moment_cover_image"
down_revision: Union[str, None] = "0015_analytics_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("moments", sa.Column("cover_image_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("moments", "cover_image_url")
