# E1 - Sankey Drilldown Spec and Gap Analysis

Status: Completed (2026-02-28)
Owner: E1
Commit audited: `773fd310aa724159902383f9bdc2f5e33b038777`

## Goal
Define Finary-like category drilldown from Sankey into a focused branch view with impacted transactions.

## Repo audit snapshot
- Sankey is rendered on `/ledger` only and is currently passive: no click handlers and no drilldown navigation.
- `buildSankeyData` strips backend node IDs and returns only `{ name }`, which prevents reliable category-node click mapping.
- Current flow data is `transaction_type -> category_bucket` from `GET /analytics/flow`; category buckets are backend IDs (`cat_<id>`) plus `uncategorized`.
- No route exists for `/analytics/category/:id`.
- No analytics endpoint exists for category-branch drilldown or filter-aligned impacted transactions.
- `GET /transactions` supports `category_id` but does not support analytics date/toggle filters, so it cannot power filter-aligned drilldown by itself.

## Drilldown UX spec (E1)
### Entry points
- Clicking a Sankey category node opens `/analytics/category/:categoryRef`.
- `:categoryRef` accepts numeric category ID or `uncategorized`.
- Optional query params are carried forward from analytics filters:
  - `start_date`
  - `end_date`
  - `exclude_transfers`
  - `exclude_moment_tagged`
  - `from` (`ledger` or `analytics`) for back-navigation intent

### Drilldown page layout
- Header:
  - Category name (or "Uncategorized")
  - Date/toggle filter summary
  - Back link to `from` route (default `/analytics`)
- Branch summary:
  - `branch_total_abs`
  - `branch_expense_abs`
  - `branch_income_abs`
  - `branch_refund_abs`
  - `transaction_count`
- Branch visualization:
  - Focused branch chart for selected category scope only.
  - Parent category drilldown includes direct children (2-level tree constraint already enforced by categories API).
  - Child category drilldown shows child-only branch.
- Impacted transactions:
  - Paginated table sorted by `posted_at desc, transaction_id desc`.
  - Each row includes branch contribution (`branch_amount_abs`) and transaction amount.
  - Supports opening existing transaction detail flow.

### Scope semantics
- For parent categories: include splits where `category_id == parent_id` or `category.parent_id == parent_id`.
- For child categories: include only `category_id == child_id`.
- For `uncategorized`: include both:
  - splits with `category_id is null`
  - transactions with zero splits (fallback already present in flow semantics)

## Gap analysis vs current code
- Gap 1: no drilldown route in router config (`frontend/src/main.tsx`).
- Gap 2: Sankey data transform drops node IDs (`frontend/src/components/ledger/charts/sankey-utils.ts`).
- Gap 3: Sankey renderer has no click contract/callback (`frontend/src/components/ledger/charts/sankey-chart.tsx`).
- Gap 4: ledger Sankey host does not wire node interactions to navigation (`frontend/src/pages/ledger/dashboard-page.tsx`).
- Gap 5: backend has no category-branch drilldown endpoint (`backend/app/routers/analytics.py`).
- Gap 6: transactions API cannot align with analytics drilldown filters for date/toggles (`backend/app/routers/transactions.py`).
- Gap 7: no tests for drilldown contracts in analytics test suite (`backend/tests/test_analytics.py`).

## API requirements for drilldown
### 1) Branch aggregate endpoint
- `GET /analytics/category/{category_ref}`
- Params:
  - `start_date`, `end_date`
  - `exclude_transfers` (default `true`)
  - `exclude_moment_tagged` (default `false`)
  - `include_children` (default `true`, ignored for child categories and uncategorized)
- Response:
  - resolved category metadata (`id`, `name`, `parent_id`, `scope_type`)
  - resolved scope category IDs
  - branch totals (`income_abs`, `expense_abs`, `refund_abs`, `transfer_abs`, `net`, `absolute_total`)
  - optional branch nodes/links for focused visualization
  - `transaction_count`

### 2) Impacted transactions endpoint
- `GET /analytics/category/{category_ref}/transactions`
- Params:
  - same filter params as aggregate endpoint
  - `limit`, `offset`
- Response:
  - `rows`, `limit`, `offset`, `total`
  - row fields:
    - `transaction_id`, `posted_at`, `label_raw`, `type`
    - `payee`, `account`
    - `transaction_amount`
    - `branch_amount_abs`
    - `matched_split_count`

## Delegation outputs (tickets for next coding session)
- [x] `E1-T1`: Backend category drilldown endpoints + uncategorized semantics (see API requirements above).
- [x] `E1-T2`: Make Sankey data and chart interaction-capable (preserve node IDs and node click callback). Overlaps with D2-2.
- [x] `E1-T3`: Frontend route + page for `/analytics/category/:categoryRef`.
- [x] `E1-T4`: Analytics drilldown tests (endpoint filters, parent/child scope, uncategorized, pagination).

## Suggested implementation order
1. Backend endpoints and tests.
2. Frontend service client additions for new analytics drilldown endpoints.
3. Route + page scaffold for `/analytics/category/:categoryRef`.
4. Sankey node click wiring from `/ledger` to drilldown route with filter query propagation.
5. Manual QA on parent, child, and uncategorized paths.
