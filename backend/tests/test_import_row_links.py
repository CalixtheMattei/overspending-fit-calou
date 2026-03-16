from datetime import date
from decimal import Decimal

from app.models import Account, Import, ImportRow, ImportRowLink, Transaction, TransactionType


def test_transaction_import_row_links_one_to_many(db_session):
    account = Account(account_num="ACC-1", label="Main")
    db_session.add(account)
    db_session.flush()

    import_one = Import(account_id=account.id, file_name="a.csv", file_hash="hash-a")
    import_two = Import(account_id=account.id, file_name="b.csv", file_hash="hash-b")
    db_session.add_all([import_one, import_two])
    db_session.flush()

    row_one = ImportRow(
        import_id=import_one.id,
        row_hash="row-1",
        raw_json={"row": 1},
        date_op=date(2024, 1, 1),
        date_val=date(2024, 1, 2),
        label_raw="CARTE TEST",
        amount=Decimal("-10.00"),
        currency="EUR",
    )
    row_two = ImportRow(
        import_id=import_two.id,
        row_hash="row-2",
        raw_json={"row": 2},
        date_op=date(2024, 1, 3),
        date_val=date(2024, 1, 4),
        label_raw="CARTE TEST",
        amount=Decimal("-10.00"),
        currency="EUR",
    )
    db_session.add_all([row_one, row_two])
    db_session.flush()

    transaction = Transaction(
        account_id=account.id,
        posted_at=date(2024, 1, 2),
        operation_at=date(2024, 1, 1),
        amount=Decimal("-20.00"),
        currency="EUR",
        label_raw="CARTE TEST",
        label_norm="carte test",
        supplier_raw=None,
        payee_id=None,
        type=TransactionType.expense,
        fingerprint="fingerprint-1",
    )
    db_session.add(transaction)
    db_session.flush()

    link_one = ImportRowLink(import_row_id=row_one.id, transaction_id=transaction.id)
    link_two = ImportRowLink(import_row_id=row_two.id, transaction_id=transaction.id)
    db_session.add_all([link_one, link_two])
    db_session.flush()

    db_session.expire_all()
    reloaded = db_session.get(Transaction, transaction.id)

    assert reloaded is not None
    assert len(reloaded.import_row_links) == 2
    assert {link.import_row_id for link in reloaded.import_row_links} == {row_one.id, row_two.id}
