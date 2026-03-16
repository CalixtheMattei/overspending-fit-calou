"""Add import row statuses and import stats counts.

Revision ID: 0002_import_status_and_counts
Revises: 0001_initial_schema
Create Date: 2026-02-03 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0002_import_status_and_counts"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("imports", sa.Column("row_count", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("imports", sa.Column("created_count", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("imports", sa.Column("linked_count", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("imports", sa.Column("duplicate_count", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("imports", sa.Column("error_count", sa.Integer(), server_default=sa.text("0"), nullable=False))

    op.add_column(
        "import_rows",
        sa.Column(
            "status",
            sa.Enum("created", "linked", "error", name="import_row_status", native_enum=False),
            server_default=sa.text("'created'"),
            nullable=False,
        ),
    )
    op.add_column("import_rows", sa.Column("error_code", sa.Text(), nullable=True))
    op.add_column("import_rows", sa.Column("error_message", sa.Text(), nullable=True))

    op.alter_column("import_rows", "date_op", existing_type=sa.Date(), nullable=True)
    op.alter_column("import_rows", "date_val", existing_type=sa.Date(), nullable=True)
    op.alter_column("import_rows", "amount", existing_type=sa.Numeric(12, 2), nullable=True)


def downgrade() -> None:
    op.alter_column("import_rows", "amount", existing_type=sa.Numeric(12, 2), nullable=False)
    op.alter_column("import_rows", "date_val", existing_type=sa.Date(), nullable=False)
    op.alter_column("import_rows", "date_op", existing_type=sa.Date(), nullable=False)

    op.drop_column("import_rows", "error_message")
    op.drop_column("import_rows", "error_code")
    op.drop_column("import_rows", "status")

    op.drop_column("imports", "error_count")
    op.drop_column("imports", "duplicate_count")
    op.drop_column("imports", "linked_count")
    op.drop_column("imports", "created_count")
    op.drop_column("imports", "row_count")
