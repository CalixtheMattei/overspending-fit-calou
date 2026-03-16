"""Ledger v2 schema updates.

Revision ID: 0004_ledger_v2
Revises: 0003_import_file_path
Create Date: 2026-02-04 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0004_ledger_v2"
down_revision: Union[str, None] = "0003_import_file_path"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "internal_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.add_column("splits", sa.Column("internal_account_id", sa.Integer(), nullable=True))
    op.add_column("splits", sa.Column("position", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.create_foreign_key(
        "fk_splits_internal_account_id",
        "splits",
        "internal_accounts",
        ["internal_account_id"],
        ["id"],
    )

    op.add_column("transactions", sa.Column("comment", sa.Text(), nullable=True))

    op.execute(
        r"""
        UPDATE payees
        SET canonical_name = lower(trim(regexp_replace(name, '\s+', ' ', 'g')))
        """
    )

    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   canonical_name,
                   ROW_NUMBER() OVER (PARTITION BY canonical_name ORDER BY id) AS rn
            FROM payees
        )
        UPDATE payees p
        SET canonical_name = p.canonical_name || '-' || p.id
        FROM ranked r
        WHERE p.id = r.id AND r.rn > 1
        """
    )

    op.alter_column("payees", "canonical_name", nullable=False)
    op.create_unique_constraint("uq_payees_canonical_name", "payees", ["canonical_name"])

    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (PARTITION BY transaction_id ORDER BY id) - 1 AS pos
            FROM splits
        )
        UPDATE splits s
        SET position = ranked.pos
        FROM ranked
        WHERE s.id = ranked.id
        """
    )


def downgrade() -> None:
    op.drop_constraint("uq_payees_canonical_name", "payees", type_="unique")
    op.alter_column("payees", "canonical_name", nullable=True)

    op.drop_column("transactions", "comment")

    op.drop_constraint("fk_splits_internal_account_id", "splits", type_="foreignkey")
    op.drop_column("splits", "position")
    op.drop_column("splits", "internal_account_id")

    op.drop_table("internal_accounts")
