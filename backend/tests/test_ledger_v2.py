from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.db import get_db
from app.main import app
from app.models import (
    Account,
    Category,
    Counterparty,
    CounterpartyKind,
    Import,
    ImportRow,
    ImportRowLink,
    Rule,
    Transaction,
    TransactionManualEvent,
    TransactionType,
)
from app.services.import_service import import_csv_bytes
from app.services.rules_engine import RuleExecutionScope, run_rules_batch


@pytest.fixture()
def client(db_session):
    db_session.begin_nested()

    @event.listens_for(db_session, "after_transaction_end")
    def restart_savepoint(session, transaction):
        if transaction.nested and not transaction._parent.nested:
            session.begin_nested()

    def _get_db_override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db_override
    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    event.remove(db_session, "after_transaction_end", restart_savepoint)


def _create_transaction(db_session, amount: Decimal, fingerprint: str):
    account = Account(account_num=f"ACC-{fingerprint}", label="Main")
    category = Category(name=f"Category {fingerprint}")
    db_session.add_all([account, category])
    db_session.flush()

    tx_type = TransactionType.income if amount > 0 else TransactionType.expense
    transaction = Transaction(
        account_id=account.id,
        posted_at=date(2024, 2, 2),
        operation_at=date(2024, 2, 1),
        amount=amount,
        currency="EUR",
        label_raw=f"Label {fingerprint}",
        label_norm=f"label {fingerprint}",
        supplier_raw=None,
        payee_id=None,
        type=tx_type,
        fingerprint=fingerprint,
    )
    db_session.add(transaction)
    db_session.flush()
    return transaction, category


def _create_payee_seed_transaction(db_session, account_id: int, fingerprint: str, label_raw: str) -> Transaction:
    transaction = Transaction(
        account_id=account_id,
        posted_at=date(2024, 2, 2),
        operation_at=date(2024, 2, 1),
        amount=Decimal("-10.00"),
        currency="EUR",
        label_raw=label_raw,
        label_norm=label_raw.lower(),
        supplier_raw=None,
        payee_id=None,
        type=TransactionType.expense,
        fingerprint=fingerprint,
    )
    db_session.add(transaction)
    db_session.flush()
    return transaction


def _create_linked_import_row(
    db_session,
    *,
    import_id: int,
    transaction_id: int,
    row_hash: str,
    label_raw: str,
    supplier_raw: str | None,
) -> None:
    row = ImportRow(
        import_id=import_id,
        row_hash=row_hash,
        raw_json={"row_hash": row_hash},
        date_op=date(2024, 2, 1),
        date_val=date(2024, 2, 2),
        label_raw=label_raw,
        supplier_raw=supplier_raw,
        amount=Decimal("-10.00"),
        currency="EUR",
    )
    db_session.add(row)
    db_session.flush()
    db_session.add(ImportRowLink(import_row_id=row.id, transaction_id=transaction_id))
    db_session.flush()


def test_split_sum_mismatch_returns_422(client, db_session):
    transaction, category = _create_transaction(db_session, Decimal("-100.00"), "ledger-sum")

    response = client.put(
        f"/transactions/{transaction.id}/splits",
        json={
            "splits": [
                {"amount": "-60.00", "category_id": category.id},
                {"amount": "-30.00", "category_id": category.id},
            ]
        },
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "SPLIT_SUM_MISMATCH"
    assert "message" in detail


def test_split_sign_mismatch_returns_422(client, db_session):
    transaction, category = _create_transaction(db_session, Decimal("-50.00"), "ledger-sign")

    response = client.put(
        f"/transactions/{transaction.id}/splits",
        json={"splits": [{"amount": "50.00", "category_id": category.id}]},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "SPLIT_SIGN_MISMATCH"
    assert "split_index" in detail
    assert "path" in detail


def test_empty_splits_allowed_and_uncategorized(client, db_session):
    transaction, _category = _create_transaction(db_session, Decimal("-42.00"), "ledger-empty")

    response = client.put(
        f"/transactions/{transaction.id}/splits",
        json={"splits": []},
    )

    assert response.status_code == 200

    list_response = client.get("/transactions", params={"status": "uncategorized", "limit": 100})
    assert list_response.status_code == 200
    payload = list_response.json()
    ids = {row["id"] for row in payload["rows"]}
    assert transaction.id in ids


def test_transaction_detail_category_summary_includes_metadata(client, db_session):
    transaction, category = _create_transaction(db_session, Decimal("-20.00"), "ledger-category-summary")

    save_response = client.put(
        f"/transactions/{transaction.id}/splits",
        json={"splits": [{"amount": "-20.00", "category_id": category.id}]},
    )
    assert save_response.status_code == 200

    detail_response = client.get(f"/transactions/{transaction.id}")
    assert detail_response.status_code == 200
    payload = detail_response.json()
    split_category = payload["splits"][0]["category"]
    assert split_category["id"] == category.id
    assert split_category["name"] == category.name
    assert split_category["parent_id"] is None
    assert split_category["color"] == "#9CA3AF"
    assert split_category["icon"] == "tag"
    assert split_category["is_custom"] is True
    assert payload["category_provenance"]["source"] == "manual"
    assert payload["category_provenance"]["rule"] is None


def test_transactions_list_single_category_includes_metadata(client, db_session):
    transaction, category = _create_transaction(db_session, Decimal("-24.00"), "ledger-list-category-summary")

    save_response = client.put(
        f"/transactions/{transaction.id}/splits",
        json={"splits": [{"amount": "-24.00", "category_id": category.id}]},
    )
    assert save_response.status_code == 200

    list_response = client.get("/transactions", params={"status": "all", "limit": 100})
    assert list_response.status_code == 200
    row = next((item for item in list_response.json()["rows"] if item["id"] == transaction.id), None)
    assert row is not None
    assert row["single_category_id"] == category.id
    assert row["single_category"] is not None
    assert row["single_category"]["id"] == category.id
    assert row["single_category"]["name"] == category.name
    assert row["single_category"]["color"] == "#9CA3AF"
    assert row["single_category"]["icon"] == "tag"


def test_transaction_detail_category_provenance_rule_then_manual_override(client, db_session):
    fingerprint = "ledger-provenance"
    transaction, rule_category = _create_transaction(db_session, Decimal("-35.00"), fingerprint)
    manual_category = Category(name=f"Manual {fingerprint}")
    db_session.add(manual_category)
    db_session.flush()

    db_session.add(
        Rule(
            name="Provenance rule",
            priority=1,
            enabled=True,
            matcher_json={"all": [{"predicate": "label_contains", "value": fingerprint}]},
            action_json={"set_category": rule_category.id},
        )
    )
    db_session.flush()

    run_rules_batch(
        db_session,
        scope=RuleExecutionScope(type="all"),
        mode="apply",
        allow_overwrite=False,
        trigger_type="manual_scope",
    )
    db_session.flush()

    first_detail = client.get(f"/transactions/{transaction.id}")
    assert first_detail.status_code == 200
    first_payload = first_detail.json()
    assert first_payload["category_provenance"]["source"] == "rule"
    assert first_payload["category_provenance"]["rule"] is not None

    update_response = client.put(
        f"/transactions/{transaction.id}/splits",
        json={"splits": [{"amount": "-35.00", "category_id": manual_category.id}]},
    )
    assert update_response.status_code == 200
    assert db_session.query(TransactionManualEvent).filter(TransactionManualEvent.transaction_id == transaction.id).count() == 1

    second_detail = client.get(f"/transactions/{transaction.id}")
    assert second_detail.status_code == 200
    second_payload = second_detail.json()
    assert second_payload["category_provenance"]["source"] == "manual"
    assert second_payload["category_provenance"]["rule"] is None

    no_change_response = client.put(
        f"/transactions/{transaction.id}/splits",
        json={"splits": [{"amount": "-35.00", "category_id": manual_category.id}]},
    )
    assert no_change_response.status_code == 200
    assert db_session.query(TransactionManualEvent).filter(TransactionManualEvent.transaction_id == transaction.id).count() == 1


def test_payee_create_idempotent(client):
    response_one = client.post("/payees", json={"name": "  Netflix Prime  "})
    assert response_one.status_code == 201
    payee_id = response_one.json()["id"]

    response_two = client.post("/payees", json={"name": "netflix   prime"})
    assert response_two.status_code == 201
    assert response_two.json()["id"] == payee_id


def test_internal_account_reorder_dense_positions(client):
    created = []
    for name in ["Alpha", "Beta", "Gamma"]:
        response = client.post("/internal-accounts", json={"name": name})
        assert response.status_code == 201
        created.append(response.json())

    target_id = created[2]["id"]

    response = client.patch(f"/internal-accounts/{target_id}", json={"position": 0})
    assert response.status_code == 200

    list_response = client.get("/internal-accounts")
    assert list_response.status_code == 200
    accounts = list_response.json()

    positions = [account["position"] for account in accounts]
    assert positions == list(range(len(accounts)))
    assert accounts[0]["id"] == target_id


def test_payees_automatic_returns_aggregated_seeds_with_distinct_counts(client, db_session):
    account = Account(account_num="ACC-AUTO-PAYEES", label="Main")
    db_session.add(account)
    db_session.flush()

    transaction_sncf_one = _create_payee_seed_transaction(db_session, account.id, "auto-sncf-1", "CARD SNCF")
    transaction_sncf_two = _create_payee_seed_transaction(db_session, account.id, "auto-sncf-2", "CARD SNCF 2")
    transaction_uber = _create_payee_seed_transaction(db_session, account.id, "auto-uber-1", "CARD UBER")
    transaction_apple = _create_payee_seed_transaction(db_session, account.id, "auto-apple-1", "CARD APPLE")

    import_record = Import(account_id=account.id, file_name="auto-payees.csv", file_hash="auto-payees-hash")
    db_session.add(import_record)
    db_session.flush()

    _create_linked_import_row(
        db_session,
        import_id=import_record.id,
        transaction_id=transaction_sncf_one.id,
        row_hash="auto-row-1",
        label_raw="CARTE 02/02/24 SNCF",
        supplier_raw=None,
    )
    _create_linked_import_row(
        db_session,
        import_id=import_record.id,
        transaction_id=transaction_sncf_two.id,
        row_hash="auto-row-2",
        label_raw="Random label",
        supplier_raw="SNCF",
    )
    _create_linked_import_row(
        db_session,
        import_id=import_record.id,
        transaction_id=transaction_sncf_one.id,
        row_hash="auto-row-3",
        label_raw="CARTE 03/02/24 SNCF",
        supplier_raw=None,
    )
    _create_linked_import_row(
        db_session,
        import_id=import_record.id,
        transaction_id=transaction_uber.id,
        row_hash="auto-row-4",
        label_raw="CARTE 04/02/24 UBER EATS",
        supplier_raw=None,
    )
    _create_linked_import_row(
        db_session,
        import_id=import_record.id,
        transaction_id=transaction_apple.id,
        row_hash="auto-row-5",
        label_raw="CARTE 04/02/24 APPLE",
        supplier_raw=None,
    )
    _create_linked_import_row(
        db_session,
        import_id=import_record.id,
        transaction_id=transaction_uber.id,
        row_hash="auto-row-6",
        label_raw="   ",
        supplier_raw=None,
    )

    response = client.get("/payees/automatic", params={"limit": 10})

    assert response.status_code == 200
    payload = response.json()
    assert [item["canonical_name"] for item in payload] == ["sncf", "apple", "uber eats"]
    assert payload[0]["linked_transaction_count"] == 2
    assert payload[1]["linked_transaction_count"] == 1
    assert payload[2]["linked_transaction_count"] == 1


def test_payees_automatic_supports_q_filter_and_limit(client, db_session):
    account = Account(account_num="ACC-AUTO-PAYEES-Q", label="Main")
    db_session.add(account)
    db_session.flush()

    transaction_sncf = _create_payee_seed_transaction(db_session, account.id, "auto-q-sncf", "CARD SNCF")
    transaction_uber = _create_payee_seed_transaction(db_session, account.id, "auto-q-uber", "CARD UBER")

    import_record = Import(account_id=account.id, file_name="auto-payees-q.csv", file_hash="auto-payees-q-hash")
    db_session.add(import_record)
    db_session.flush()

    _create_linked_import_row(
        db_session,
        import_id=import_record.id,
        transaction_id=transaction_sncf.id,
        row_hash="auto-q-row-1",
        label_raw="CARTE 02/02/24 SNCF",
        supplier_raw=None,
    )
    _create_linked_import_row(
        db_session,
        import_id=import_record.id,
        transaction_id=transaction_uber.id,
        row_hash="auto-q-row-2",
        label_raw="CARTE 04/02/24 UBER EATS",
        supplier_raw=None,
    )

    filtered = client.get("/payees/automatic", params={"q": "uber", "limit": 10})
    assert filtered.status_code == 200
    assert [item["canonical_name"] for item in filtered.json()] == ["uber eats"]

    limited = client.get("/payees/automatic", params={"limit": 1})
    assert limited.status_code == 200
    assert len(limited.json()) == 1


def test_payees_automatic_hides_seeds_that_match_saved_payees(client, db_session):
    account = Account(account_num="ACC-AUTO-HIDE-SAVED", label="Main")
    db_session.add(account)
    db_session.flush()

    transaction_sncf = _create_payee_seed_transaction(db_session, account.id, "auto-hide-saved-sncf", "CARD SNCF")
    transaction_uber = _create_payee_seed_transaction(db_session, account.id, "auto-hide-saved-uber", "CARD UBER")

    import_record = Import(account_id=account.id, file_name="auto-hide-saved.csv", file_hash="auto-hide-saved")
    db_session.add(import_record)
    db_session.flush()

    _create_linked_import_row(
        db_session,
        import_id=import_record.id,
        transaction_id=transaction_sncf.id,
        row_hash="auto-hide-saved-row-1",
        label_raw="CARTE 02/02/24 SNCF",
        supplier_raw=None,
    )
    _create_linked_import_row(
        db_session,
        import_id=import_record.id,
        transaction_id=transaction_uber.id,
        row_hash="auto-hide-saved-row-2",
        label_raw="CARTE 04/02/24 UBER EATS",
        supplier_raw=None,
    )

    db_session.add(
        Counterparty(
            name="Sncf",
            canonical_name="sncf",
            kind=CounterpartyKind.merchant,
            type=None,
            position=0,
            is_archived=False,
        )
    )
    db_session.flush()

    response = client.get("/payees/automatic", params={"limit": 10})
    assert response.status_code == 200
    assert [item["canonical_name"] for item in response.json()] == ["uber eats"]


def test_payees_automatic_apply_non_overwrite_updates_only_unassigned(client, db_session):
    account = Account(account_num="ACC-AUTO-APPLY-NON-OVERWRITE", label="Main")
    db_session.add(account)
    db_session.flush()

    existing_payee = Counterparty(
        name="Existing Vendor",
        canonical_name="existing vendor",
        kind=CounterpartyKind.merchant,
        type=None,
        position=0,
        is_archived=False,
    )
    db_session.add(existing_payee)
    db_session.flush()

    transaction_unassigned = _create_payee_seed_transaction(db_session, account.id, "auto-apply-non-overwrite-1", "CARD SNCF A")
    transaction_assigned = _create_payee_seed_transaction(db_session, account.id, "auto-apply-non-overwrite-2", "CARD SNCF B")
    transaction_assigned.payee_id = existing_payee.id
    db_session.flush()

    import_record = Import(account_id=account.id, file_name="auto-apply-non-overwrite.csv", file_hash="auto-apply-non-overwrite")
    db_session.add(import_record)
    db_session.flush()

    _create_linked_import_row(
        db_session,
        import_id=import_record.id,
        transaction_id=transaction_unassigned.id,
        row_hash="auto-apply-non-overwrite-row-1",
        label_raw="CARTE 02/02/24 SNCF",
        supplier_raw=None,
    )
    _create_linked_import_row(
        db_session,
        import_id=import_record.id,
        transaction_id=transaction_assigned.id,
        row_hash="auto-apply-non-overwrite-row-2",
        label_raw="CARTE 03/02/24 SNCF",
        supplier_raw=None,
    )

    response = client.post(
        "/payees/automatic/apply",
        json={
            "seed_canonical_name": "sncf",
            "payee_name": "sncf travel",
            "kind": "merchant",
            "overwrite_existing": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["matched_transaction_count"] == 2
    assert payload["updated_transaction_count"] == 1
    assert payload["skipped_assigned_count"] == 1
    assert payload["payee"]["name"] == "Sncf Travel"

    db_session.refresh(transaction_unassigned)
    db_session.refresh(transaction_assigned)
    assert transaction_unassigned.payee_id == payload["payee"]["id"]
    assert transaction_assigned.payee_id == existing_payee.id


def test_payees_automatic_apply_hides_seed_and_applies_to_future_imports(client, db_session):
    account = Account(account_num="ACC-AUTO-FUTURE", label="Main")
    db_session.add(account)
    db_session.flush()

    seed_transaction = _create_payee_seed_transaction(db_session, account.id, "auto-future-seed", "CARD SNCF")
    import_record = Import(account_id=account.id, file_name="auto-future-seed.csv", file_hash="auto-future-seed")
    db_session.add(import_record)
    db_session.flush()
    _create_linked_import_row(
        db_session,
        import_id=import_record.id,
        transaction_id=seed_transaction.id,
        row_hash="auto-future-seed-row",
        label_raw="CARTE 01/02/24 SNCF",
        supplier_raw=None,
    )

    apply_response = client.post(
        "/payees/automatic/apply",
        json={
            "seed_canonical_name": "sncf",
            "payee_name": "Rail Travel",
            "kind": "merchant",
            "overwrite_existing": False,
        },
    )
    assert apply_response.status_code == 200
    payee_id = apply_response.json()["payee"]["id"]

    hidden_response = client.get("/payees/automatic")
    assert hidden_response.status_code == 200
    assert hidden_response.json() == []

    csv_data = (
        "dateOp\tdateVal\tlabel\tcategory\tcategoryParent\tsupplierFound\tamount\tcomment\taccountNum\taccountLabel\taccountbalance\n"
        "07/02/2024\t08/02/2024\tCARTE 08/02/24 SNCF\t\t\t\t-15,00\t\tACC-AUTO-FUTURE\tMain\t1000,00\n"
    )
    result = import_csv_bytes(db_session, "auto-future-import.csv", csv_data.encode("utf-8"))
    assert result.stats.created_count == 1

    imported_transaction = (
        db_session.query(Transaction)
        .filter(Transaction.label_raw == "CARTE 08/02/24 SNCF")
        .one()
    )
    assert imported_transaction.payee_id == payee_id


def test_payees_automatic_apply_overwrite_updates_all_matches(client, db_session):
    account = Account(account_num="ACC-AUTO-APPLY-OVERWRITE", label="Main")
    db_session.add(account)
    db_session.flush()

    existing_payee = Counterparty(
        name="Existing Payee",
        canonical_name="existing payee",
        kind=CounterpartyKind.merchant,
        type=None,
        position=0,
        is_archived=False,
    )
    db_session.add(existing_payee)
    db_session.flush()

    transaction_one = _create_payee_seed_transaction(db_session, account.id, "auto-apply-overwrite-1", "CARD UBER A")
    transaction_two = _create_payee_seed_transaction(db_session, account.id, "auto-apply-overwrite-2", "CARD UBER B")
    transaction_one.payee_id = existing_payee.id
    db_session.flush()

    import_record = Import(account_id=account.id, file_name="auto-apply-overwrite.csv", file_hash="auto-apply-overwrite")
    db_session.add(import_record)
    db_session.flush()

    _create_linked_import_row(
        db_session,
        import_id=import_record.id,
        transaction_id=transaction_one.id,
        row_hash="auto-apply-overwrite-row-1",
        label_raw="CARTE 04/02/24 UBER EATS",
        supplier_raw=None,
    )
    _create_linked_import_row(
        db_session,
        import_id=import_record.id,
        transaction_id=transaction_two.id,
        row_hash="auto-apply-overwrite-row-2",
        label_raw="CARTE 05/02/24 UBER EATS",
        supplier_raw=None,
    )

    response = client.post(
        "/payees/automatic/apply",
        json={
            "seed_canonical_name": "uber eats",
            "payee_name": "uber eats",
            "kind": "merchant",
            "overwrite_existing": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["matched_transaction_count"] == 2
    assert payload["updated_transaction_count"] == 2
    assert payload["skipped_assigned_count"] == 0

    db_session.refresh(transaction_one)
    db_session.refresh(transaction_two)
    assert transaction_one.payee_id == payload["payee"]["id"]
    assert transaction_two.payee_id == payload["payee"]["id"]


def test_payees_automatic_ignore_and_restore(client, db_session):
    account = Account(account_num="ACC-AUTO-IGNORE", label="Main")
    db_session.add(account)
    db_session.flush()

    transaction = _create_payee_seed_transaction(db_session, account.id, "auto-ignore-1", "CARD APPLE")
    import_record = Import(account_id=account.id, file_name="auto-ignore.csv", file_hash="auto-ignore")
    db_session.add(import_record)
    db_session.flush()

    _create_linked_import_row(
        db_session,
        import_id=import_record.id,
        transaction_id=transaction.id,
        row_hash="auto-ignore-row-1",
        label_raw="CARTE 06/02/24 APPLE",
        supplier_raw=None,
    )

    ignore_response = client.post("/payees/automatic/ignore", json={"canonical_name": "apple"})
    assert ignore_response.status_code == 201
    assert ignore_response.json()["ignored"] is True

    hidden_response = client.get("/payees/automatic")
    assert hidden_response.status_code == 200
    assert hidden_response.json() == []

    include_ignored_response = client.get("/payees/automatic", params={"include_ignored": "true"})
    assert include_ignored_response.status_code == 200
    rows = include_ignored_response.json()
    assert len(rows) == 1
    assert rows[0]["canonical_name"] == "apple"
    assert rows[0]["is_ignored"] is True

    restore_response = client.delete("/payees/automatic/ignore/apple")
    assert restore_response.status_code == 200
    assert restore_response.json()["ignored"] is False

    restored_list = client.get("/payees/automatic")
    assert restored_list.status_code == 200
    restored_rows = restored_list.json()
    assert len(restored_rows) == 1
    assert restored_rows[0]["canonical_name"] == "apple"
    assert restored_rows[0]["is_ignored"] is False


def test_transaction_patch_rejects_internal_counterparty_as_payee(client, db_session):
    transaction, _category = _create_transaction(db_session, Decimal("-22.00"), "ledger-internal-payee-guard")
    internal_counterparty = Counterparty(
        name="Household Cash",
        canonical_name="household cash",
        kind=CounterpartyKind.internal,
        type="cash",
        position=0,
        is_archived=False,
    )
    db_session.add(internal_counterparty)
    db_session.flush()

    response = client.patch(
        f"/transactions/{transaction.id}",
        json={"payee_id": internal_counterparty.id},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Payee id must reference a payee counterparty"


def test_replace_splits_rejects_non_internal_counterparty_for_internal_account(client, db_session):
    transaction, category = _create_transaction(db_session, Decimal("-18.00"), "ledger-internal-split-guard")
    non_internal_counterparty = Counterparty(
        name="Coffee Shop",
        canonical_name="coffee shop",
        kind=CounterpartyKind.merchant,
        type=None,
        position=0,
        is_archived=False,
    )
    db_session.add(non_internal_counterparty)
    db_session.flush()

    response = client.put(
        f"/transactions/{transaction.id}/splits",
        json={
            "splits": [
                {
                    "amount": "-18.00",
                    "category_id": category.id,
                    "internal_account_id": non_internal_counterparty.id,
                }
            ]
        },
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "INTERNAL_ACCOUNT_NOT_FOUND"
    assert "message" in detail
    assert non_internal_counterparty.id in detail["internal_account_ids"]


# ---------------------------------------------------------------------------
# Scenario #7: Sign mismatch on positive transaction (income/refund)
# ---------------------------------------------------------------------------

def test_split_sign_mismatch_positive_transaction_returns_422(client, db_session):
    """Positive transaction with negative split amounts must be rejected."""
    transaction, category = _create_transaction(db_session, Decimal("100.00"), "ledger-sign-pos")

    response = client.put(
        f"/transactions/{transaction.id}/splits",
        json={"splits": [{"amount": "-100.00", "category_id": category.id}]},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "SPLIT_SIGN_MISMATCH"
    assert detail["split_index"] == 0


def test_split_sign_mismatch_positive_transaction_multi_split(client, db_session):
    """Positive transaction with a mix where one split is negative must be rejected."""
    transaction, category = _create_transaction(db_session, Decimal("50.00"), "ledger-sign-pos-multi")

    response = client.put(
        f"/transactions/{transaction.id}/splits",
        json={
            "splits": [
                {"amount": "60.00", "category_id": category.id},
                {"amount": "-10.00", "category_id": category.id},
            ]
        },
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "SPLIT_SIGN_MISMATCH"
    assert detail["split_index"] == 1


# ---------------------------------------------------------------------------
# Scenario #8: Decimal precision > 2 places
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "bad_amount",
    [
        "-50.001",
        "-50.123",
        "100.999",
        "-0.005",
    ],
    ids=[
        "three_decimals_negative",
        "three_decimals_negative_2",
        "three_decimals_positive",
        "three_decimals_tiny",
    ],
)
def test_split_decimal_precision_over_2_returns_422(client, db_session, bad_amount):
    """Split amounts with more than 2 decimal places must be rejected."""
    transaction, category = _create_transaction(db_session, Decimal("-50.00"), "ledger-decimal-prec")

    response = client.put(
        f"/transactions/{transaction.id}/splits",
        json={"splits": [{"amount": bad_amount, "category_id": category.id}]},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "SPLIT_AMOUNT_INVALID"
    assert "at most 2 decimal places" in detail["message"]
    assert detail["split_index"] == 0
    assert detail["path"] == "splits[0].amount"


# ---------------------------------------------------------------------------
# Scenario #9: Null / missing category_id in split row (allowed)
# ---------------------------------------------------------------------------

def test_split_missing_category_id_allowed(client, db_session):
    """A split row without category_id is allowed (uncategorized split)."""
    transaction, _category = _create_transaction(db_session, Decimal("-30.00"), "ledger-no-cat")

    response = client.put(
        f"/transactions/{transaction.id}/splits",
        json={"splits": [{"amount": "-30.00"}]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["splits_count"] == 1
    assert payload["splits"][0]["category_id"] is None
    assert payload["is_categorized"] is False


def test_split_explicit_null_category_id_allowed(client, db_session):
    """A split row with category_id explicitly set to null is allowed."""
    transaction, _category = _create_transaction(db_session, Decimal("-30.00"), "ledger-null-cat")

    response = client.put(
        f"/transactions/{transaction.id}/splits",
        json={"splits": [{"amount": "-30.00", "category_id": None}]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["splits_count"] == 1
    assert payload["splits"][0]["category_id"] is None
    assert payload["is_categorized"] is False


def test_single_split_uncategorize_roundtrip(client, db_session):
    """Categorize then uncategorize a single-split transaction."""
    transaction, category = _create_transaction(db_session, Decimal("-50.00"), "ledger-uncat-rt")

    # First categorize
    cat_response = client.put(
        f"/transactions/{transaction.id}/splits",
        json={"splits": [{"amount": "-50.00", "category_id": category.id}]},
    )
    assert cat_response.status_code == 200
    assert cat_response.json()["is_categorized"] is True
    split_id = cat_response.json()["splits"][0]["id"]

    # Now uncategorize by setting category_id to null
    uncat_response = client.put(
        f"/transactions/{transaction.id}/splits",
        json={"splits": [{"id": split_id, "amount": "-50.00", "category_id": None}]},
    )
    assert uncat_response.status_code == 200
    payload = uncat_response.json()
    assert payload["splits_count"] == 1
    assert payload["splits"][0]["category_id"] is None
    assert payload["is_categorized"] is False

    # Verify it appears in uncategorized list
    list_response = client.get("/transactions", params={"status": "uncategorized", "limit": 100})
    assert list_response.status_code == 200
    ids = {row["id"] for row in list_response.json()["rows"]}
    assert transaction.id in ids


def test_multi_split_with_some_null_categories(client, db_session):
    """Multi-split where some splits have categories and some do not."""
    transaction, category = _create_transaction(db_session, Decimal("-100.00"), "ledger-multi-uncat")

    response = client.put(
        f"/transactions/{transaction.id}/splits",
        json={
            "splits": [
                {"amount": "-60.00", "category_id": category.id},
                {"amount": "-40.00", "category_id": None},
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["splits_count"] == 2
    assert payload["is_categorized"] is False
    categorized_splits = [s for s in payload["splits"] if s["category_id"] is not None]
    uncategorized_splits = [s for s in payload["splits"] if s["category_id"] is None]
    assert len(categorized_splits) == 1
    assert len(uncategorized_splits) == 1


# ---------------------------------------------------------------------------
# Scenario #10: Duplicate split IDs in payload
# ---------------------------------------------------------------------------

def test_split_duplicate_ids_in_payload_returns_422(client, db_session):
    """Payload containing the same split ID twice must be rejected."""
    transaction, category = _create_transaction(db_session, Decimal("-100.00"), "ledger-dup-id")

    # First, create a valid split so we have a real split ID
    setup_response = client.put(
        f"/transactions/{transaction.id}/splits",
        json={"splits": [{"amount": "-100.00", "category_id": category.id}]},
    )
    assert setup_response.status_code == 200
    split_id = setup_response.json()["splits"][0]["id"]

    # Now send a payload with the same split ID duplicated
    response = client.put(
        f"/transactions/{transaction.id}/splits",
        json={
            "splits": [
                {"id": split_id, "amount": "-60.00", "category_id": category.id},
                {"id": split_id, "amount": "-40.00", "category_id": category.id},
            ]
        },
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "SPLIT_ID_DUPLICATE"
    assert split_id in detail["split_ids"]


# ---------------------------------------------------------------------------
# Scenario #11: Split ID not belonging to transaction
# ---------------------------------------------------------------------------

def test_split_id_not_belonging_to_transaction_returns_422(client, db_session):
    """A split ID that exists on a different transaction must be rejected."""
    # Create two separate transactions
    tx_a, cat_a = _create_transaction(db_session, Decimal("-50.00"), "ledger-foreign-id-a")
    tx_b, cat_b = _create_transaction(db_session, Decimal("-70.00"), "ledger-foreign-id-b")

    # Create a split on tx_b
    setup_response = client.put(
        f"/transactions/{tx_b.id}/splits",
        json={"splits": [{"amount": "-70.00", "category_id": cat_b.id}]},
    )
    assert setup_response.status_code == 200
    foreign_split_id = setup_response.json()["splits"][0]["id"]

    # Try to use tx_b's split ID when updating tx_a
    response = client.put(
        f"/transactions/{tx_a.id}/splits",
        json={
            "splits": [
                {"id": foreign_split_id, "amount": "-50.00", "category_id": cat_a.id},
            ]
        },
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "SPLIT_ID_NOT_FOUND"
    assert foreign_split_id in detail["split_ids"]


def test_split_id_nonexistent_returns_422(client, db_session):
    """A completely fabricated split ID must be rejected."""
    transaction, category = _create_transaction(db_session, Decimal("-40.00"), "ledger-fake-id")

    # Create a valid split first so we have existing splits on the transaction
    setup_response = client.put(
        f"/transactions/{transaction.id}/splits",
        json={"splits": [{"amount": "-40.00", "category_id": category.id}]},
    )
    assert setup_response.status_code == 200

    fake_id = 999999

    response = client.put(
        f"/transactions/{transaction.id}/splits",
        json={
            "splits": [
                {"id": fake_id, "amount": "-40.00", "category_id": category.id},
            ]
        },
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "SPLIT_ID_NOT_FOUND"
    assert fake_id in detail["split_ids"]
