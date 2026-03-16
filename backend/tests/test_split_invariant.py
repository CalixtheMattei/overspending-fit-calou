from datetime import date
from decimal import Decimal

import pytest

from app.models import Account, Category, Split, Transaction, TransactionType


def test_split_sum_mismatch_raises(db_session):
    account = Account(account_num="ACC-2", label="Secondary")
    category = Category(name="Food")
    db_session.add_all([account, category])
    db_session.flush()

    transaction = Transaction(
        account_id=account.id,
        posted_at=date(2024, 2, 2),
        operation_at=date(2024, 2, 1),
        amount=Decimal("-100.00"),
        currency="EUR",
        label_raw="CARTE FOOD",
        label_norm="carte food",
        supplier_raw=None,
        payee_id=None,
        type=TransactionType.expense,
        fingerprint="fingerprint-2",
    )
    db_session.add(transaction)
    db_session.flush()

    split_one = Split(transaction_id=transaction.id, amount=Decimal("-60.00"), category_id=category.id)
    split_two = Split(transaction_id=transaction.id, amount=Decimal("-30.00"), category_id=category.id)
    db_session.add_all([split_one, split_two])

    with pytest.raises(Exception):
        db_session.commit()
    db_session.rollback()
