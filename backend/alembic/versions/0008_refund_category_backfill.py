"""Backfill refund categories to transaction type and unknown category.

Revision ID: 0008_refund_category_backfill
Revises: 0007_rules_engine_lineage
Create Date: 2026-02-09 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0008_refund_category_backfill"
down_revision: Union[str, None] = "0007_rules_engine_lineage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    backfill_refund_categories(op.get_bind())


def backfill_refund_categories(bind) -> None:

    categories = sa.table(
        "categories",
        sa.column("id", sa.Integer()),
        sa.column("name", sa.Text()),
        sa.column("source", sa.Text()),
        sa.column("source_ref", sa.Text()),
        sa.column("parent_id", sa.Integer()),
    )
    splits = sa.table(
        "splits",
        sa.column("id", sa.Integer()),
        sa.column("transaction_id", sa.Integer()),
        sa.column("category_id", sa.Integer()),
    )
    transactions = sa.table(
        "transactions",
        sa.column("id", sa.Integer()),
        sa.column("type", sa.Text()),
    )

    refund_source_refs = ["25", "31442", "31443", "31444", "31445"]
    refund_names = ["refunds", "product_returns", "tax_refunds", "warranty_claims", "insurance_payouts"]

    refund_ids = {
        int(row[0])
        for row in bind.execute(
            sa.select(categories.c.id).where(
                sa.or_(
                    sa.and_(
                        categories.c.source == "native_catalog",
                        categories.c.source_ref.in_(refund_source_refs),
                    ),
                    categories.c.name.in_(refund_names),
                )
            )
        ).fetchall()
    }
    if not refund_ids:
        return

    unknown_row = bind.execute(
        sa.select(categories.c.id)
        .where(
            sa.or_(
                sa.and_(
                    categories.c.source == "native_catalog",
                    categories.c.source_ref == "35",
                ),
                sa.and_(
                    categories.c.name == "unknown",
                    categories.c.parent_id.is_(None),
                ),
            )
        )
        .order_by(categories.c.id.asc())
        .limit(1)
    ).first()
    if unknown_row is None:
        raise RuntimeError("Missing unknown category; cannot backfill refund categories")
    unknown_category_id = int(unknown_row[0])

    affected_transaction_ids = (
        sa.select(splits.c.transaction_id)
        .where(splits.c.category_id.in_(refund_ids))
        .distinct()
    )

    bind.execute(
        sa.update(transactions)
        .where(transactions.c.id.in_(affected_transaction_ids))
        .values(type="refund")
    )
    bind.execute(
        sa.update(splits)
        .where(splits.c.category_id.in_(refund_ids))
        .values(category_id=unknown_category_id)
    )


def downgrade() -> None:
    # Deterministic downgrade is not possible because original split categories are lost.
    pass
