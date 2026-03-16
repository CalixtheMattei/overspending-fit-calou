# ORCHESTRATION PLAN

Date: 2026-02-28  
Source audits: A1, A2, A3, B1, C1, D1, D2, E1, F1

## Executive summary
- Audit-complete: A1, A2, A3, B1, C1, D1, D2, E1, F1 are all completed in `docs/audit`.
- Coding-ready now: Categories (A1/A2/A3), Transactions/Splits (B1/C1), Analytics foundations (D1/D2), Moments core (F1-T1..T4).
- Not fully coding-ready: E1 drilldown work is specified but report does not assign concrete `E1-T*` ticket IDs; keep as a gating admin step before delegation.
- Profile remains intentionally out of scope for this delegation wave.

## Reconciliation: index checklist vs report reality
Stale checklist items in `docs/AUDIT-INDEX.md` (currently unchecked but audit work is complete):
- Categories:
  - `A1 defines target UX parity and acceptance criteria` -> complete (`A1-categories-ux.md`).
  - `A2 validates category API/model constraints and proposes schema deltas` -> complete (`A2-categories-data-api.md`).
  - `A3 specifies create/edit/delete/picker modal states and interactions` -> complete (`A3-category-edit-flow.md`).
  - `Delegated coding tickets are written and scoped` -> complete (A1/A2/A3 tickets present).
- Transactions and Splits:
  - `C1 produces 10-15 must-pass split scenarios + API/UX recommendations` -> complete (`C1-splits-e2e.md`).
- Analytics and Sankey:
  - `D2 defines canonical node/edge semantics + endpoint proposal` -> complete (`D2-sankey-data.md`).
  - `E1 defines drilldown UX/spec and gaps to current code` -> complete (`E1-sankey-drilldown.md`).
  - `Coding tickets ... are drafted` -> partially stale: D1/D2 tickets are concrete; E1 tickets are drafted but unnamed.
- Moments:
  - All four F1 checklist items are complete in report content and delegation outputs.

True remaining work is implementation/execution of drafted tickets, not audit discovery.

## Agent launch matrix
| Coding agent | Ticket IDs owned | Dependencies / blockers | Parallel? | Rationale |
|---|---|---|---|---|
| `agent-categories-backend` | `A2-T1`, `A2-T2`, `A2-T3`, `A2-T4` | `A2-T3` should land before `A3-3`; migration ordering required between `A2-T2` and `A2-T4` | No (serial inside agent) | Sets core API/schema contracts that multiple frontend tickets depend on. |
| `agent-categories-frontend` | `A1-1`, `A1-2`, `A1-3`, `A3-1`, `A3-2`, `A3-4` | `A3-4 -> A1-2`; `A3-4 -> B1-T1/C1-T1` decision on uncategorize semantics | Yes (with other domains) | Consolidates shared picker + categories UX surfaces to reduce component divergence. |
| `agent-categories-delete-flow` | `A3-3` | `A3-3 -> A2-T3` | No | Delete strategy UI must match new backend delete/reassign contract exactly. |
| `agent-splits-core` | `B1-T1`, `B1-T2`, `B1-T3`, `C1-T1`, `C1-T3`, `C1-T4` | Resolve overlap: `C1-T1 <-> B1-T1` should be implemented as one change set; `B1-T3` conflicts with D1/D2 edits in dashboard | Yes (if staged by file ownership) | Highest throughput and correctness impact on daily categorization loop. |
| `agent-splits-tests` | `C1-T2` (+ regression add-ons for `B1-T1`) | Needs final API error contract from `C1-T3` before final assertions | Yes | Expands split invariant coverage and prevents regressions from quick-path edits. |
| `agent-analytics-filters` | `D1-T1`, `D1-T2`, `D1-T3`, `D1-T4` | `D1-T2 -> D1-T3 -> D1-T4`; also unblocks drilldown query propagation | Yes | Creates single filter source of truth and removes known `/analytics` vs `/ledger` drift. |
| `agent-analytics-sankey` | `D2-1`, `D2-2`, `D2-3`, `D2-4` | `D2-2 -> D2-1`; `D2-3` should align with `D1-T1/T2` query contract | Yes | Provides typed node semantics, drilldown APIs, and performance hardening. |
| `agent-moments-core` | `F1-T1`, `F1-T2`, `F1-T3`, `F1-T4` | `F1-T3` should consume final ledger drawer/split navigation behavior; `F1-T4` may depend on split policy from `B1-T1/C1-T1` | Yes | Closes PRD parity gaps with high user-visible value. |
| `agent-moments-optional` | `F1-T5` | Storage/upload decision required | No (delay) | Optional enhancement; defer until core parity tickets are stable. |
| `agent-drilldown-frontend` | E1 drafted items (unnumbered) | Blocked: no concrete `E1-T*` IDs in report; also depends on `D2-2`, `D2-3`, `D1-T2` | No (delay) | Spec is complete but delegation hygiene requires concrete ticket IDs before launch. |

## Ordered execution waves
### Wave 1 - Contract foundations
Parallel group A:
- `A2-T1`, `A2-T2`
- `D1-T1`
- `C1-T2` (can begin scaffolding from existing behavior)
- `F1-T1`

Parallel group B:
- `D2-1`
- `A2-T4`

Merge/integration checkpoint (end of Wave 1):
- Merge backend contract/schema PRs first: `A2-T1/T2`, `D2-1`, `D1-T1`.
- Publish shared contract notes for frontend agents: category ordering/deletion contract, analytics node typing, unified filter shape.

### Wave 2 - Core UX + behavior alignment
Parallel group A (Categories/Splits UX):
- `A1-1`, `A1-2`, `A1-3`, `A3-1`, `A3-2`
- `B1-T1` + `C1-T1` (single combined implementation)
- `B1-T2`, `C1-T3`, `C1-T4`

Parallel group B (Analytics parity):
- `D1-T2`, `D1-T3`
- `D2-2`

Parallel group C (Moments core):
- `F1-T2`, `F1-T3`, `F1-T4`

Merge/integration checkpoint (end of Wave 2):
- Merge `D1-T2/T3` before any drilldown route wiring.
- Merge combined `B1-T1/C1-T1` before `A3-4`.
- Rebase all open PRs touching `dashboard-page.tsx` prior to final review.

### Wave 3 - Drilldown + destructive-flow hardening + performance
Parallel group A:
- `A2-T3` -> `A3-3`
- `A3-4`

Parallel group B:
- `D2-3`
- E1 drafted frontend drilldown items (only after IDs are assigned)

Parallel group C:
- `D1-T4`
- `B1-T3`
- `D2-4`

Parallel group D (optional):
- `F1-T5`

Merge/integration checkpoint (end of Wave 3):
- Merge backend drilldown endpoints (`D2-3`) before frontend drilldown navigation.
- Run cross-surface regression suite (ledger + analytics + moments) before final cut.

## Critical path analysis
Minimum sequence that unlocks most downstream work:
1. `D1-T1 -> D1-T2`
2. `D2-1 -> D2-2 -> D2-3`
3. E1 drilldown frontend implementation (after assigning concrete IDs)

Secondary critical path for risky destructive actions:
1. `A2-T3`
2. `A3-3`

High-conflict operational path:
1. `B1-T1/C1-T1`
2. `A3-4`
3. `B1-T3`

## Risk and coupling notes
Backend-first constraints:
- `A3-3` cannot ship safely before `A2-T3`.
- Drilldown UI should not start until `D2-3` API shape is stable.
- Filter parity UI should consume `D1-T1/T2` contract, not duplicate per-page state.

Frontend-first candidates:
- `A1-1`, `A1-2`, `A1-3`, `A3-1`, `A3-2` can start against existing APIs.
- `F1-T2` UI scaffolding can start before final backend summary fields if mocked/feature-flagged.

Shared files likely to conflict:
- `frontend/src/pages/ledger/dashboard-page.tsx` (A1/A3/B1/D1/D2/E1/F1).
- `frontend/src/components/ledger/splits/split-editor.tsx` (A1/A3/C1/F1).
- `backend/app/routers/transactions.py` (B1/C1/F1).
- `backend/app/routers/analytics.py` (D1/D2/E1).
- `backend/app/routers/categories.py` (A2/A3).

## Suggested branch strategy
Naming convention:
- `agent/<lane>/<ticket-id>-<slug>`
- Examples:
  - `agent/categories-backend/A2-T1-tree-invariants`
  - `agent/splits-core/B1-T1-uncategorize-semantics`
  - `agent/analytics/D2-3-category-drilldown-endpoints`

PR sequencing and merge order:
1. Merge contract PRs first (`A2-T1/T2`, `D1-T1`, `D2-1`).
2. Merge behavior-alignment PRs second (`B1-T1/C1-T1`, `D1-T2/T3`, `D2-2`, `A1/A3 non-delete UI`).
3. Merge destructive/drilldown/perf PRs third (`A2-T3/A3-3`, `D2-3`, `B1-T3`, `D2-4`).
4. Merge optional enhancements last (`F1-T5`).

## Validation plan
Per-agent pre-handoff checks:
- Categories backend (`A2-*`):
  - `pytest backend/tests/test_categories.py -q`
  - add/execute targeted migration tests for `sort_order` + uniqueness.
- Categories frontend (`A1-*`, `A3-*`):
  - frontend unit/integration tests for picker rendering, row actions, delete strategy flow.
- Splits (`B1-*`, `C1-*`):
  - `pytest backend/tests/test_ledger_v2.py -q`
  - `pytest backend/tests/test_split_invariant.py -q`
  - frontend tests for drawer quick categorize + split modal validation/error mapping.
- Analytics (`D1-*`, `D2-*`):
  - `pytest backend/tests/test_analytics.py -q`
  - frontend tests comparing `/analytics` vs `/ledger` totals under identical filters.
- Moments (`F1-*`):
  - `pytest backend/tests/test_moments.py -q`
  - `pytest backend/tests/test_moment_candidates.py -q`
  - moments page interaction tests (edit/delete/open tx/candidates policy).

Cross-agent regression checks after each wave:
- Wave 1: category CRUD + analytics flow contract smoke + migration up/down.
- Wave 2: ledger quick categorize and split modal flows; `/analytics` vs `/ledger` flow parity.
- Wave 3: drilldown route end-to-end, delete reassign safety flow, moments-to-ledger navigation, performance sanity for analytics flow queries.

## Launch now
Launch immediately (parallelizable):
- `agent-categories-backend` for `A2-T1`, `A2-T2`, `A2-T4`
- `agent-analytics-filters` for `D1-T1`
- `agent-analytics-sankey` for `D2-1`
- `agent-splits-tests` for `C1-T2`
- `agent-moments-core` for `F1-T1`

Delay for now:
- `agent-categories-delete-flow` (`A3-3`) until `A2-T3` lands.
- `agent-drilldown-frontend` (E1 drafted items) until concrete ticket IDs are assigned and `D2-2/D2-3` land.
- `agent-moments-optional` (`F1-T5`) pending upload/storage decision.
- `B1-T3` until `D1-T2/T3` and dashboard conflict-heavy PRs stabilize.

Why:
- Immediate set maximizes contract and test foundation with minimal file-collision risk.
- Delayed set depends on unresolved API contracts, missing ticket IDs, or high-conflict files.

## Assumptions and unresolved decisions
- Ticket ID normalization is inconsistent across reports (`A1-1`/`A3-1`/`D2-1` vs `*-T*`). This plan uses IDs exactly as authored in audit files.
- E1 report has drafted tasks but no concrete ticket IDs; assign `E1-T1..E1-T4` before launching a dedicated drilldown frontend agent.
- Test execution may require `TEST_DATABASE_URL`; if unavailable in CI/dev shells, enforce at least static typecheck + targeted frontend tests plus CI DB-backed runs.
