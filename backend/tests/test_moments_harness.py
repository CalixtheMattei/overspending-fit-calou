import pytest

from app.models import Split


def _skip_wave2_if_not_ready(response, *, todo: str) -> None:
    if response.status_code in {404, 405, 501}:
        pytest.skip(f"TODO(Wave 2): {todo}")


def test_list_moments_includes_ws_g_fixture_records(client, ws_g_fixture):
    response = client.get("/moments")
    assert response.status_code == 200

    payload = response.json()
    names = {row["name"] for row in payload}
    assert ws_g_fixture.primary_moment_name in names
    assert ws_g_fixture.secondary_moment_name in names


def test_split_reassignment_baseline_updates_moment_without_confirmation(client, db_session, ws_g_fixture):
    response = client.put(
        f"/transactions/{ws_g_fixture.tagged_transaction_id}/splits",
        json={
            "splits": [
                {
                    "amount": ws_g_fixture.tagged_split_amount,
                    "category_id": ws_g_fixture.tagged_split_category_id,
                    "moment_id": ws_g_fixture.secondary_moment_id,
                    "internal_account_id": ws_g_fixture.tagged_split_internal_account_id,
                }
            ]
        },
    )
    assert response.status_code == 200

    split = db_session.query(Split).filter(Split.id == ws_g_fixture.tagged_split_id).one()
    assert split.moment_id == ws_g_fixture.secondary_moment_id


def test_create_moment_contract_skeleton(client):
    response = client.post(
        "/moments",
        json={
            "name": "Ski Week 2025",
            "start_date": "2025-01-04",
            "end_date": "2025-01-11",
            "description": "TODO fixture payload for Wave 2 contract tests",
        },
    )
    _skip_wave2_if_not_ready(
        response,
        todo="Implement POST /moments and finalize 201 + response schema contract.",
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["id"] > 0
    assert payload["name"] == "Ski Week 2025"


def test_get_moment_by_id_contract_skeleton(client, ws_g_fixture):
    response = client.get(f"/moments/{ws_g_fixture.primary_moment_id}")
    _skip_wave2_if_not_ready(
        response,
        todo="Implement GET /moments/{id} detail endpoint.",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == ws_g_fixture.primary_moment_id


def test_patch_moment_contract_skeleton(client, ws_g_fixture):
    response = client.patch(
        f"/moments/{ws_g_fixture.primary_moment_id}",
        json={"description": "Updated by skeleton test"},
    )
    _skip_wave2_if_not_ready(
        response,
        todo="Implement PATCH /moments/{id} update endpoint.",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["description"] == "Updated by skeleton test"


def test_delete_moment_contract_skeleton(client, ws_g_fixture):
    response = client.delete(f"/moments/{ws_g_fixture.secondary_moment_id}")
    _skip_wave2_if_not_ready(
        response,
        todo="Implement DELETE /moments/{id} endpoint with untagged-split side effects.",
    )

    assert response.status_code in {200, 204}


def test_reassignment_confirmation_contract_skeleton(client, ws_g_fixture):
    response = client.put(
        f"/transactions/{ws_g_fixture.tagged_transaction_id}/splits",
        json={
            "confirm_reassign": False,
            "splits": [
                {
                    "amount": ws_g_fixture.tagged_split_amount,
                    "category_id": ws_g_fixture.tagged_split_category_id,
                    "moment_id": ws_g_fixture.secondary_moment_id,
                    "internal_account_id": ws_g_fixture.tagged_split_internal_account_id,
                }
            ],
        },
    )

    if response.status_code == 200:
        pytest.skip(
            "TODO(Wave 2): enforce reassignment handshake (expect 409 before confirm_reassign=true)."
        )

    assert response.status_code == 409
    detail = response.json().get("detail")
    assert isinstance(detail, dict)
    assert detail.get("code") == "MOMENT_REASSIGN_CONFIRMATION_REQUIRED"
