from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.db import get_db
from app.main import app
from app.models import Account, Category, Counterparty, CounterpartyKind, Moment, Split, Transaction, TransactionType


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


def _seed_analytics_fixture(db_session):
    account = Account(account_num="ACC-ANALYTICS", label="Main")
    category_food = Category(name="Food")
    category_salary = Category(name="Salary")
    moment_january = Moment(name="January Moment", start_date=date(2024, 1, 1), end_date=date(2024, 1, 31))
    payee_alice = Counterparty(
        name="Alice Market",
        kind=CounterpartyKind.merchant,
        canonical_name="alice market",
        type=None,
        position=0,
        is_archived=False,
    )
    payee_bob = Counterparty(
        name="Bob Corp",
        kind=CounterpartyKind.merchant,
        canonical_name="bob corp",
        type=None,
        position=0,
        is_archived=False,
    )
    account_cash = Counterparty(
        name="Cash",
        canonical_name="cash",
        kind=CounterpartyKind.internal,
        type="wallet",
        position=0,
        is_archived=False,
    )
    account_savings = Counterparty(
        name="Savings",
        canonical_name="savings",
        kind=CounterpartyKind.internal,
        type="savings",
        position=1,
        is_archived=False,
    )
    db_session.add_all(
        [account, category_food, category_salary, moment_january, payee_alice, payee_bob, account_cash, account_savings]
    )
    db_session.flush()

    tx_expense = Transaction(
        account_id=account.id,
        posted_at=date(2024, 2, 1),
        operation_at=date(2024, 2, 1),
        amount=Decimal("-100.00"),
        currency="EUR",
        label_raw="Expense tx",
        label_norm="expense tx",
        supplier_raw=None,
        payee_id=payee_alice.id,
        type=TransactionType.expense,
        fingerprint="analytics-expense",
    )
    tx_income = Transaction(
        account_id=account.id,
        posted_at=date(2024, 2, 2),
        operation_at=date(2024, 2, 2),
        amount=Decimal("200.00"),
        currency="EUR",
        label_raw="Income tx",
        label_norm="income tx",
        supplier_raw=None,
        payee_id=payee_bob.id,
        type=TransactionType.income,
        fingerprint="analytics-income",
    )
    tx_no_split = Transaction(
        account_id=account.id,
        posted_at=date(2024, 2, 3),
        operation_at=date(2024, 2, 3),
        amount=Decimal("-50.00"),
        currency="EUR",
        label_raw="No split tx",
        label_norm="no split tx",
        supplier_raw=None,
        payee_id=payee_alice.id,
        type=TransactionType.expense,
        fingerprint="analytics-no-split",
    )
    tx_transfer = Transaction(
        account_id=account.id,
        posted_at=date(2024, 2, 4),
        operation_at=date(2024, 2, 4),
        amount=Decimal("-30.00"),
        currency="EUR",
        label_raw="Transfer tx",
        label_norm="transfer tx",
        supplier_raw=None,
        payee_id=payee_bob.id,
        type=TransactionType.transfer,
        fingerprint="analytics-transfer",
    )
    tx_refund = Transaction(
        account_id=account.id,
        posted_at=date(2024, 2, 5),
        operation_at=date(2024, 2, 5),
        amount=Decimal("20.00"),
        currency="EUR",
        label_raw="Refund tx",
        label_norm="refund tx",
        supplier_raw=None,
        payee_id=payee_alice.id,
        type=TransactionType.refund,
        fingerprint="analytics-refund",
    )
    db_session.add_all([tx_expense, tx_income, tx_no_split, tx_transfer, tx_refund])
    db_session.flush()

    db_session.add_all(
        [
            Split(
                transaction_id=tx_expense.id,
                amount=Decimal("-60.00"),
                category_id=category_food.id,
                moment_id=moment_january.id,
                internal_account_id=account_cash.id,
                position=0,
            ),
            Split(
                transaction_id=tx_expense.id,
                amount=Decimal("-40.00"),
                category_id=None,
                internal_account_id=None,
                position=1,
            ),
            Split(
                transaction_id=tx_income.id,
                amount=Decimal("200.00"),
                category_id=category_salary.id,
                internal_account_id=account_savings.id,
                position=0,
            ),
            Split(
                transaction_id=tx_transfer.id,
                amount=Decimal("-30.00"),
                category_id=category_food.id,
                moment_id=moment_january.id,
                internal_account_id=account_cash.id,
                position=0,
            ),
            Split(
                transaction_id=tx_refund.id,
                amount=Decimal("20.00"),
                category_id=category_food.id,
                internal_account_id=account_cash.id,
                position=0,
            ),
        ]
    )
    db_session.commit()


def test_flow_totals_match_links_and_include_uncategorized(client, db_session):
    _seed_analytics_fixture(db_session)

    response = client.get("/analytics/flow")
    assert response.status_code == 200
    payload = response.json()

    source_totals = {"income": 0.0, "expense": 0.0, "refund": 0.0, "transfer": 0.0}
    for link in payload["links"]:
        source_totals[link["source"]] += link["value"]

    assert payload["totals"]["income"] == source_totals["income"]
    assert payload["totals"]["expenses"] == source_totals["expense"]
    assert payload["totals"]["refunds"] == source_totals["refund"]
    assert payload["totals"]["transfers"] == source_totals["transfer"]
    assert payload["totals"]["expenses"] == 150.0
    assert payload["totals"]["income"] == 200.0
    assert payload["totals"]["refunds"] == 20.0
    assert payload["totals"]["transfers"] == 0.0
    assert any(node["id"] == "uncategorized" for node in payload["nodes"])


def test_flow_node_typed_contract(client, db_session):
    """D2-1: every node carries id, name, label, kind, and optional typed metadata."""
    _seed_analytics_fixture(db_session)

    response = client.get("/analytics/flow", params={"exclude_transfers": "false"})
    assert response.status_code == 200
    payload = response.json()
    nodes = payload["nodes"]
    nodes_by_id = {n["id"]: n for n in nodes}

    # All nodes must have the base fields
    for node in nodes:
        assert "id" in node
        assert "name" in node
        assert "label" in node
        assert "kind" in node
        assert node["label"] == node["name"]  # label mirrors name for backward compat

    # Source (transaction_type) nodes
    for tx_type_val in ("expense", "income", "refund", "transfer"):
        node = nodes_by_id[tx_type_val]
        assert node["kind"] == "transaction_type"
        assert node["transaction_type"] == tx_type_val
        assert node["type"] == "source"  # backward compat
        assert "category_id" not in node

    # Category bucket nodes
    category_nodes = [n for n in nodes if n["kind"] == "category_bucket"]
    assert len(category_nodes) >= 2  # at least Food + uncategorized

    for cat_node in category_nodes:
        assert cat_node["type"] == "expense"  # backward compat
        assert "transaction_type" not in cat_node
        if cat_node["id"] == "uncategorized":
            assert "category_id" not in cat_node
            assert cat_node["name"] == "Uncategorized"
        else:
            assert cat_node["id"].startswith("cat_")
            assert isinstance(cat_node["category_id"], int)
            assert cat_node["id"] == f"cat_{cat_node['category_id']}"


def test_flow_node_contract_without_transfers(client, db_session):
    """When transfers excluded, transfer node is absent but others still typed."""
    _seed_analytics_fixture(db_session)

    response = client.get("/analytics/flow")  # exclude_transfers defaults to True
    assert response.status_code == 200
    payload = response.json()
    nodes_by_id = {n["id"]: n for n in payload["nodes"]}

    assert "transfer" not in nodes_by_id
    assert "expense" in nodes_by_id
    assert nodes_by_id["expense"]["kind"] == "transaction_type"


def test_flow_can_include_transfers(client, db_session):
    _seed_analytics_fixture(db_session)

    response = client.get("/analytics/flow", params={"exclude_transfers": "false"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["totals"]["transfers"] == 30.0
    assert any(link["source"] == "transfer" for link in payload["links"])


@pytest.mark.parametrize(
    ("exclude_transfers", "exclude_moment_tagged", "expected_expenses", "expected_transfers"),
    [
        ("true", "false", 150.0, 0.0),
        ("true", "true", 90.0, 0.0),
        ("false", "false", 150.0, 30.0),
        ("false", "true", 90.0, 0.0),
    ],
)
def test_flow_filter_matrix_exclude_transfers_and_moment_tagged(
    client, db_session, exclude_transfers, exclude_moment_tagged, expected_expenses, expected_transfers
):
    _seed_analytics_fixture(db_session)

    response = client.get(
        "/analytics/flow",
        params={
            "exclude_transfers": exclude_transfers,
            "exclude_moment_tagged": exclude_moment_tagged,
        },
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["totals"]["expenses"] == expected_expenses
    assert payload["totals"]["transfers"] == expected_transfers


def test_flow_exclude_moment_tagged_keeps_unsplit_fallback_rows(client, db_session):
    _seed_analytics_fixture(db_session)

    response = client.get(
        "/analytics/flow",
        params={
            "start_date": "2024-02-03",
            "end_date": "2024-02-03",
            "exclude_moment_tagged": "true",
        },
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["totals"]["expenses"] == 50.0
    uncategorized_link = next((link for link in payload["links"] if link["source"] == "expense"), None)
    assert uncategorized_link is not None
    assert uncategorized_link["target"] == "uncategorized"
    assert uncategorized_link["value"] == 50.0


def test_payee_analytics_split_amounts_and_counterparty_mode(client, db_session):
    _seed_analytics_fixture(db_session)

    user_response = client.get("/analytics/payees", params={"granularity": "month", "exclude_transfers": "true"})
    assert user_response.status_code == 200
    user_payload = user_response.json()

    rows_by_name = {row["entity_name"]: row for row in user_payload["rows"]}
    assert rows_by_name["Bob Corp"]["net"] == 200.0
    assert rows_by_name["Bob Corp"]["income"] == 200.0
    assert rows_by_name["Alice Market"]["net"] == -80.0
    assert rows_by_name["Alice Market"]["income"] == 20.0
    assert rows_by_name["Alice Market"]["expense"] == 100.0
    assert user_payload["totals"]["net"] == 120.0

    counterparty_response = client.get(
        "/analytics/payees",
        params={"granularity": "month", "exclude_transfers": "true", "mode": "counterparty"},
    )
    assert counterparty_response.status_code == 200
    counterparty_payload = counterparty_response.json()
    counterparty_rows_by_name = {row["entity_name"]: row for row in counterparty_payload["rows"]}
    assert counterparty_rows_by_name["Bob Corp"]["net"] == -200.0
    assert counterparty_rows_by_name["Alice Market"]["net"] == 80.0
    assert counterparty_payload["totals"]["net"] == -120.0


def test_payee_analytics_can_exclude_moment_tagged_splits(client, db_session):
    _seed_analytics_fixture(db_session)

    response = client.get(
        "/analytics/payees",
        params={
            "granularity": "month",
            "exclude_transfers": "true",
            "exclude_moment_tagged": "true",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    rows_by_name = {row["entity_name"]: row for row in payload["rows"]}

    assert rows_by_name["Bob Corp"]["net"] == 200.0
    assert rows_by_name["Alice Market"]["net"] == -20.0
    assert rows_by_name["Alice Market"]["income"] == 20.0
    assert rows_by_name["Alice Market"]["expense"] == 40.0
    assert payload["totals"]["net"] == 180.0


def test_internal_account_analytics_includes_unassigned_and_mode_inversion(client, db_session):
    _seed_analytics_fixture(db_session)

    user_response = client.get(
        "/analytics/internal-accounts",
        params={"granularity": "month", "exclude_transfers": "true"},
    )
    assert user_response.status_code == 200
    user_payload = user_response.json()
    rows_by_name = {row["entity_name"]: row for row in user_payload["rows"]}

    assert rows_by_name["Savings"]["net"] == 200.0
    assert rows_by_name["Cash"]["net"] == -40.0
    assert rows_by_name["Unassigned"]["net"] == -40.0

    counterparty_response = client.get(
        "/analytics/internal-accounts",
        params={"granularity": "month", "exclude_transfers": "true", "mode": "counterparty"},
    )
    assert counterparty_response.status_code == 200
    counterparty_payload = counterparty_response.json()
    counterparty_rows_by_name = {row["entity_name"]: row for row in counterparty_payload["rows"]}

    assert counterparty_rows_by_name["Savings"]["net"] == -200.0
    assert counterparty_rows_by_name["Cash"]["net"] == 40.0
    assert counterparty_rows_by_name["Unassigned"]["net"] == 40.0


def test_internal_account_analytics_can_exclude_moment_tagged_splits(client, db_session):
    _seed_analytics_fixture(db_session)

    response = client.get(
        "/analytics/internal-accounts",
        params={
            "granularity": "month",
            "exclude_transfers": "true",
            "exclude_moment_tagged": "true",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    rows_by_name = {row["entity_name"]: row for row in payload["rows"]}

    assert rows_by_name["Savings"]["net"] == 200.0
    assert rows_by_name["Cash"]["net"] == 20.0
    assert rows_by_name["Unassigned"]["net"] == -40.0


# ---------------------------------------------------------------------------
# D1-T4  Cross-surface analytics consistency regression tests
# ---------------------------------------------------------------------------


def test_flow_and_payee_totals_agree_on_net(client, db_session):
    """Flow totals (income - expenses + refunds) must equal payee net total."""
    _seed_analytics_fixture(db_session)

    flow = client.get("/analytics/flow").json()
    payee = client.get("/analytics/payees", params={"granularity": "month", "exclude_transfers": "true"}).json()

    flow_net = flow["totals"]["income"] - flow["totals"]["expenses"] + flow["totals"]["refunds"]
    assert abs(flow_net - payee["totals"]["net"]) < 0.01


def test_flow_date_filter_matches_payee_date_filter(client, db_session):
    """Same date range on /flow and /payees must yield consistent expense totals."""
    _seed_analytics_fixture(db_session)
    params = {"start_date": "2024-02-01", "end_date": "2024-02-03", "exclude_transfers": "true"}

    flow = client.get("/analytics/flow", params=params).json()
    payee = client.get("/analytics/payees", params={**params, "granularity": "month"}).json()

    assert flow["totals"]["expenses"] == payee["totals"]["expense"]


def test_transfer_exclusion_parity_across_endpoints(client, db_session):
    """exclude_transfers=true must remove transfers from flow, payees, and internal-accounts equally."""
    _seed_analytics_fixture(db_session)

    flow_excl = client.get("/analytics/flow", params={"exclude_transfers": "true"}).json()
    flow_incl = client.get("/analytics/flow", params={"exclude_transfers": "false"}).json()

    assert flow_excl["totals"]["transfers"] == 0.0
    assert flow_incl["totals"]["transfers"] == 30.0

    # Payees should not include the transfer's payee split amount when excluded
    payee_excl = client.get(
        "/analytics/payees", params={"granularity": "month", "exclude_transfers": "true"}
    ).json()
    payee_incl = client.get(
        "/analytics/payees", params={"granularity": "month", "exclude_transfers": "false"}
    ).json()

    # Bob Corp has the transfer — with exclusion, only income; without, income + transfer
    bob_excl = next(r for r in payee_excl["rows"] if r["entity_name"] == "Bob Corp")
    bob_incl = next(r for r in payee_incl["rows"] if r["entity_name"] == "Bob Corp")
    assert bob_excl["expense"] == 0.0
    assert bob_incl["expense"] == 30.0


def test_moment_exclusion_parity_across_endpoints(client, db_session):
    """exclude_moment_tagged must have consistent effect on flow, payees, and internal-accounts."""
    _seed_analytics_fixture(db_session)

    flow = client.get("/analytics/flow", params={"exclude_moment_tagged": "true"}).json()
    payee = client.get(
        "/analytics/payees",
        params={"granularity": "month", "exclude_transfers": "true", "exclude_moment_tagged": "true"},
    ).json()
    ia = client.get(
        "/analytics/internal-accounts",
        params={"granularity": "month", "exclude_transfers": "true", "exclude_moment_tagged": "true"},
    ).json()

    # All three should show expenses = 90 (150 - 60 moment-tagged expense split)
    assert flow["totals"]["expenses"] == 90.0
    assert payee["totals"]["expense"] == 40.0  # Only Alice's non-moment splits
    assert ia["totals"]["expense"] == 40.0


def test_empty_date_range_returns_zeroes(client, db_session):
    """A date range with no data should return zero totals, not errors."""
    _seed_analytics_fixture(db_session)
    params = {"start_date": "2025-01-01", "end_date": "2025-01-31"}

    flow = client.get("/analytics/flow", params=params).json()
    assert flow["totals"]["expenses"] == 0.0
    assert flow["totals"]["income"] == 0.0
    assert flow["links"] == []

    payee = client.get("/analytics/payees", params={**params, "granularity": "month"}).json()
    assert payee["rows"] == []
    assert payee["totals"]["net"] == 0.0


def test_flow_links_sum_equals_totals(client, db_session):
    """Every link's value summed by source type must match totals exactly."""
    _seed_analytics_fixture(db_session)

    flow = client.get("/analytics/flow", params={"exclude_transfers": "false"}).json()

    link_sums = {"income": 0.0, "expense": 0.0, "refund": 0.0, "transfer": 0.0}
    for link in flow["links"]:
        link_sums[link["source"]] += link["value"]

    assert abs(link_sums["income"] - flow["totals"]["income"]) < 0.01
    assert abs(link_sums["expense"] - flow["totals"]["expenses"]) < 0.01
    assert abs(link_sums["refund"] - flow["totals"]["refunds"]) < 0.01
    assert abs(link_sums["transfer"] - flow["totals"]["transfers"]) < 0.01


# ---------------------------------------------------------------------------
# E1-T4  Category drilldown endpoint tests
# ---------------------------------------------------------------------------


def test_drilldown_parent_category_with_children(client, db_session):
    """Parent category drilldown should include children by default."""
    _seed_analytics_fixture(db_session)

    # Food is a root category with splits
    # First get the category id
    cats = client.get("/categories").json()
    food_cat = next(c for c in cats if c["name"] == "Food")
    food_id = food_cat["id"]

    resp = client.get(f"/analytics/category/{food_id}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["category"]["name"] == "Food"
    assert data["category"]["scope_type"] == "parent"
    # Food has: expense split -60 (moment-tagged), transfer split -30, refund split +20
    # With exclude_transfers=True (default): expense 60 + refund 20 = 80 abs
    assert data["totals"]["expense_abs"] == 60.0
    assert data["totals"]["refund_abs"] == 20.0
    assert data["totals"]["transfer_abs"] == 0.0  # transfers excluded by default
    assert data["transaction_count"] >= 2  # expense + refund


def test_drilldown_parent_with_transfers_included(client, db_session):
    """Drilldown with exclude_transfers=false should include transfers."""
    _seed_analytics_fixture(db_session)

    cats = client.get("/categories").json()
    food_cat = next(c for c in cats if c["name"] == "Food")
    food_id = food_cat["id"]

    resp = client.get(f"/analytics/category/{food_id}", params={"exclude_transfers": "false"})
    assert resp.status_code == 200
    data = resp.json()

    assert data["totals"]["transfer_abs"] == 30.0
    assert data["totals"]["expense_abs"] == 60.0


def test_drilldown_uncategorized(client, db_session):
    """Uncategorized drilldown includes null-category splits and zero-split transactions."""
    _seed_analytics_fixture(db_session)

    resp = client.get("/analytics/category/uncategorized")
    assert resp.status_code == 200
    data = resp.json()

    assert data["category"]["name"] == "Uncategorized"
    assert data["category"]["scope_type"] == "uncategorized"
    # Uncategorized: split with category_id=None (-40 on expense tx) + no-split tx (-50)
    assert data["totals"]["expense_abs"] == 90.0
    assert data["transaction_count"] == 2  # expense tx (via null split) + no-split tx


def test_drilldown_date_filtering(client, db_session):
    """Drilldown respects date range filters."""
    _seed_analytics_fixture(db_session)

    cats = client.get("/categories").json()
    food_cat = next(c for c in cats if c["name"] == "Food")
    food_id = food_cat["id"]

    # Only Feb 5 (refund day)
    resp = client.get(
        f"/analytics/category/{food_id}",
        params={"start_date": "2024-02-05", "end_date": "2024-02-05"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["totals"]["expense_abs"] == 0.0
    assert data["totals"]["refund_abs"] == 20.0
    assert data["transaction_count"] == 1


def test_drilldown_nonexistent_category_returns_404(client, db_session):
    """Requesting a non-existent category ID returns 404."""
    _seed_analytics_fixture(db_session)

    resp = client.get("/analytics/category/99999")
    assert resp.status_code == 404


def test_drilldown_transactions_pagination(client, db_session):
    """Drilldown transactions endpoint supports pagination."""
    _seed_analytics_fixture(db_session)

    resp = client.get(
        "/analytics/category/uncategorized/transactions",
        params={"limit": 1, "offset": 0},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["total"] == 2  # null-split + no-split tx
    assert len(data["rows"]) == 1
    assert data["limit"] == 1
    assert data["offset"] == 0

    # Second page
    resp2 = client.get(
        "/analytics/category/uncategorized/transactions",
        params={"limit": 1, "offset": 1},
    )
    data2 = resp2.json()
    assert len(data2["rows"]) == 1
    assert data2["rows"][0]["transaction_id"] != data["rows"][0]["transaction_id"]


def test_drilldown_transactions_row_shape(client, db_session):
    """Each transaction row must have the expected fields including branch_amount_abs."""
    _seed_analytics_fixture(db_session)

    cats = client.get("/categories").json()
    food_cat = next(c for c in cats if c["name"] == "Food")
    food_id = food_cat["id"]

    resp = client.get(f"/analytics/category/{food_id}/transactions")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total"] >= 1
    row = data["rows"][0]
    expected_keys = {
        "transaction_id", "posted_at", "label_raw", "type",
        "payee", "account", "transaction_amount", "branch_amount_abs",
        "matched_split_count",
    }
    assert expected_keys.issubset(set(row.keys()))
    assert row["branch_amount_abs"] > 0
    assert row["matched_split_count"] >= 1


def test_drilldown_transactions_nonexistent_category_returns_404(client, db_session):
    """Transactions endpoint also returns 404 for unknown category."""
    _seed_analytics_fixture(db_session)

    resp = client.get("/analytics/category/99999/transactions")
    assert resp.status_code == 404


def test_drilldown_exclude_moment_tagged(client, db_session):
    """Drilldown with exclude_moment_tagged should exclude moment-tagged splits."""
    _seed_analytics_fixture(db_session)

    cats = client.get("/categories").json()
    food_cat = next(c for c in cats if c["name"] == "Food")
    food_id = food_cat["id"]

    resp = client.get(
        f"/analytics/category/{food_id}",
        params={"exclude_moment_tagged": "true"},
    )
    assert resp.status_code == 200
    data = resp.json()

    # Food splits: -60 (moment-tagged, excluded), -30 (transfer, excluded by default), +20 (refund, no moment)
    assert data["totals"]["expense_abs"] == 0.0
    assert data["totals"]["refund_abs"] == 20.0
