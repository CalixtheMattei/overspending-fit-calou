"""Add import file storage path.

Revision ID: 0003_import_file_path
Revises: 0002_import_status_and_counts
Create Date: 2026-02-04 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0003_import_file_path"
down_revision: Union[str, None] = "0002_import_status_and_counts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("imports", sa.Column("file_path", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("imports", "file_path")
