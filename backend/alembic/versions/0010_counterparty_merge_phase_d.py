"""Merge payees/internal accounts into counterparties and add suggestion ignores.

Revision ID: 0010_counterparty_merge_phase_d
Revises: 0009_transaction_manual_events
Create Date: 2026-02-18 00:00:00.000000
"""

from __future__ import annotations

import re
from typing import Any, Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0010_counterparty_merge_phase_d"
down_revision: Union[str, None] = "0009_transaction_manual_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


JSON_REWRITE_TARGETS: list[tuple[str, str]] = [
    ("rules", "action_json"),
    ("rule_runs", "result_json"),
    ("rule_run_effects", "before_json"),
    ("rule_run_effects", "after_json"),
    ("rule_run_effects", "change_json"),
    ("split_lineage", "before_json"),
    ("split_lineage", "after_json"),
    ("transaction_manual_events", "payload_json"),
]


def _canonicalize_name(value: str | None) -> str:
    cleaned = re.sub(r"\s+", " ", (value or "").strip().lower())
    return cleaned


def _rewrite_internal_account_ids(payload: Any, id_map: dict[int, int]) -> Any:
    if isinstance(payload, list):
        changed = False
        next_rows: list[Any] = []
        for item in payload:
            rewritten = _rewrite_internal_account_ids(item, id_map)
            if rewritten is not item:
                changed = True
            next_rows.append(rewritten)
        return next_rows if changed else payload

    if isinstance(payload, dict):
        changed = False
        next_obj: dict[str, Any] = {}
        for key, value in payload.items():
            next_value = value
            if key == "internal_account_id" and isinstance(value, int):
                mapped = id_map.get(value)
                if mapped is not None and mapped != value:
                    next_value = mapped
            else:
                rewritten = _rewrite_internal_account_ids(value, id_map)
                if rewritten is not value:
                    next_value = rewritten
            if next_value is not value:
                changed = True
            next_obj[key] = next_value
        return next_obj if changed else payload

    return payload


def _rewrite_json_columns(id_map: dict[int, int]) -> None:
    if not id_map:
        return

    bind = op.get_bind()
    for table_name, column_name in JSON_REWRITE_TARGETS:
        rows = bind.execute(
            sa.text(f"SELECT id, {column_name} FROM {table_name}"),
        ).mappings()

        for row in rows:
            payload = row[column_name]
            rewritten = _rewrite_internal_account_ids(payload, id_map)
            if rewritten is payload:
                continue
            bind.execute(
                sa.text(f"UPDATE {table_name} SET {column_name} = :payload WHERE id = :id"),
                {"payload": rewritten, "id": row["id"]},
            )


def _drop_constraint_if_exists(table_name: str, constraint_name: str) -> None:
    op.execute(sa.text(f'ALTER TABLE "{table_name}" DROP CONSTRAINT IF EXISTS "{constraint_name}"'))


def upgrade() -> None:
    op.create_table(
        "counterparties",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Enum("person", "merchant", "unknown", "internal", name="counterparty_kind", native_enum=False), nullable=False),
        sa.Column("type", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "payee_suggestion_ignores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical_name", name="uq_payee_suggestion_ignores_canonical_name"),
    )

    bind = op.get_bind()

    payee_rows = bind.execute(
        sa.text(
            """
            SELECT id, name, kind, canonical_name, created_at
            FROM payees
            ORDER BY id
            """
        )
    ).mappings()

    for row in payee_rows:
        bind.execute(
            sa.text(
                """
                INSERT INTO counterparties
                    (id, name, canonical_name, kind, type, position, is_archived, created_at)
                VALUES
                    (:id, :name, :canonical_name, :kind, NULL, 0, false, :created_at)
                """
            ),
            {
                "id": row["id"],
                "name": row["name"],
                "canonical_name": row["canonical_name"],
                "kind": row["kind"],
                "created_at": row["created_at"],
            },
        )

    max_payee_id = bind.execute(sa.text("SELECT COALESCE(MAX(id), 0) FROM payees")).scalar_one()
    offset = int(max_payee_id or 0)

    internal_rows = bind.execute(
        sa.text(
            """
            SELECT id, name, type, position, is_archived, created_at
            FROM internal_accounts
            ORDER BY id
            """
        )
    ).mappings()
    id_map: dict[int, int] = {}

    for row in internal_rows:
        old_id = int(row["id"])
        new_id = offset + old_id
        id_map[old_id] = new_id
        canonical_name = _canonicalize_name(row["name"]) or f"internal-{new_id}"
        bind.execute(
            sa.text(
                """
                INSERT INTO counterparties
                    (id, name, canonical_name, kind, type, position, is_archived, created_at)
                VALUES
                    (:id, :name, :canonical_name, 'internal', :type, :position, :is_archived, :created_at)
                """
            ),
            {
                "id": new_id,
                "name": row["name"],
                "canonical_name": canonical_name,
                "type": row["type"],
                "position": row["position"],
                "is_archived": row["is_archived"],
                "created_at": row["created_at"],
            },
        )

    # Ensure uniqueness across copied payees and internal counterparties.
    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT id,
                       canonical_name,
                       ROW_NUMBER() OVER (PARTITION BY canonical_name ORDER BY id) AS rn
                FROM counterparties
            )
            UPDATE counterparties c
            SET canonical_name = c.canonical_name || '-' || c.id
            FROM ranked r
            WHERE c.id = r.id
              AND r.rn > 1
            """
        )
    )
    op.create_unique_constraint("uq_counterparties_canonical_name", "counterparties", ["canonical_name"])

    _drop_constraint_if_exists("transactions", "transactions_payee_id_fkey")
    _drop_constraint_if_exists("splits", "fk_splits_internal_account_id")
    _drop_constraint_if_exists("splits", "splits_internal_account_id_fkey")

    if offset:
        bind.execute(
            sa.text(
                """
                UPDATE splits
                SET internal_account_id = internal_account_id + :offset
                WHERE internal_account_id IS NOT NULL
                """
            ),
            {"offset": offset},
        )

    _rewrite_json_columns(id_map)

    op.create_foreign_key(
        "fk_transactions_payee_id_counterparties",
        "transactions",
        "counterparties",
        ["payee_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_splits_internal_account_id_counterparties",
        "splits",
        "counterparties",
        ["internal_account_id"],
        ["id"],
    )

    op.rename_table("payees", "payees_legacy")
    op.rename_table("internal_accounts", "internal_accounts_legacy")


def downgrade() -> None:
    bind = op.get_bind()

    _drop_constraint_if_exists("transactions", "fk_transactions_payee_id_counterparties")
    _drop_constraint_if_exists("splits", "fk_splits_internal_account_id_counterparties")

    op.rename_table("payees_legacy", "payees")
    op.rename_table("internal_accounts_legacy", "internal_accounts")

    max_payee_id = bind.execute(sa.text("SELECT COALESCE(MAX(id), 0) FROM payees")).scalar_one()
    offset = int(max_payee_id or 0)

    internal_rows = bind.execute(sa.text("SELECT id FROM internal_accounts ORDER BY id")).mappings()
    reverse_id_map: dict[int, int] = {}
    for row in internal_rows:
        old_id = int(row["id"])
        reverse_id_map[old_id + offset] = old_id

    if offset:
        bind.execute(
            sa.text(
                """
                UPDATE splits
                SET internal_account_id = internal_account_id - :offset
                WHERE internal_account_id IS NOT NULL
                """
            ),
            {"offset": offset},
        )

    _rewrite_json_columns(reverse_id_map)

    bind.execute(
        sa.text(
            """
            UPDATE transactions
            SET payee_id = NULL
            WHERE payee_id IS NOT NULL
              AND payee_id NOT IN (SELECT id FROM payees)
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE splits
            SET internal_account_id = NULL
            WHERE internal_account_id IS NOT NULL
              AND internal_account_id NOT IN (SELECT id FROM internal_accounts)
            """
        )
    )

    op.create_foreign_key(
        "transactions_payee_id_fkey",
        "transactions",
        "payees",
        ["payee_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_splits_internal_account_id",
        "splits",
        "internal_accounts",
        ["internal_account_id"],
        ["id"],
    )

    op.drop_table("counterparties")
    op.drop_table("payee_suggestion_ignores")
