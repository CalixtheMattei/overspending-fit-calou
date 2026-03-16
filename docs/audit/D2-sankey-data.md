# D2 - Sankey Data Correctness Audit

Status: Complete (2026-02-28)
Owner: D2

## Goal
Define canonical Sankey semantics and validate backend contract/data correctness.

## Scope audited
- `backend/app/routers/analytics.py`
- `backend/tests/test_analytics.py`
- `frontend/src/services/analytics.ts`
- `frontend/src/components/ledger/charts/sankey-utils.ts`
- `frontend/src/components/ledger/charts/sankey-chart.tsx`
- `frontend/src/pages/ledger/dashboard-page.tsx`
- `frontend/src/pages/analytics-page.tsx`

## Verified current behavior
1. `/analytics/flow` is split-first and coherent: links and totals are derived from the same aggregated pair map (`transaction_type`, `category bucket`), with no-split fallback mapped to `uncategorized`.
2. `exclude_transfers` defaults to `true` and removes transfer source nodes/links from flow data.
3. `exclude_moment_tagged` is applied to split-backed rows only; no-split fallback rows remain included.
4. Backend tests cover totals-vs-links consistency, transfer toggle, and moment-toggle matrix behavior for flow.

## Findings and risks
1. Sankey semantics are still implicit in payload shape. Nodes only expose `id`, `name`, and loose `type`; category nodes are emitted with `type: "expense"` even when fed by income/refund links.
2. Frontend transform drops node IDs and node kinds (`sankey-utils` returns `nodes: {name}[]` only), so interactive drilldown cannot map clicked nodes back to category IDs.
3. Current flow query filters on `transactions.posted_at`, but the indexed date column in schema/model is `transactions.operation_at`; this is a scale risk for larger ledgers.
4. No explicit indexes exist for heavy join/group path fields used by flow (`splits.transaction_id`, `splits.category_id`, `transactions.posted_at`).

## Canonical Sankey semantics recommendation
Lock this as the default overview contract:
1. Dimension model: `transaction_type -> category_bucket`.
2. Source nodes: `expense`, `income`, `refund`, `transfer` (subject to `exclude_transfers`).
3. Target nodes:
   - `cat_{category_id}` for categorized splits
   - `uncategorized` for (a) split rows with `category_id = null` and (b) transactions with zero splits
4. Link value: `abs(split.amount)` for split-backed rows; `abs(transaction.amount)` for no-split fallback rows.
5. Totals: computed strictly as source-wise sums of returned links (never a separate fact source).
6. Transfer rule: excluded by default; included only when `exclude_transfers=false`.

## Required API proposals
1. Keep `GET /analytics/flow` for overview, but upgrade response nodes to typed metadata:
   - `id`, `label`, `kind` (`transaction_type` | `category_bucket`)
   - optional `transaction_type` or `category_id` fields for deterministic client actions
2. Add category branch endpoint for E1 drilldown:
   - `GET /analytics/category/{category_ref}`
   - `GET /analytics/category/{category_ref}/transactions`
   - both accept `start_date`, `end_date`, `exclude_transfers`, `exclude_moment_tagged`
3. Keep a shared filter contract across flow/payees/internal-accounts/category-drilldown endpoints to avoid cross-widget drift.

## Performance notes
1. Current on-demand aggregation is acceptable for small/medium personal datasets.
2. Before broader rollout, add or validate indexes for:
   - `splits(transaction_id)`
   - `splits(category_id)`
   - `transactions(posted_at)` (or switch analytics filters to `operation_at` if that is the canonical analytic date)
3. If response latency grows, add a pre-aggregated daily fact table/materialized view keyed by date, type, and category.

## Rules for uncategorized and transfers
1. Uncategorized must include both `category_id is null` split rows and zero-split transactions.
2. Excluding moment-tagged data should only remove split-backed tagged amounts; no-split rows remain visible.
3. Transfer exclusion must be default-on for spending analytics, with explicit opt-in for inclusion.

## Deliverable checklist
- [x] Recommended Sankey semantics (payee->category vs category->payee vs account->category).
- [x] Required API endpoint proposal(s).
- [x] Performance notes (pre-aggregate vs compute on demand).
- [x] Rules for uncategorized and transfers.

## Delegation outputs
- [x] Ticket D2-1: Formalize `/analytics/flow` typed node contract and preserve backward compatibility for one frontend release.
- [x] Ticket D2-2: Preserve node IDs/kinds in frontend Sankey model and expose node click callbacks for drilldown routing.
- [x] Ticket D2-3: Add category drilldown endpoints and tests (`/analytics/category/{category_ref}` + `/transactions`).
- [x] Ticket D2-4: Add analytics query-path indexes and benchmark query latency before/after.
