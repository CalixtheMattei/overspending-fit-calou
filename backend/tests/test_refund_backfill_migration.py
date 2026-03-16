from __future__ import annotations

import importlib.util
from datetime import date
from decimal import Decimal
from pathlib import Path

from app.models import Account, Category, Split, Transaction, TransactionType
from app.services.category_catalog import seed_native_categories


def _load_refund_backfill_module():
    migration_path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0008_refund_category_backfill.py"
    spec = importlib.util.spec_from_file_location("refund_backfill_migration", migration_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load refund backfill migration module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_refund_backfill_rewrites_refund_categories_and_transaction_type(db_session):
    seed_native_categories(db_session)

    refund_category = (
        db_session.query(Category)
        .filter(Category.source == "native_catalog", Category.source_ref == "31442")
        .one()
    )
    unknown_category = (
        db_session.query(Category)
        .filter(Category.source == "native_catalog", Category.source_ref == "35")
        .one()
    )
    non_refund_category = (
        db_session.query(Category)
        .filter(Category.source == "native_catalog", Category.source_ref == "31402")
        .one()
    )

    account = Account(account_num="ACC-REFUND-BACKFILL", label="Refund backfill")
    db_session.add(account)
    db_session.flush()

    refund_tx = Transaction(
        account_id=account.id,
        posted_at=date(2024, 2, 8),
        operation_at=date(2024, 2, 8),
        amount=Decimal("20.00"),
        currency="EUR",
        label_raw="Refund bucket",
        label_norm="refund bucket",
        supplier_raw=None,
        payee_id=None,
        type=TransactionType.expense,
        fingerprint="refund-backfill-refund-tx",
    )
    keep_tx = Transaction(
        account_id=account.id,
        posted_at=date(2024, 2, 8),
        operation_at=date(2024, 2, 8),
        amount=Decimal("-15.00"),
        currency="EUR",
        label_raw="Regular expense",
        label_norm="regular expense",
        supplier_raw=None,
        payee_id=None,
        type=TransactionType.expense,
        fingerprint="refund-backfill-regular-tx",
    )
    db_session.add_all([refund_tx, keep_tx])
    db_session.flush()

    db_session.add_all(
        [
            Split(
                transaction_id=refund_tx.id,
                amount=Decimal("20.00"),
                category_id=refund_category.id,
                position=0,
            ),
            Split(
                transaction_id=keep_tx.id,
                amount=Decimal("-15.00"),
                category_id=non_refund_category.id,
                position=0,
            ),
        ]
    )
    db_session.flush()

    migration_module = _load_refund_backfill_module()
    migration_module.backfill_refund_categories(db_session.connection())
    db_session.flush()
    db_session.expire_all()

    updated_refund_tx = db_session.query(Transaction).filter(Transaction.id == refund_tx.id).one()
    updated_keep_tx = db_session.query(Transaction).filter(Transaction.id == keep_tx.id).one()
    updated_refund_split = db_session.query(Split).filter(Split.transaction_id == refund_tx.id).one()
    updated_keep_split = db_session.query(Split).filter(Split.transaction_id == keep_tx.id).one()

    assert updated_refund_tx.type == TransactionType.refund
    assert updated_refund_split.category_id == unknown_category.id
    assert updated_keep_tx.type == TransactionType.expense
    assert updated_keep_split.category_id == non_refund_category.id
