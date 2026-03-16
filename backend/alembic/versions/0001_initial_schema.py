"""Initial schema.

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-02-03 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_num", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("institution", sa.Text(), nullable=True),
        sa.Column("currency", sa.String(length=3), server_default=sa.text("'EUR'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_num", name="uq_accounts_account_num"),
    )

    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["categories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "moments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "payees",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Enum("person", "merchant", "unknown", name="payee_kind", native_enum=False), nullable=False),
        sa.Column("canonical_name", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("matcher_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("action_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "imports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("file_hash", sa.Text(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("posted_at", sa.Date(), nullable=False),
        sa.Column("operation_at", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("label_raw", sa.Text(), nullable=False),
        sa.Column("label_norm", sa.Text(), nullable=False),
        sa.Column("supplier_raw", sa.Text(), nullable=True),
        sa.Column("payee_id", sa.Integer(), nullable=True),
        sa.Column(
            "type",
            sa.Enum(
                "expense",
                "income",
                "transfer",
                "refund",
                "adjustment",
                name="transaction_type",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["payee_id"], ["payees.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fingerprint", name="uq_transactions_fingerprint"),
    )

    op.create_table(
        "import_rows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("import_id", sa.Integer(), nullable=False),
        sa.Column("row_hash", sa.Text(), nullable=False),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("date_op", sa.Date(), nullable=False),
        sa.Column("date_val", sa.Date(), nullable=False),
        sa.Column("label_raw", sa.Text(), nullable=False),
        sa.Column("supplier_raw", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default=sa.text("'EUR'"), nullable=False),
        sa.Column("category_raw", sa.Text(), nullable=True),
        sa.Column("category_parent_raw", sa.Text(), nullable=True),
        sa.Column("comment_raw", sa.Text(), nullable=True),
        sa.Column("balance_after", sa.Numeric(14, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["import_id"], ["imports.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("import_id", "row_hash", name="uq_import_rows_import_id_row_hash"),
    )

    op.create_table(
        "import_row_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("import_row_id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["import_row_id"], ["import_rows.id"]),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("import_row_id", name="uq_import_row_links_import_row_id"),
    )
    op.create_index("ix_import_row_links_transaction_id", "import_row_links", ["transaction_id"])

    op.create_table(
        "splits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("moment_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.ForeignKeyConstraint(["moment_id"], ["moments.id"]),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "rule_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["rule_id"], ["rules.id"]),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION check_transaction_splits_sum(p_transaction_id integer)
        RETURNS void AS $$
        DECLARE
            tx_amount numeric(12,2);
            splits_sum numeric(12,2);
            split_count integer;
        BEGIN
            SELECT amount INTO tx_amount FROM transactions WHERE id = p_transaction_id;
            IF tx_amount IS NULL THEN
                RETURN;
            END IF;

            SELECT COALESCE(SUM(amount), 0), COUNT(*)
            INTO splits_sum, split_count
            FROM splits
            WHERE transaction_id = p_transaction_id;

            IF split_count > 0 AND splits_sum <> tx_amount THEN
                RAISE EXCEPTION 'splits sum % does not match transaction amount % for transaction %',
                    splits_sum, tx_amount, p_transaction_id;
            END IF;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_splits_sum_trigger()
        RETURNS trigger AS $$
        DECLARE
            tx_id integer;
        BEGIN
            IF (TG_OP = 'DELETE') THEN
                tx_id := OLD.transaction_id;
            ELSE
                tx_id := NEW.transaction_id;
            END IF;

            PERFORM check_transaction_splits_sum(tx_id);
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_transaction_amount_trigger()
        RETURNS trigger AS $$
        BEGIN
            PERFORM check_transaction_splits_sum(NEW.id);
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE CONSTRAINT TRIGGER splits_sum_check
        AFTER INSERT OR UPDATE OR DELETE ON splits
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION enforce_splits_sum_trigger();
        """
    )

    op.execute(
        """
        CREATE CONSTRAINT TRIGGER transactions_amount_check
        AFTER UPDATE OF amount ON transactions
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION enforce_transaction_amount_trigger();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS transactions_amount_check ON transactions")
    op.execute("DROP TRIGGER IF EXISTS splits_sum_check ON splits")
    op.execute("DROP FUNCTION IF EXISTS enforce_transaction_amount_trigger")
    op.execute("DROP FUNCTION IF EXISTS enforce_splits_sum_trigger")
    op.execute("DROP FUNCTION IF EXISTS check_transaction_splits_sum")

    op.drop_table("rule_runs")
    op.drop_table("splits")
    op.drop_index("ix_import_row_links_transaction_id", table_name="import_row_links")
    op.drop_table("import_row_links")
    op.drop_table("import_rows")
    op.drop_table("transactions")
    op.drop_table("imports")
    op.drop_table("rules")
    op.drop_table("payees")
    op.drop_table("moments")
    op.drop_table("categories")
    op.drop_table("accounts")
