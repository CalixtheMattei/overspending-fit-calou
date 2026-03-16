"""Merge divergent 0011 migration heads.

Revision ID: 0012_merge_0011_heads
Revises: 0011_fix_cpty_id_seq, 0011_moments_v2_schema
Create Date: 2026-02-24 00:00:00.000000
"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "0012_merge_0011_heads"
down_revision: Union[str, Sequence[str], None] = (
    "0011_fix_cpty_id_seq",
    "0011_moments_v2_schema",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
