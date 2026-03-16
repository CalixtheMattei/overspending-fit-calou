from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.db import get_db
from app.main import app
from app.models import Account, Category, RuleRunBatch, Split, Transaction, TransactionType


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


def _get_presets(client: TestClient) -> dict[str, object]:
    response = client.get("/categories/presets")
    assert response.status_code == 200
    payload = response.json()
    assert payload["colors"]
    assert payload["icons"]
    return payload


def _get_unknown_root_category(client: TestClient) -> dict[str, object]:
    response = client.get("/categories", params={"limit": 500})
    assert response.status_code == 200
    unknown = next(
        (
            row
            for row in response.json()
            if row["parent_id"] is None and str(row["name"]).strip().lower() == "unknown"
        ),
        None,
    )
    assert unknown is not None
    return unknown


def test_list_categories_includes_metadata_fields(client: TestClient):
    response = client.get("/categories", params={"limit": 200})
    assert response.status_code == 200
    rows = response.json()
    assert rows
    sample = rows[0]
    assert "color" in sample
    assert "icon" in sample
    assert "is_custom" in sample
    assert "display_name" in sample
    assert "is_deprecated" in sample
    assert "canonical_id" in sample
    assert "group" in sample

    by_name = {row["name"]: row for row in rows}
    assert by_name["leasure_and_entertainment"]["display_name"] == "Leisure and entertainment"
    assert by_name["subscriptions"]["is_deprecated"] is True
    assert by_name["subscriptions"]["canonical_id"] is not None
    assert by_name["refunds"]["is_deprecated"] is True


def test_presets_endpoint_includes_enriched_categories_and_tree(client: TestClient):
    response = client.get("/categories/presets")
    assert response.status_code == 200

    payload = response.json()
    assert payload["colors"]
    assert payload["icons"]
    assert isinstance(payload.get("categories"), list)
    assert isinstance(payload.get("tree"), list)
    assert payload["categories"]
    assert payload["tree"]

    categories_by_name = {row["name"]: row for row in payload["categories"]}
    assert categories_by_name["subscriptions"]["is_deprecated"] is True
    assert categories_by_name["subscriptions"]["canonical_id"] is not None

    housing = categories_by_name["housing"]
    rent = categories_by_name["rent"]
    student_housing = categories_by_name["student_housing"]
    assert rent["parent_id"] == housing["id"]
    assert student_housing["parent_id"] == housing["id"]


def test_create_category_validates_presets(client: TestClient):
    bad_color = client.post(
        "/categories",
        json={"name": "Invalid color", "color": "#12345", "icon": "tag"},
    )
    assert bad_color.status_code == 400
    assert bad_color.json()["detail"] == "Invalid category color preset"

    bad_icon = client.post(
        "/categories",
        json={"name": "Invalid icon", "color": "#9CA3AF", "icon": "not-a-real-icon"},
    )
    assert bad_icon.status_code == 400
    assert bad_icon.json()["detail"] == "Invalid category icon preset"


def test_create_and_update_custom_category_with_metadata(client: TestClient):
    presets = _get_presets(client)
    colors = presets["colors"]
    icons = presets["icons"]
    assert isinstance(colors, list)
    assert isinstance(icons, list)
    color_one = str(colors[0])
    color_two = str(colors[1] if len(colors) > 1 else colors[0])
    icon_one = str(icons[0])
    icon_two = str(icons[1] if len(icons) > 1 else icons[0])

    root_response = client.post(
        "/categories",
        json={"name": "Custom Root", "color": color_one, "icon": icon_one},
    )
    assert root_response.status_code == 201
    root = root_response.json()
    assert root["is_custom"] is True
    assert root["color"] == color_one
    assert root["icon"] == icon_one

    child_response = client.post(
        "/categories",
        json={"name": "Custom Child", "parent_id": root["id"], "color": color_two, "icon": icon_two},
    )
    assert child_response.status_code == 201
    child = child_response.json()
    assert child["parent_id"] == root["id"]

    update_response = client.patch(
        f"/categories/{child['id']}",
        json={"name": "Custom Child Updated", "parent_id": None, "color": color_one, "icon": icon_one},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["name"] == "Custom Child Updated"
    assert updated["parent_id"] is None
    assert updated["color"] == color_one
    assert updated["icon"] == icon_one
    assert updated["is_custom"] is True


def test_create_rejects_subcategory_under_unknown_category(client: TestClient):
    presets = _get_presets(client)
    unknown = _get_unknown_root_category(client)
    response = client.post(
        "/categories",
        json={
            "name": "UnknownChildCreateGuard",
            "parent_id": unknown["id"],
            "color": presets["colors"][0],
            "icon": presets["icons"][0],
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Unknown category cannot have subcategories"


def test_update_rejects_move_under_unknown_category(client: TestClient):
    presets = _get_presets(client)
    unknown = _get_unknown_root_category(client)
    root = client.post(
        "/categories",
        json={"name": "UnknownParentMoveGuard", "color": presets["colors"][0], "icon": presets["icons"][0]},
    )
    assert root.status_code == 201

    move = client.patch(f"/categories/{root.json()['id']}", json={"parent_id": unknown["id"]})
    assert move.status_code == 400
    assert move.json()["detail"] == "Unknown category cannot have subcategories"


def test_native_category_is_read_only(client: TestClient):
    list_response = client.get("/categories", params={"limit": 200})
    assert list_response.status_code == 200
    native = next((category for category in list_response.json() if category["is_custom"] is False), None)
    assert native is not None

    update_response = client.patch(f"/categories/{native['id']}", json={"name": "Renamed"})
    assert update_response.status_code == 409
    assert update_response.json()["detail"] == "Native categories are immutable"

    delete_response = client.delete(f"/categories/{native['id']}")
    assert delete_response.status_code == 409
    assert delete_response.json()["detail"] == "Native categories cannot be deleted"


def test_replace_splits_canonicalizes_deprecated_category_id(client: TestClient, db_session):
    categories = client.get("/categories", params={"limit": 500}).json()
    by_name = {row["name"]: row for row in categories}
    deprecated = by_name["subscriptions"]
    canonical = by_name["bills_subscriptions"]

    account = Account(account_num="ACC-CANONICALIZE", label="Canonical test")
    db_session.add(account)
    db_session.flush()

    transaction = Transaction(
        account_id=account.id,
        posted_at=date(2024, 2, 6),
        operation_at=date(2024, 2, 6),
        amount=Decimal("-42.00"),
        currency="EUR",
        label_raw="Subscription charge",
        label_norm="subscription charge",
        supplier_raw=None,
        payee_id=None,
        type=TransactionType.expense,
        fingerprint="test-canonicalize-deprecated-split",
    )
    db_session.add(transaction)
    db_session.flush()

    response = client.put(
        f"/transactions/{transaction.id}/splits",
        json={
            "splits": [
                {
                    "amount": "-42.00",
                    "category_id": deprecated["id"],
                }
            ]
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["splits"][0]["category_id"] == canonical["id"]


def test_replace_splits_rejects_business_branch_for_income_transactions(client: TestClient, db_session):
    categories = client.get("/categories", params={"limit": 500}).json()
    by_name = {row["name"]: row for row in categories}
    business_category = by_name["office_supplies"]

    account = Account(account_num="ACC-INCOME-GUARD", label="Income guard")
    db_session.add(account)
    db_session.flush()

    transaction = Transaction(
        account_id=account.id,
        posted_at=date(2024, 2, 7),
        operation_at=date(2024, 2, 7),
        amount=Decimal("100.00"),
        currency="EUR",
        label_raw="Income row",
        label_norm="income row",
        supplier_raw=None,
        payee_id=None,
        type=TransactionType.income,
        fingerprint="test-income-business-guard",
    )
    db_session.add(transaction)
    db_session.flush()

    response = client.put(
        f"/transactions/{transaction.id}/splits",
        json={
            "splits": [
                {
                    "amount": "100.00",
                    "category_id": business_category["id"],
                }
            ]
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "BUSINESS_CATEGORY_INCOME_NOT_ALLOWED"


def test_rules_endpoint_canonicalizes_deprecated_action_categories(client: TestClient):
    categories = client.get("/categories", params={"limit": 500}).json()
    by_name = {row["name"]: row for row in categories}
    deprecated = by_name["subscriptions"]
    canonical = by_name["bills_subscriptions"]

    response = client.post(
        "/rules",
        json={
            "name": "Canon subscriptions",
            "priority": 1,
            "enabled": True,
            "matcher_json": {"all": [{"predicate": "label_contains", "value": "streaming"}]},
            "action_json": {"set_category": deprecated["id"]},
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["action_json"]["set_category"] == canonical["id"]


def test_create_rule_without_priority_inserts_at_top(client: TestClient):
    categories = client.get("/categories", params={"limit": 500}).json()
    category_id = categories[0]["id"]

    first = client.post(
        "/rules",
        json={
            "name": "Base priority",
            "priority": 10,
            "enabled": True,
            "matcher_json": {"all": [{"predicate": "label_contains", "value": "base"}]},
            "action_json": {"set_category": category_id},
        },
    )
    assert first.status_code == 201

    second = client.post(
        "/rules",
        json={
            "name": "Auto priority",
            "enabled": True,
            "matcher_json": {"all": [{"predicate": "label_contains", "value": "auto"}]},
            "action_json": {"set_category": category_id},
        },
    )
    assert second.status_code == 201
    second_payload = second.json()
    assert second_payload["priority"] == 9

    listed = client.get("/rules")
    assert listed.status_code == 200
    rows = listed.json()
    assert rows[0]["id"] == second_payload["id"]


def test_rules_preview_endpoint_returns_projection_without_mutation(client: TestClient, db_session):
    categories = client.get("/categories", params={"limit": 500}).json()
    category_id = categories[0]["id"]

    account = Account(account_num="ACC-PREVIEW-ENDPOINT", label="Preview endpoint")
    db_session.add(account)
    db_session.flush()

    transaction = Transaction(
        account_id=account.id,
        posted_at=date(2024, 2, 9),
        operation_at=date(2024, 2, 9),
        amount=Decimal("-22.00"),
        currency="EUR",
        label_raw="PREVIEW ENDPOINT LABEL",
        label_norm="preview endpoint label",
        supplier_raw=None,
        payee_id=None,
        type=TransactionType.expense,
        fingerprint="test-rules-preview-endpoint",
    )
    db_session.add(transaction)
    db_session.flush()

    response = client.post(
        "/rules/preview",
        json={
            "scope": {"type": "all"},
            "matcher_json": {"all": [{"predicate": "label_contains", "value": "preview endpoint"}]},
            "action_json": {"set_category": category_id},
            "mode": "non_destructive",
            "limit": 10,
            "offset": 0,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["match_count"] == 1
    assert payload["rows"][0]["transaction_id"] == transaction.id
    assert payload["rows"][0]["before"]["has_splits"] is False
    assert payload["rows"][0]["after"]["category_id"] == category_id

    assert db_session.query(Split).filter(Split.transaction_id == transaction.id).count() == 0
    assert db_session.query(RuleRunBatch).count() == 0


def test_rules_run_endpoint_supports_rule_ids_selection(client: TestClient, db_session):
    categories = client.get("/categories", params={"limit": 500}).json()
    category_one_id = categories[0]["id"]
    category_two_id = categories[1]["id"]

    account = Account(account_num="ACC-RUN-RULE-IDS", label="Run rule ids")
    db_session.add(account)
    db_session.flush()

    transaction = Transaction(
        account_id=account.id,
        posted_at=date(2024, 2, 10),
        operation_at=date(2024, 2, 10),
        amount=Decimal("-33.00"),
        currency="EUR",
        label_raw="RUN RULE IDS LABEL",
        label_norm="run rule ids label",
        supplier_raw=None,
        payee_id=None,
        type=TransactionType.expense,
        fingerprint="test-rules-run-rule-ids",
    )
    db_session.add(transaction)
    db_session.flush()

    first = client.post(
        "/rules",
        json={
            "name": "Run ids first",
            "priority": 1,
            "enabled": True,
            "matcher_json": {"all": [{"predicate": "label_contains", "value": "run rule ids"}]},
            "action_json": {"set_category": category_one_id},
        },
    )
    assert first.status_code == 201

    second = client.post(
        "/rules",
        json={
            "name": "Run ids second",
            "priority": 2,
            "enabled": True,
            "matcher_json": {"all": [{"predicate": "label_contains", "value": "run rule ids"}]},
            "action_json": {"set_category": category_two_id},
        },
    )
    assert second.status_code == 201
    second_payload = second.json()

    run_response = client.post(
        "/rules/run",
        json={
            "scope": "all",
            "mode": "apply",
            "allow_overwrite": False,
            "rule_ids": [second_payload["id"]],
        },
    )
    assert run_response.status_code == 200
    summary = run_response.json()["summary_json"] or {}
    assert summary.get("transactions_changed") == 1

    split = db_session.query(Split).filter(Split.transaction_id == transaction.id).one()
    assert split.category_id == category_two_id


# ---------------------------------------------------------------------------
# A2-T1: Tree depth invariant and sibling uniqueness
# ---------------------------------------------------------------------------


def test_update_rejects_moving_parent_with_children_under_another_root(client: TestClient):
    """Moving a root category that has children under another root would produce depth > 2."""
    presets = _get_presets(client)
    color = presets["colors"][0]
    icon = presets["icons"][0]

    # Create root A with child A1
    root_a = client.post("/categories", json={"name": "TreeTestRootA", "color": color, "icon": icon})
    assert root_a.status_code == 201
    root_a_id = root_a.json()["id"]

    child_a1 = client.post(
        "/categories",
        json={"name": "TreeTestChildA1", "parent_id": root_a_id, "color": color, "icon": icon},
    )
    assert child_a1.status_code == 201

    # Create root B
    root_b = client.post("/categories", json={"name": "TreeTestRootB", "color": color, "icon": icon})
    assert root_b.status_code == 201
    root_b_id = root_b.json()["id"]

    # Try to move root A (which has children) under root B -> should fail
    move = client.patch(f"/categories/{root_a_id}", json={"parent_id": root_b_id})
    assert move.status_code == 400
    assert "max depth is 2" in move.json()["detail"]


def test_update_allows_moving_leaf_under_root(client: TestClient):
    """Moving a leaf (no children) under a root is fine."""
    presets = _get_presets(client)
    color = presets["colors"][0]
    icon = presets["icons"][0]

    root = client.post("/categories", json={"name": "LeafMoveRoot", "color": color, "icon": icon})
    assert root.status_code == 201

    leaf = client.post("/categories", json={"name": "LeafMoveLeaf", "color": color, "icon": icon})
    assert leaf.status_code == 201

    move = client.patch(f"/categories/{leaf.json()['id']}", json={"parent_id": root.json()["id"]})
    assert move.status_code == 200
    assert move.json()["parent_id"] == root.json()["id"]


def test_create_rejects_duplicate_sibling_name(client: TestClient):
    """Two custom categories with the same normalized name under the same parent should be rejected."""
    presets = _get_presets(client)
    color = presets["colors"][0]
    icon = presets["icons"][0]

    first = client.post("/categories", json={"name": "DupSibTest", "color": color, "icon": icon})
    assert first.status_code == 201

    # Same name (case-insensitive / normalized)
    duplicate = client.post("/categories", json={"name": "dup sib test", "color": color, "icon": icon})
    assert duplicate.status_code == 409
    assert "sibling category with the same name" in duplicate.json()["detail"]


def test_update_rejects_duplicate_sibling_name_on_rename(client: TestClient):
    """Renaming a category to collide with a sibling should be rejected."""
    presets = _get_presets(client)
    color = presets["colors"][0]
    icon = presets["icons"][0]

    first = client.post("/categories", json={"name": "RenameSibA", "color": color, "icon": icon})
    assert first.status_code == 201

    second = client.post("/categories", json={"name": "RenameSibB", "color": color, "icon": icon})
    assert second.status_code == 201

    rename = client.patch(f"/categories/{second.json()['id']}", json={"name": "rename sib a"})
    assert rename.status_code == 409
    assert "sibling category with the same name" in rename.json()["detail"]


def test_update_rejects_duplicate_sibling_name_on_move(client: TestClient):
    """Moving a category under a parent where a sibling with the same name exists should be rejected."""
    presets = _get_presets(client)
    color = presets["colors"][0]
    icon = presets["icons"][0]

    root = client.post("/categories", json={"name": "MoveSibRoot", "color": color, "icon": icon})
    assert root.status_code == 201
    root_id = root.json()["id"]

    child_existing = client.post(
        "/categories",
        json={"name": "MoveSibChild", "parent_id": root_id, "color": color, "icon": icon},
    )
    assert child_existing.status_code == 201

    orphan = client.post("/categories", json={"name": "move sib child", "color": color, "icon": icon})
    assert orphan.status_code == 201

    move = client.patch(f"/categories/{orphan.json()['id']}", json={"parent_id": root_id})
    assert move.status_code == 409
    assert "sibling category with the same name" in move.json()["detail"]


# ---------------------------------------------------------------------------
# A2-T2: sort_order contract and reorder endpoint
# ---------------------------------------------------------------------------


def test_category_payload_includes_sort_order(client: TestClient):
    """Category list and presets payloads should include sort_order."""
    response = client.get("/categories", params={"limit": 5})
    assert response.status_code == 200
    rows = response.json()
    assert rows
    assert "sort_order" in rows[0]

    presets = client.get("/categories/presets")
    assert presets.status_code == 200
    cats = presets.json()["categories"]
    assert cats
    assert "sort_order" in cats[0]


def test_reorder_siblings(client: TestClient):
    """PATCH /categories/reorder should update sort_order for siblings."""
    presets = _get_presets(client)
    color = presets["colors"][0]
    icon = presets["icons"][0]

    root = client.post("/categories", json={"name": "ReorderRoot", "color": color, "icon": icon})
    assert root.status_code == 201
    root_id = root.json()["id"]

    c1 = client.post("/categories", json={"name": "ReorderChild1", "parent_id": root_id, "color": color, "icon": icon})
    assert c1.status_code == 201
    c2 = client.post("/categories", json={"name": "ReorderChild2", "parent_id": root_id, "color": color, "icon": icon})
    assert c2.status_code == 201

    # Reorder: put c2 before c1
    reorder = client.patch(
        "/categories/reorder",
        json={
            "parent_id": root_id,
            "items": [
                {"id": c2.json()["id"], "sort_order": 0},
                {"id": c1.json()["id"], "sort_order": 1},
            ],
        },
    )
    assert reorder.status_code == 200
    items = reorder.json()["items"]
    assert items[0]["id"] == c2.json()["id"]
    assert items[0]["sort_order"] == 0
    assert items[1]["id"] == c1.json()["id"]
    assert items[1]["sort_order"] == 1


def test_reorder_rejects_invalid_sibling(client: TestClient):
    """Reordering with a category ID not under the given parent should fail."""
    presets = _get_presets(client)
    color = presets["colors"][0]
    icon = presets["icons"][0]

    root = client.post("/categories", json={"name": "ReorderInvalidRoot", "color": color, "icon": icon})
    assert root.status_code == 201

    orphan = client.post("/categories", json={"name": "ReorderOrphan", "color": color, "icon": icon})
    assert orphan.status_code == 201

    reorder = client.patch(
        "/categories/reorder",
        json={
            "parent_id": root.json()["id"],
            "items": [{"id": orphan.json()["id"], "sort_order": 0}],
        },
    )
    assert reorder.status_code == 400
    assert "not siblings" in reorder.json()["detail"]


# ---------------------------------------------------------------------------
# A2-T4: Guard startup native seed from mutating custom rows
# ---------------------------------------------------------------------------


def test_seed_does_not_overwrite_custom_category(db_session):
    """A custom category whose name matches a native catalog entry must not
    be rewritten as native during seed_native_categories."""
    from app.services.category_catalog import seed_native_categories, load_category_catalog

    # First run the seed to establish native rows
    seed_native_categories(db_session)
    db_session.flush()

    catalog = load_category_catalog()
    native_rows = catalog["native_categories"]
    if not native_rows:
        pytest.skip("No native categories in catalog")

    # Pick a native root category to test against
    native_root_spec = next(r for r in native_rows if r["source_parent_id"] is None)
    native_name = native_root_spec["name"]

    # Create a custom category with the same name (under root, same parent=None)
    custom = Category(
        name=native_name,
        normalized_name=native_name.lower().replace("_", " "),
        parent_id=None,
        color="#FF0000",
        icon="star",
        is_custom=True,
        source=None,  # explicitly not native
        source_ref=None,
    )
    db_session.add(custom)
    db_session.flush()
    custom_id = custom.id

    # Re-run seed — should NOT overwrite the custom row
    seed_native_categories(db_session)
    db_session.flush()

    db_session.refresh(custom)
    assert custom.id == custom_id
    assert custom.is_custom is True, "Custom category was overwritten as native"
    assert custom.source is None, "Custom category source was mutated"
    assert custom.color == "#FF0000", "Custom category color was overwritten"


# ---------------------------------------------------------------------------
# A2-T3: Safe delete/reassign API
# ---------------------------------------------------------------------------


def _make_custom_root(client: TestClient, name: str) -> dict:
    presets = _get_presets(client)
    resp = client.post(
        "/categories",
        json={"name": name, "color": presets["colors"][0], "icon": presets["icons"][0]},
    )
    assert resp.status_code == 201
    return resp.json()


def _make_custom_child(client: TestClient, name: str, parent_id: int) -> dict:
    presets = _get_presets(client)
    resp = client.post(
        "/categories",
        json={"name": name, "parent_id": parent_id, "color": presets["colors"][0], "icon": presets["icons"][0]},
    )
    assert resp.status_code == 201
    return resp.json()


def _add_split_for_category(db_session, category_id: int) -> int:
    """Create a transaction + split using the given category, return the split id."""
    account = Account(account_num=f"ACC-DEL-{category_id}", label="Delete test")
    db_session.add(account)
    db_session.flush()

    txn = Transaction(
        account_id=account.id,
        posted_at=date(2024, 3, 1),
        operation_at=date(2024, 3, 1),
        amount=Decimal("-50.00"),
        currency="EUR",
        label_raw="Delete test",
        label_norm="delete test",
        supplier_raw=None,
        payee_id=None,
        type=TransactionType.expense,
        fingerprint=f"fp-del-{category_id}-{id(account)}",
    )
    db_session.add(txn)
    db_session.flush()

    split = Split(
        transaction_id=txn.id,
        amount=Decimal("-50.00"),
        category_id=category_id,
        position=0,
    )
    db_session.add(split)
    db_session.flush()
    return split.id


def test_delete_preview_returns_correct_counts(client: TestClient, db_session):
    root = _make_custom_root(client, "PreviewRoot")
    child1 = _make_custom_child(client, "PreviewChild1", root["id"])
    child2 = _make_custom_child(client, "PreviewChild2", root["id"])
    _add_split_for_category(db_session, root["id"])
    _add_split_for_category(db_session, root["id"])

    resp = client.get(f"/categories/{root['id']}/delete-preview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["direct_split_count"] == 2
    assert data["child_count"] == 2
    assert len(data["children"]) == 2
    child_ids = {c["id"] for c in data["children"]}
    assert child1["id"] in child_ids
    assert child2["id"] in child_ids


def test_delete_with_reassign_strategy(client: TestClient, db_session):
    source = _make_custom_root(client, "ReassignSource")
    target = _make_custom_root(client, "ReassignTarget")
    split_id = _add_split_for_category(db_session, source["id"])

    resp = client.request(
        "DELETE",
        f"/categories/{source['id']}",
        json={
            "split_action": "reassign",
            "reassign_category_id": target["id"],
            "child_action": "promote",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["deleted"] is True
    assert data["splits_reassigned"] == 1

    split = db_session.query(Split).filter(Split.id == split_id).one()
    assert split.category_id == target["id"]


def test_delete_with_uncategorize_strategy(client: TestClient, db_session):
    source = _make_custom_root(client, "UncatSource")
    split_id = _add_split_for_category(db_session, source["id"])

    resp = client.request(
        "DELETE",
        f"/categories/{source['id']}",
        json={
            "split_action": "uncategorize",
            "child_action": "promote",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["deleted"] is True
    assert data["splits_reassigned"] == 1

    split = db_session.query(Split).filter(Split.id == split_id).one()
    assert split.category_id is None


def test_delete_with_reparent_children_strategy(client: TestClient, db_session):
    parent = _make_custom_root(client, "ReparentParent")
    new_parent = _make_custom_root(client, "ReparentNewParent")
    child = _make_custom_child(client, "ReparentChild", parent["id"])

    resp = client.request(
        "DELETE",
        f"/categories/{parent['id']}",
        json={
            "split_action": "uncategorize",
            "child_action": "reparent",
            "reparent_category_id": new_parent["id"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["deleted"] is True
    assert data["children_moved"] == 1

    moved = db_session.query(Category).filter(Category.id == child["id"]).one()
    assert moved.parent_id == new_parent["id"]


def test_delete_with_promote_children_strategy(client: TestClient, db_session):
    parent = _make_custom_root(client, "PromoteParent")
    child = _make_custom_child(client, "PromoteChild", parent["id"])

    resp = client.request(
        "DELETE",
        f"/categories/{parent['id']}",
        json={
            "split_action": "uncategorize",
            "child_action": "promote",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["deleted"] is True
    assert data["children_moved"] == 1

    promoted = db_session.query(Category).filter(Category.id == child["id"]).one()
    assert promoted.parent_id is None


def test_delete_zero_impact_without_strategy(client: TestClient):
    cat = _make_custom_root(client, "ZeroImpact")

    resp = client.delete(f"/categories/{cat['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["deleted"] is True
    assert data["splits_reassigned"] == 0
    assert data["children_moved"] == 0


def test_delete_rejects_invalid_reassign_target(client: TestClient, db_session):
    source = _make_custom_root(client, "InvalidReassignSrc")
    _add_split_for_category(db_session, source["id"])

    # reassign to self
    resp = client.request(
        "DELETE",
        f"/categories/{source['id']}",
        json={
            "split_action": "reassign",
            "reassign_category_id": source["id"],
            "child_action": "promote",
        },
    )
    assert resp.status_code == 400
    assert "cannot be the category being deleted" in resp.json()["detail"]

    # reassign to non-existent
    resp = client.request(
        "DELETE",
        f"/categories/{source['id']}",
        json={
            "split_action": "reassign",
            "reassign_category_id": 999999,
            "child_action": "promote",
        },
    )
    assert resp.status_code == 400
    assert "does not exist" in resp.json()["detail"]

    # reassign missing when required
    resp = client.request(
        "DELETE",
        f"/categories/{source['id']}",
        json={
            "split_action": "reassign",
            "child_action": "promote",
        },
    )
    assert resp.status_code == 400
    assert "reassign_category_id is required" in resp.json()["detail"]


def test_delete_requires_strategy_when_has_impact(client: TestClient, db_session):
    source = _make_custom_root(client, "NeedsStrategy")
    _add_split_for_category(db_session, source["id"])

    resp = client.delete(f"/categories/{source['id']}")
    assert resp.status_code == 400
    assert "Strategy is required" in resp.json()["detail"]


def test_delete_rejects_reparent_to_non_root(client: TestClient, db_session):
    parent = _make_custom_root(client, "ReparentNonRootParent")
    child_target = _make_custom_child(client, "ReparentNonRootTarget", parent["id"])
    source = _make_custom_root(client, "ReparentNonRootSource")
    _make_custom_child(client, "ReparentNonRootChild", source["id"])

    resp = client.request(
        "DELETE",
        f"/categories/{source['id']}",
        json={
            "split_action": "uncategorize",
            "child_action": "reparent",
            "reparent_category_id": child_target["id"],
        },
    )
    assert resp.status_code == 400
    assert "must be a root category" in resp.json()["detail"]
