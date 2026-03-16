# D1 - Analytics Filtering System Audit

Status: Completed (2026-02-28)
Owner: D1

## Goal
Audit analytics filter state management and consistency across analytics surfaces.

## Quick repo context
- Analytics page: `frontend/src/pages/analytics-page.tsx`
- Ledger Sankey controls: `frontend/src/pages/ledger/dashboard-page.tsx`
- Analytics API client: `frontend/src/services/analytics.ts`
- Backend analytics router: `backend/app/routers/analytics.py`
- Analytics tests: `backend/tests/test_analytics.py`

## Current snapshot
- `/analytics` owns a full filter object in local component state:
  - `startDate`, `endDate`, `granularity`, `mode`, `excludeTransfers`, `excludeMomentTagged`
  - Source lines: `frontend/src/pages/analytics-page.tsx:51` to `frontend/src/pages/analytics-page.tsx:56`
- `/analytics` threads the same filter values into all three analytics endpoints in one effect:
  - Source lines: `frontend/src/pages/analytics-page.tsx:70` to `frontend/src/pages/analytics-page.tsx:95`
- `/analytics` persists only `excludeMomentTagged` in session storage key `analytics-exclude-moment-tagged`:
  - Source lines: `frontend/src/pages/analytics-page.tsx:21`, `frontend/src/pages/analytics-page.tsx:34`, `frontend/src/pages/analytics-page.tsx:43`, `frontend/src/pages/analytics-page.tsx:117`
- `/ledger` Sankey owns separate state (`flowStart`, `flowEnd`, preset ID, draft date range):
  - Source lines: `frontend/src/pages/ledger/dashboard-page.tsx:159` to `frontend/src/pages/ledger/dashboard-page.tsx:163`
- `/ledger` calls flow endpoint with hardcoded exclusion flags:
  - `exclude_transfers: true`, `exclude_moment_tagged: false`
  - Source lines: `frontend/src/pages/ledger/dashboard-page.tsx:223` to `frontend/src/pages/ledger/dashboard-page.tsx:228`
- `/ledger` Sankey controls expose preset chips and custom date range only (no granularity/mode/exclusion controls):
  - Source lines: `frontend/src/pages/ledger/dashboard-page.tsx:867` to `frontend/src/pages/ledger/dashboard-page.tsx:885`
- Service layer already supports shared optional params for all analytics calls:
  - `start_date`, `end_date`, `exclude_transfers`, `exclude_moment_tagged`
  - plus `granularity`, `mode` on grouped endpoints
  - Source lines: `frontend/src/services/analytics.ts:59` to `frontend/src/services/analytics.ts:118`
- Backend contract is consistent across endpoints for shared exclusion params:
  - `/analytics/flow`: `exclude_transfers`, `exclude_moment_tagged`
  - `/analytics/payees`, `/analytics/internal-accounts`: same flags + `granularity` + `mode`
  - Source lines: `backend/app/routers/analytics.py:49` to `backend/app/routers/analytics.py:239`
- Backend analytics tests cover exclusion matrix and endpoint behaviors:
  - Source lines: `backend/tests/test_analytics.py:231`, `backend/tests/test_analytics.py:250`, `backend/tests/test_analytics.py:298`, `backend/tests/test_analytics.py:348`

## Deliverable checklist
- [x] Current filter state model map (where state lives today).
- [x] Inconsistencies across charts/tables.
- [x] Proposal for single source of truth.

## Inconsistency matrix
- Surface scope mismatch:
  - `/analytics` controls all filter dimensions for all widgets.
  - `/ledger` Sankey only controls date range.
  - Impact: same user question gets different answers depending on page.
- Exclusion mismatch:
  - `/analytics`: user can include transfers and toggle moment-tagged splits.
  - `/ledger`: transfers always excluded, moment-tagged always included.
  - Impact: unavoidable totals divergence between analytics page and ledger Sankey.
- Default-window mismatch:
  - `/analytics`: rolling 90 days (`getDefaultDates`).
  - `/ledger`: fixed preset default `1M`.
  - Impact: first-load comparisons are biased by different time windows.
- Persistence mismatch:
  - `/analytics`: session-only persistence for one toggle.
  - `/ledger`: no Sankey filter persistence (only unrelated status filter in local storage).
  - Impact: navigation resets lead to silent context loss.
- State ownership mismatch:
  - Both pages build separate filter states with no shared typed contract/hook.
  - Impact: filter features are reimplemented and drift over time.

## Single source of truth proposal
- Canonical frontend filter contract:
  - Add `AnalyticsFilterState` in a shared module (suggested path: `frontend/src/features/analytics/filters.ts`).
  - Fields:
    - `startDate`, `endDate`
    - `granularity` (`day|week|month`)
    - `mode` (`user|counterparty`)
    - `excludeTransfers`
    - `excludeMomentTagged`
    - optional `presetId` for ledger-style quick ranges
- Shared state hook:
  - Add `useAnalyticsFilters()` with:
    - normalized defaults
    - reset behavior
    - optional per-surface capability flags (`supportsGranularity`, `supportsMode`)
    - serializer/deserializer for URL query params
- URL-backed synchronization:
  - Store active filters in route query string for `/analytics` and `/ledger`.
  - Keep session/local storage as fallback only for restoring previous state when query params are absent.
- API call unification:
  - Replace hardcoded `/ledger` flow flags with shared state values.
  - Keep `/ledger` UI compact while honoring shared values under the hood.
- Rollout guardrails:
  - Add frontend integration tests to verify that equal filters produce equal flow totals between `/analytics` and `/ledger`.
  - Keep D2/E1 drilldown changes independent, but require drilldown route to consume the same shared filter contract.

## Delegation outputs
- [x] Ticket: Shared analytics filter state across charts/pages.
- [x] Ticket: URL query param contract for analytics filters.
- [x] Ticket: Ledger Sankey filter parity with analytics contract.
- [x] Ticket: Cross-surface analytics consistency regression tests.

## Proposed tickets for coding delegation
- `D1-T1 Shared analytics filter domain`
  - Create `AnalyticsFilterState` type + helpers + range presets in shared feature module.
  - Replace page-local ad hoc defaults with shared defaults.
- `D1-T2 URL/state synchronization`
  - Implement filter query params for `/analytics` and `/ledger`.
  - On initial load, hydrate from URL first, fallback to persisted session/local state.
- `D1-T3 Ledger flow parity`
  - Thread shared `excludeTransfers` and `excludeMomentTagged` values into ledger `fetchAnalyticsFlow` calls.
  - Keep compact controls but add an "advanced filters" bridge link to `/analytics` preserving query params.
- `D1-T4 Regression suite`
  - Add frontend tests that compare `/analytics` and `/ledger` flow totals under identical query params.
  - Add route-navigation test ensuring filter context survives page switches.

## Validation notes
- Static code audit completed for frontend, service layer, backend router, and backend analytics tests.
- Local runtime test execution blocked in this environment: `pytest backend/tests/test_analytics.py` skips because `TEST_DATABASE_URL` is not set.
