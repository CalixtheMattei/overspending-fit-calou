from app.models import ImportRow, ImportRowStatus, Transaction
from app.services.import_service import import_csv_bytes


def test_import_service_creates_and_links_transactions(db_session):
    csv_data = (
        "dateOp\tdateVal\tlabel\tcategory\tcategoryParent\tsupplierFound\tamount\tcomment\taccountNum\taccountLabel\taccountbalance\n"
        "01/01/2024\t02/01/2024\tCARTE 01/01/24 MERCHANT CB*1234\tFood\tDining\tsncf\t-10,00\t\tACC-1\tMain\t1000,00\n"
        "03/01/2024\t03/01/2024\tPRLV SEPA NETFLIX\tEntertainment\tSubscriptions\t\t-15,99\t\tACC-1\tMain\t984,01\n"
        "03/01/2024\t03/01/2024\tPRLV SEPA NETFLIX\tEntertainment\tSubscriptions\t\t-15,99\t\tACC-1\tMain\t984,01\n"
    )

    result = import_csv_bytes(db_session, "jan.csv", csv_data.encode("utf-8"))

    assert result.stats.row_count == 3
    assert result.stats.duplicate_count == 1
    assert result.stats.created_count == 2
    assert result.stats.linked_count == 0

    transactions = db_session.query(Transaction).all()
    assert len(transactions) == 2


def test_import_service_dedupes_across_imports(db_session):
    csv_data = (
        "dateOp\tdateVal\tlabel\tcategory\tcategoryParent\tsupplierFound\tamount\tcomment\taccountNum\taccountLabel\taccountbalance\n"
        "01/01/2024\t02/01/2024\tCARTE 01/01/24 MERCHANT CB*1234\tFood\tDining\tsncf\t-10,00\t\tACC-2\tMain\t1000,00\n"
    )

    first = import_csv_bytes(db_session, "jan.csv", csv_data.encode("utf-8"))
    second = import_csv_bytes(db_session, "jan.csv", csv_data.encode("utf-8"))

    assert first.stats.created_count == 1
    assert second.stats.created_count == 0
    assert second.stats.linked_count == 1


def test_import_service_persists_error_rows(db_session):
    csv_data = (
        "dateOp\tdateVal\tlabel\tcategory\tcategoryParent\tsupplierFound\tamount\tcomment\taccountNum\taccountLabel\taccountbalance\n"
        "01/01/2024\t02/01/2024\tCARTE 01/01/24 MERCHANT CB*1234\tFood\tDining\tsncf\tnot-a-number\t\tACC-3\tMain\t1000,00\n"
    )

    result = import_csv_bytes(db_session, "bad.csv", csv_data.encode("utf-8"))

    assert result.stats.error_count == 1
    rows = (
        db_session.query(ImportRow)
        .filter(ImportRow.import_id == result.import_record.id, ImportRow.status == ImportRowStatus.error)
        .all()
    )
    assert len(rows) == 1
    assert rows[0].amount is None
    assert rows[0].error_code == "parse_error"
