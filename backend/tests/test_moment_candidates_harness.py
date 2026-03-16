import pytest


def _skip_wave2_if_not_ready(response, *, todo: str) -> None:
    if response.status_code in {404, 405, 501}:
        pytest.skip(f"TODO(Wave 2): {todo}")


def test_refresh_candidates_contract_skeleton(client, ws_g_fixture):
    response = client.post(f"/moments/{ws_g_fixture.primary_moment_id}/candidates/refresh")
    _skip_wave2_if_not_ready(
        response,
        todo="Implement POST /moments/{id}/candidates/refresh with upsert semantics.",
    )

    assert response.status_code in {200, 202}
    payload = response.json()
    assert isinstance(payload, dict)


def test_list_pending_candidates_contract_skeleton(client, ws_g_fixture):
    response = client.get(
        f"/moments/{ws_g_fixture.primary_moment_id}/candidates",
        params={"status": "pending"},
    )
    _skip_wave2_if_not_ready(
        response,
        todo="Implement GET /moments/{id}/candidates listing by status.",
    )

    assert response.status_code == 200
    payload = response.json()
    rows = payload["rows"] if isinstance(payload, dict) and "rows" in payload else payload
    assert isinstance(rows, list)


def test_bulk_candidate_decision_contract_skeleton(client, ws_g_fixture):
    response = client.post(
        f"/moments/{ws_g_fixture.primary_moment_id}/candidates/decisions",
        json={
            "decision": "accept",
            "split_ids": [ws_g_fixture.untagged_candidate_split_id],
        },
    )
    _skip_wave2_if_not_ready(
        response,
        todo="Implement bulk accept/reject endpoint and freeze final route path.",
    )

    assert response.status_code in {200, 204}


@pytest.mark.skip(
    reason="TODO(Wave 2): finalize split-id drift/concurrency route contract before enabling this test."
)
def test_candidate_drift_protection_skeleton(client, ws_g_fixture):
    response = client.post(
        f"/moments/{ws_g_fixture.primary_moment_id}/candidates/refresh",
        json={"lock_version": 1},
    )
    assert response.status_code in {200, 409}
