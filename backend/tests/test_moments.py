from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy import event

from app.db import get_db
from app.main import app
from app.models import Account, Category, Moment, Split, Transaction, TransactionType


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


def _create_split(
    db_session,
    *,
    fingerprint: str,
    amount: Decimal,
    operation_at: date,
    moment_id: int | None = None,
) -> tuple[Transaction, Split, Category]:
    account = Account(account_num=f"ACC-{fingerprint}", label=f"Account {fingerprint}")
    category = Category(name=f"Category {fingerprint}")
    db_session.add_all([account, category])
    db_session.flush()

    tx_type = TransactionType.income if amount > 0 else TransactionType.expense
    tx = Transaction(
        account_id=account.id,
        posted_at=operation_at,
        operation_at=operation_at,
        amount=amount,
        currency="EUR",
        label_raw=f"Label {fingerprint}",
        label_norm=f"label {fingerprint}",
        supplier_raw=f"Supplier {fingerprint}",
        payee_id=None,
        type=tx_type,
        fingerprint=fingerprint,
    )
    db_session.add(tx)
    db_session.flush()

    split = Split(
        transaction_id=tx.id,
        amount=amount,
        category_id=category.id,
        moment_id=moment_id,
        note=f"note {fingerprint}",
        position=0,
    )
    db_session.add(split)
    db_session.flush()
    return tx, split, category


def test_moments_crud_contract(client):
    create_response = client.post(
        "/moments",
        json={
            "name": "Summer Trip",
            "start_date": "2024-07-01",
            "end_date": "2024-07-31",
            "description": "vacation",
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    moment_id = created["id"]
    assert created["name"] == "Summer Trip"
    assert created["tagged_splits_count"] == 0
    assert created["cover_image_url"] is None
    assert created["created_at"] is not None
    assert created["updated_at"] is not None

    get_response = client.get(f"/moments/{moment_id}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == moment_id

    list_response = client.get("/moments")
    assert list_response.status_code == 200
    ids = {row["id"] for row in list_response.json()}
    assert moment_id in ids

    patch_response = client.patch(
        f"/moments/{moment_id}",
        json={
            "name": "Summer Trip 2",
            "description": "updated",
            "cover_image_url": "https://example.com/cover.jpg",
        },
    )
    assert patch_response.status_code == 200
    patched = patch_response.json()
    assert patched["name"] == "Summer Trip 2"
    assert patched["description"] == "updated"
    assert patched["cover_image_url"] == "https://example.com/cover.jpg"


def test_moment_errors_use_normalized_detail_codes(client):
    bad_range = client.post(
        "/moments",
        json={
            "name": "Bad",
            "start_date": "2024-08-31",
            "end_date": "2024-08-01",
        },
    )
    assert bad_range.status_code == 422
    assert bad_range.json()["detail"]["code"] == "MOMENT_INVALID_DATE_RANGE"

    missing = client.get("/moments/999999")
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "MOMENT_NOT_FOUND"


def test_delete_moment_untags_splits(client, db_session):
    moment = Moment(
        name="Delete Me",
        start_date=date(2024, 5, 1),
        end_date=date(2024, 5, 31),
        description=None,
    )
    db_session.add(moment)
    db_session.flush()

    _tx, split, _category = _create_split(
        db_session,
        fingerprint="delete-untag",
        amount=Decimal("-25.00"),
        operation_at=date(2024, 5, 12),
        moment_id=moment.id,
    )
    db_session.flush()

    response = client.delete(f"/moments/{moment.id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["deleted"] is True
    assert payload["untagged_splits_count"] == 1

    db_session.refresh(split)
    assert split.moment_id is None
    assert db_session.query(Moment).filter(Moment.id == moment.id).one_or_none() is None


def test_tagged_bulk_contracts_and_reassign_confirmation(client, db_session):
    source = Moment(name="Source", start_date=date(2024, 6, 1), end_date=date(2024, 6, 30))
    target = Moment(name="Target", start_date=date(2024, 6, 1), end_date=date(2024, 6, 30))
    db_session.add_all([source, target])
    db_session.flush()

    _tx_one, split_one, _ = _create_split(
        db_session,
        fingerprint="tagged-one",
        amount=Decimal("-10.00"),
        operation_at=date(2024, 6, 3),
        moment_id=source.id,
    )
    _tx_two, split_two, _ = _create_split(
        db_session,
        fingerprint="tagged-two",
        amount=Decimal("-20.00"),
        operation_at=date(2024, 6, 4),
        moment_id=source.id,
    )

    tagged_response = client.get(f"/moments/{source.id}/tagged")
    assert tagged_response.status_code == 200
    assert tagged_response.json()["total"] == 2

    conflict_response = client.post(
        f"/moments/{source.id}/tagged/move",
        json={
            "split_ids": [split_one.id],
            "target_moment_id": target.id,
            "confirm_reassign": False,
        },
    )
    assert conflict_response.status_code == 409
    assert conflict_response.json()["detail"]["code"] == "MOMENT_REASSIGN_CONFIRM_REQUIRED"

    confirm_response = client.post(
        f"/moments/{source.id}/tagged/move",
        json={
            "split_ids": [split_one.id],
            "target_moment_id": target.id,
            "confirm_reassign": True,
        },
    )
    assert confirm_response.status_code == 200
    assert confirm_response.json()["updated_count"] == 1

    db_session.refresh(split_one)
    assert split_one.moment_id == target.id

    remove_response = client.post(
        f"/moments/{source.id}/tagged/remove",
        json={"split_ids": [split_two.id]},
    )
    assert remove_response.status_code == 200
    assert remove_response.json()["updated_count"] == 1
    db_session.refresh(split_two)
    assert split_two.moment_id is None


def test_candidates_refresh_list_and_decide(client, db_session):
    moment = Moment(
        name="Candidates",
        start_date=date(2024, 9, 1),
        end_date=date(2024, 9, 30),
    )
    db_session.add(moment)
    db_session.flush()

    _tx, split, _category = _create_split(
        db_session,
        fingerprint="candidate-pending",
        amount=Decimal("-30.00"),
        operation_at=date(2024, 9, 12),
        moment_id=None,
    )

    refresh = client.post(f"/moments/{moment.id}/candidates/refresh")
    assert refresh.status_code == 200
    assert refresh.json()["inserted_count"] >= 1

    pending = client.get(f"/moments/{moment.id}/candidates", params={"status": "pending"})
    assert pending.status_code == 200
    pending_rows = pending.json()["rows"]
    assert any(row["split_id"] == split.id for row in pending_rows)

    reject = client.post(
        f"/moments/{moment.id}/candidates/decision",
        json={"split_ids": [split.id], "decision": "rejected"},
    )
    assert reject.status_code == 200
    assert reject.json()["updated_count"] == 1

    rejected = client.get(f"/moments/{moment.id}/candidates", params={"status": "rejected"})
    assert rejected.status_code == 200
    assert any(row["split_id"] == split.id for row in rejected.json()["rows"])

    accept = client.post(
        f"/moments/{moment.id}/candidates/decision",
        json={"split_ids": [split.id], "decision": "accepted"},
    )
    assert accept.status_code == 200
    db_session.refresh(split)
    assert split.moment_id == moment.id


def test_candidates_accept_conflict_requires_confirmation(client, db_session):
    source = Moment(name="Source C", start_date=date(2024, 10, 1), end_date=date(2024, 10, 31))
    target = Moment(name="Target C", start_date=date(2024, 10, 1), end_date=date(2024, 10, 31))
    db_session.add_all([source, target])
    db_session.flush()

    _tx, split, _category = _create_split(
        db_session,
        fingerprint="candidate-conflict",
        amount=Decimal("-40.00"),
        operation_at=date(2024, 10, 15),
        moment_id=source.id,
    )
    db_session.execute(
        text(
            """
            INSERT INTO moment_candidates (
                moment_id,
                split_id,
                status,
                first_seen_at,
                last_seen_at
            )
            VALUES (
                :moment_id,
                :split_id,
                :status,
                :first_seen_at,
                :last_seen_at
            )
            """
        ),
        {
            "moment_id": target.id,
            "split_id": split.id,
            "status": "pending",
            "first_seen_at": datetime.now(timezone.utc),
            "last_seen_at": datetime.now(timezone.utc),
        },
    )
    db_session.flush()

    conflict = client.post(
        f"/moments/{target.id}/candidates/decision",
        json={
            "split_ids": [split.id],
            "decision": "accepted",
            "confirm_reassign": False,
        },
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "MOMENT_REASSIGN_CONFIRM_REQUIRED"

    confirmed = client.post(
        f"/moments/{target.id}/candidates/decision",
        json={
            "split_ids": [split.id],
            "decision": "accepted",
            "confirm_reassign": True,
        },
    )
    assert confirmed.status_code == 200
    db_session.refresh(split)
    assert split.moment_id == target.id


def test_transactions_splits_missing_moment_uses_404_code(client, db_session):
    tx, _split, category = _create_split(
        db_session,
        fingerprint="tx-moment-missing",
        amount=Decimal("-12.00"),
        operation_at=date(2024, 11, 2),
        moment_id=None,
    )

    response = client.put(
        f"/transactions/{tx.id}/splits",
        json={
            "splits": [
                {
                    "amount": "-12.00",
                    "category_id": category.id,
                    "moment_id": 999999,
                }
            ]
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "MOMENT_NOT_FOUND"


def test_transactions_splits_reassign_requires_confirmation(client, db_session):
    source = Moment(name="Tx Source", start_date=date(2024, 12, 1), end_date=date(2024, 12, 31))
    target = Moment(name="Tx Target", start_date=date(2024, 12, 1), end_date=date(2024, 12, 31))
    db_session.add_all([source, target])
    db_session.flush()

    tx, split, category = _create_split(
        db_session,
        fingerprint="tx-reassign",
        amount=Decimal("-18.00"),
        operation_at=date(2024, 12, 12),
        moment_id=source.id,
    )

    payload = {
        "splits": [
            {
                "id": split.id,
                "amount": "-18.00",
                "category_id": category.id,
                "moment_id": target.id,
            }
        ]
    }
    conflict = client.put(f"/transactions/{tx.id}/splits", json=payload)
    assert conflict.status_code == 409
    detail = conflict.json()["detail"]
    assert detail["code"] == "MOMENT_REASSIGN_CONFIRM_REQUIRED"
    assert detail["split_ids"] == [split.id]
    assert detail["source_moment_ids"] == [source.id]
    assert detail["target_moment_ids"] == [target.id]

    confirmed = client.put(
        f"/transactions/{tx.id}/splits",
        json={**payload, "confirm_reassign": True},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["splits"][0]["moment_id"] == target.id


def test_transactions_splits_decision_table_allows_set_and_clear_without_confirmation(client, db_session):
    target = Moment(name="Tx Set/Clear", start_date=date(2024, 12, 1), end_date=date(2024, 12, 31))
    db_session.add(target)
    db_session.flush()

    tx, split, category = _create_split(
        db_session,
        fingerprint="tx-set-clear",
        amount=Decimal("-22.00"),
        operation_at=date(2024, 12, 8),
        moment_id=None,
    )

    set_response = client.put(
        f"/transactions/{tx.id}/splits",
        json={
            "splits": [
                {
                    "id": split.id,
                    "amount": "-22.00",
                    "category_id": category.id,
                    "moment_id": target.id,
                }
            ]
        },
    )
    assert set_response.status_code == 200
    set_payload = set_response.json()
    assert set_payload["splits"][0]["moment_id"] == target.id

    clear_response = client.put(
        f"/transactions/{tx.id}/splits",
        json={
            "splits": [
                {
                    "id": set_payload["splits"][0]["id"],
                    "amount": "-22.00",
                    "category_id": category.id,
                    "moment_id": None,
                }
            ]
        },
    )
    assert clear_response.status_code == 200
    assert clear_response.json()["splits"][0]["moment_id"] is None
