"""Fix counterparties id sequence to match existing data

Revision ID: 0011
Revises: 0010
"""

from alembic import op

revision = "0011_fix_cpty_id_seq"
down_revision = "0010_counterparty_merge_phase_d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "SELECT setval("
        "  pg_get_serial_sequence('counterparties', 'id'), "
        "  COALESCE((SELECT MAX(id) FROM counterparties), 0) + 1, "
        "  false"
        ")"
    )


def downgrade() -> None:
    pass
