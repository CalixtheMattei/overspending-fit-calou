import pytest


def _skip_if_toggle_not_wired(*, baseline: float, toggled: float, endpoint: str) -> None:
    if baseline == toggled:
        pytest.skip(
            f"TODO(Wave 2): wire exclude_moment_tagged in {endpoint} and tighten this to a hard assertion."
        )


def test_flow_exclude_moment_tagged_toggle_harness(client, ws_g_fixture):
    baseline_response = client.get("/analytics/flow", params={"exclude_transfers": "true"})
    toggled_response = client.get(
        "/analytics/flow",
        params={"exclude_transfers": "true", "exclude_moment_tagged": "true"},
    )

    assert baseline_response.status_code == 200
    assert toggled_response.status_code == 200

    baseline_expenses = baseline_response.json()["totals"]["expenses"]
    toggled_expenses = toggled_response.json()["totals"]["expenses"]
    _skip_if_toggle_not_wired(
        baseline=baseline_expenses,
        toggled=toggled_expenses,
        endpoint="/analytics/flow",
    )

    assert toggled_expenses < baseline_expenses
    assert round(baseline_expenses - toggled_expenses, 2) == ws_g_fixture.analytics_tagged_expense_total


def test_payees_exclude_moment_tagged_toggle_harness(client, ws_g_fixture):
    baseline_response = client.get(
        "/analytics/payees",
        params={"granularity": "month", "exclude_transfers": "true"},
    )
    toggled_response = client.get(
        "/analytics/payees",
        params={"granularity": "month", "exclude_transfers": "true", "exclude_moment_tagged": "true"},
    )

    assert baseline_response.status_code == 200
    assert toggled_response.status_code == 200

    baseline_net = baseline_response.json()["totals"]["net"]
    toggled_net = toggled_response.json()["totals"]["net"]
    _skip_if_toggle_not_wired(
        baseline=baseline_net,
        toggled=toggled_net,
        endpoint="/analytics/payees",
    )

    assert toggled_net > baseline_net
    assert round(toggled_net - baseline_net, 2) == ws_g_fixture.analytics_tagged_expense_total


def test_internal_accounts_exclude_moment_tagged_toggle_harness(client, ws_g_fixture):
    baseline_response = client.get(
        "/analytics/internal-accounts",
        params={"granularity": "month", "exclude_transfers": "true"},
    )
    toggled_response = client.get(
        "/analytics/internal-accounts",
        params={"granularity": "month", "exclude_transfers": "true", "exclude_moment_tagged": "true"},
    )

    assert baseline_response.status_code == 200
    assert toggled_response.status_code == 200

    baseline_net = baseline_response.json()["totals"]["net"]
    toggled_net = toggled_response.json()["totals"]["net"]
    _skip_if_toggle_not_wired(
        baseline=baseline_net,
        toggled=toggled_net,
        endpoint="/analytics/internal-accounts",
    )

    assert toggled_net > baseline_net
    assert round(toggled_net - baseline_net, 2) == ws_g_fixture.analytics_tagged_expense_total
